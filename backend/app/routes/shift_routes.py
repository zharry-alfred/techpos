from decimal import Decimal
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.tenant import UserRole
from app.models.shift import CashShift, CashMovement, ShiftStatus
from app.utils.auth_guards import role_required, get_current_tenant_id, active_license_required

shift_bp = Blueprint('shifts', __name__, url_prefix='/api/v1/shifts')

@shift_bp.route('/current', methods=['GET'])
@jwt_required()
@active_license_required
def get_current_shift():
    """Retrieve active shift details and live X-report snapshot."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()

    shift = CashShift.query.filter_by(
        store_id=store_id,
        user_id=user_id,
        status=ShiftStatus.OPEN
    ).first()

    if not shift:
        return jsonify({"has_open_shift": False, "shift": None}), 200

    # Build real-time X-report
    x_report = {
        "shift_id": str(shift.id),
        "cashier": shift.cashier.full_name if shift.cashier else "Cashier",
        "opened_at": shift.opened_at.isoformat(),
        "opening_float": float(shift.opening_float),
        "total_cash_sales": float(shift.total_cash_sales),
        "total_card_sales": float(shift.total_card_sales),
        "total_mobile_sales": float(shift.total_mobile_sales),
        "total_drops": float(shift.total_drops),
        "total_payouts": float(shift.total_payouts),
        "expected_in_drawer": float(shift.expected_cash),
        "snapshot_time": datetime.now(timezone.utc).isoformat()
    }

    return jsonify({
        "has_open_shift": True,
        "shift": shift.to_dict(),
        "x_report": x_report
    }), 200

@shift_bp.route('/open', methods=['POST'])
@jwt_required()
@active_license_required
def open_shift():
    """Open cash drawer shift with initial opening float."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    opening_float = Decimal(str(data.get('opening_float', 0.00)))
    terminal_id = data.get('terminal_id', 'POS-01')

    # Check for existing open shift for this user
    existing = CashShift.query.filter_by(
        store_id=store_id,
        user_id=user_id,
        status=ShiftStatus.OPEN
    ).first()

    if existing:
        return jsonify({
            "error": "You already have an open shift. Please close it before opening a new one.",
            "shift": existing.to_dict()
        }), 400

    shift = CashShift(
        store_id=store_id,
        user_id=user_id,
        terminal_id=terminal_id,
        status=ShiftStatus.OPEN,
        opening_float=opening_float,
        expected_cash=opening_float
    )
    db.session.add(shift)
    db.session.commit()

    return jsonify({
        "message": "Shift opened successfully",
        "shift": shift.to_dict()
    }), 201

@shift_bp.route('/drop', methods=['POST'])
@jwt_required()
@active_license_required
def cash_drop_or_payout():
    """Log mid-shift cash drop to safe or payout/petty cash."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    shift = CashShift.query.filter_by(
        store_id=store_id,
        user_id=user_id,
        status=ShiftStatus.OPEN
    ).first()

    if not shift:
        return jsonify({"error": "No open shift found"}), 404

    movement_type = data.get('movement_type', 'CASH_DROP') # CASH_DROP, PAYOUT, FLOAT_ADD
    amount = Decimal(str(data.get('amount', 0.00)))
    reason = data.get('reason', 'Safe drop')
    notes = data.get('notes')

    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400

    movement = CashMovement(
        shift_id=shift.id,
        store_id=store_id,
        user_id=user_id,
        movement_type=movement_type,
        amount=amount,
        reason=reason,
        notes=notes
    )
    db.session.add(movement)

    if movement_type == 'CASH_DROP':
        shift.total_drops = Decimal(str(shift.total_drops)) + amount
        shift.expected_cash = Decimal(str(shift.expected_cash)) - amount
    elif movement_type in ['PAYOUT', 'PETTY_CASH']:
        shift.total_payouts = Decimal(str(shift.total_payouts)) + amount
        shift.expected_cash = Decimal(str(shift.expected_cash)) - amount
    elif movement_type == 'FLOAT_ADD':
        shift.expected_cash = Decimal(str(shift.expected_cash)) + amount

    db.session.commit()
    return jsonify({
        "message": f"{movement_type} recorded successfully",
        "movement": movement.to_dict(),
        "expected_cash": float(shift.expected_cash)
    }), 201

@shift_bp.route('/close', methods=['POST'])
@jwt_required()
@active_license_required
def close_shift():
    """Close shift, reconcile actual counted cash vs expected, and generate Z-Report."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    shift = CashShift.query.filter_by(
        store_id=store_id,
        user_id=user_id,
        status=ShiftStatus.OPEN
    ).first()

    if not shift:
        return jsonify({"error": "No open shift found to close"}), 404

    closing_cash_actual = Decimal(str(data.get('closing_cash_actual', shift.expected_cash)))
    closing_notes = data.get('closing_notes')
    discrepancy = closing_cash_actual - shift.expected_cash

    now = datetime.now(timezone.utc)

    # Build final Z-Report
    z_report = {
        "z_report_number": f"Z-{shift.terminal_id}-{now.strftime('%Y%m%d%H%M%S')}",
        "shift_id": str(shift.id),
        "terminal_id": shift.terminal_id,
        "cashier": shift.cashier.full_name if shift.cashier else "Cashier",
        "opened_at": shift.opened_at.isoformat(),
        "closed_at": now.isoformat(),
        "opening_float": float(shift.opening_float),
        "total_cash_sales": float(shift.total_cash_sales),
        "total_card_sales": float(shift.total_card_sales),
        "total_mobile_sales": float(shift.total_mobile_sales),
        "gross_sales": float(shift.total_cash_sales + shift.total_card_sales + shift.total_mobile_sales),
        "total_drops": float(shift.total_drops),
        "total_payouts": float(shift.total_payouts),
        "expected_cash": float(shift.expected_cash),
        "closing_cash_actual": float(closing_cash_actual),
        "discrepancy": float(discrepancy),
        "status": "BALANCED" if discrepancy == 0 else ("OVERAGE" if discrepancy > 0 else "SHORTAGE"),
        "notes": closing_notes
    }

    shift.status = ShiftStatus.CLOSED
    shift.closing_cash_actual = closing_cash_actual
    shift.discrepancy = discrepancy
    shift.closing_notes = closing_notes
    shift.z_report_json = z_report
    shift.closed_at = now

    db.session.commit()
    return jsonify({
        "message": "Shift closed successfully. Z-Report generated.",
        "shift": shift.to_dict(),
        "z_report": z_report
    }), 200

@shift_bp.route('/history', methods=['GET'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def shift_history():
    """Retrieve historical shifts and reconciliation audit reports."""
    store_id = get_current_tenant_id()
    shifts = CashShift.query.filter_by(store_id=store_id).order_by(CashShift.opened_at.desc()).limit(50).all()
    return jsonify({"shifts": [s.to_dict() for s in shifts]}), 200
