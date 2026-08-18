import base64
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.tenant import Store, UserRole
from app.models.sales import Order
from app.models.hardware import StoreHardwareConfig
from app.services.escpos_service import ESCPOSBuilder
from app.services.fiscal_service import FiscalService
from app.utils.auth_guards import role_required, get_current_tenant_id, active_license_required

hardware_bp = Blueprint('hardware', __name__, url_prefix='/api/v1/hardware')

@hardware_bp.route('/config', methods=['GET'])
@jwt_required()
@active_license_required
def get_hardware_config():
    """Get POS hardware and peripheral settings."""
    store_id = get_current_tenant_id()
    config = StoreHardwareConfig.query.filter_by(store_id=store_id).first()
    if not config:
        config = StoreHardwareConfig(store_id=store_id)
        db.session.add(config)
        db.session.commit()
    return jsonify({"hardware_config": config.to_dict()}), 200

@hardware_bp.route('/config', methods=['PUT'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN)
def update_hardware_config():
    """Update hardware peripheral settings."""
    store_id = get_current_tenant_id()
    config = StoreHardwareConfig.query.filter_by(store_id=store_id).first()
    if not config:
        config = StoreHardwareConfig(store_id=store_id)
        db.session.add(config)

    data = request.get_json() or {}
    if 'printer_interface' in data:
        config.printer_interface = data['printer_interface']
    if 'printer_address' in data:
        config.printer_address = data['printer_address']
    if 'cash_drawer_pin' in data:
        config.cash_drawer_pin = int(data['cash_drawer_pin'])
    if 'enable_scale_reader' in data:
        config.enable_scale_reader = bool(data['enable_scale_reader'])
    if 'scale_port' in data:
        config.scale_port = data['scale_port']
    if 'scale_baud_rate' in data:
        config.scale_baud_rate = int(data['scale_baud_rate'])
    if 'enable_cfd' in data:
        config.enable_cfd = bool(data['enable_cfd'])
    if 'fiscal_device_url' in data:
        config.fiscal_device_url = data['fiscal_device_url']

    db.session.commit()
    return jsonify({"message": "Hardware configuration updated", "hardware_config": config.to_dict()}), 200

@hardware_bp.route('/receipt/<order_id>', methods=['GET'])
@jwt_required()
@active_license_required
def get_order_receipt_bytes(order_id):
    """Generate raw ESC/POS binary receipt commands for thermal printing."""
    store_id = get_current_tenant_id()
    order = Order.query.filter_by(id=order_id, store_id=store_id).first()
    if not order:
        return jsonify({"error": "Order not found"}), 404

    store = Store.query.get(store_id)
    receipt_bytes = ESCPOSBuilder.build_receipt_bytes(order, store)
    receipt_b64 = base64.b64encode(receipt_bytes).decode('utf-8')

    fmt = request.args.get('format', 'json')
    if fmt == 'raw':
        return Response(receipt_bytes, mimetype='application/octet-stream')

    return jsonify({
        "order_number": order.order_number,
        "receipt_b64": receipt_b64,
        "byte_length": len(receipt_bytes)
    }), 200

@hardware_bp.route('/open-drawer', methods=['POST'])
@jwt_required()
@active_license_required
def get_drawer_kick_command():
    """Return raw ESC/POS pulse byte sequence to pop open the cash drawer."""
    store_id = get_current_tenant_id()
    config = StoreHardwareConfig.query.filter_by(store_id=store_id).first()
    pin = config.cash_drawer_pin if config else 2
    cmd_bytes = ESCPOSBuilder.DRAWER_KICK_PIN2 if pin == 2 else ESCPOSBuilder.DRAWER_KICK_PIN5

    return jsonify({
        "message": f"Drawer kick command for Pin {pin}",
        "command_b64": base64.b64encode(cmd_bytes).decode('utf-8')
    }), 200

@hardware_bp.route('/fiscal-sign/<order_id>', methods=['POST'])
@jwt_required()
@active_license_required
def fiscal_sign_order(order_id):
    """Generate eTIMS/ESD compliant fiscal signature for receipt."""
    store_id = get_current_tenant_id()
    order = Order.query.filter_by(id=order_id, store_id=store_id).first()
    if not order:
        return jsonify({"error": "Order not found"}), 404

    store = Store.query.get(store_id)
    fiscal_info = FiscalService.sign_order_receipt(order, store)
    db.session.commit()

    return jsonify({
        "message": "Order fiscalized successfully",
        "fiscal": fiscal_info,
        "order": order.to_dict()
    }), 200
