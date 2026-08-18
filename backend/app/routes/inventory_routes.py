from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.tenant import UserRole
from app.models.stock import StockLevel, StockTransfer, StockAdjustmentLog
from app.services.inventory_service import InventoryService
from app.utils.auth_guards import role_required, get_current_tenant_id, active_license_required

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/v1/inventory')

@inventory_bp.route('/adjust', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def adjust_inventory():
    """Manual stock adjustment (Spec Section 4: /api/v1/inventory/adjust)."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    item_id = data.get('item_id')
    quantity_delta = data.get('quantity_delta')
    reason = data.get('reason', 'MANUAL_ADJUSTMENT')
    notes = data.get('notes')
    batch_number = data.get('batch_number', 'DEFAULT')

    if not item_id or quantity_delta is None:
        return jsonify({"error": "item_id and quantity_delta are required"}), 400

    try:
        stock = InventoryService.adjust_stock(
            store_id=store_id,
            item_id=item_id,
            quantity_delta=float(quantity_delta),
            reason=reason,
            user_id=user_id,
            batch_number=batch_number,
            notes=notes
        )
        db.session.commit()
        return jsonify({
            "message": "Stock adjusted successfully",
            "stock": stock.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@inventory_bp.route('/low-stock', methods=['GET'])
@jwt_required()
@active_license_required
def get_low_stock():
    """List low-stock warning items."""
    store_id = get_current_tenant_id()
    low_stock = InventoryService.get_low_stock_items(store_id)
    return jsonify({"low_stock_items": low_stock, "count": len(low_stock)}), 200

@inventory_bp.route('/logs', methods=['GET'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def list_adjustment_logs():
    """Get historical audit trail of stock adjustments."""
    store_id = get_current_tenant_id()
    logs = StockAdjustmentLog.query.filter_by(store_id=store_id).order_by(StockAdjustmentLog.created_at.desc()).limit(100).all()
    return jsonify({"logs": [log.to_dict() for log in logs]}), 200

@inventory_bp.route('/transfers', methods=['GET'])
@jwt_required()
@active_license_required
def list_transfers():
    """List all stock transfers for the store (both inbound and outbound)."""
    store_id = get_current_tenant_id()
    transfers = StockTransfer.query.filter(
        (StockTransfer.source_store_id == store_id) | (StockTransfer.destination_store_id == store_id)
    ).order_by(StockTransfer.created_at.desc()).all()
    return jsonify({"transfers": [t.to_dict() for t in transfers]}), 200

@inventory_bp.route('/transfers', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def create_transfer():
    """Request a new Inter-Store Stock Transfer."""
    source_store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    destination_store_id = data.get('destination_store_id')
    items = data.get('items', []) # [{'item_id': str, 'quantity': float}]
    notes = data.get('notes')

    if not destination_store_id or not items:
        return jsonify({"error": "destination_store_id and items list are required"}), 400

    if destination_store_id == source_store_id:
        return jsonify({"error": "Source and destination store cannot be identical"}), 400

    try:
        transfer = InventoryService.create_transfer(
            source_store_id=source_store_id,
            destination_store_id=destination_store_id,
            items=items,
            user_id=user_id,
            notes=notes
        )
        db.session.commit()
        return jsonify({"message": "Transfer requested", "transfer": transfer.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@inventory_bp.route('/transfers/<transfer_id>/dispatch', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def dispatch_transfer(transfer_id):
    """Dispatch stock transfer from source warehouse/store."""
    user_id = get_jwt_identity()
    try:
        transfer = InventoryService.dispatch_transfer(transfer_id, user_id)
        db.session.commit()
        return jsonify({"message": "Transfer dispatched in transit", "transfer": transfer.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@inventory_bp.route('/transfers/<transfer_id>/receive', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def receive_transfer(transfer_id):
    """Receive dispatched stock into destination store."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    received_items = data.get('items')

    try:
        transfer = InventoryService.receive_transfer(transfer_id, user_id, received_items)
        db.session.commit()
        return jsonify({"message": "Transfer received and inventory updated", "transfer": transfer.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
