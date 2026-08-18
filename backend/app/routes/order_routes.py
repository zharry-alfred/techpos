from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import db
from app.models.tenant import UserRole
from app.models.sales import Order, OrderStatus
from app.services.checkout_service import CheckoutService
from app.utils.auth_guards import role_required, get_current_tenant_id, active_license_required

order_bp = Blueprint('orders', __name__, url_prefix='/api/v1/orders')

@order_bp.route('', methods=['POST'])
@jwt_required()
@active_license_required
def create_order():
    """Create a new checkout order (Spec Section 4: /api/v1/orders)."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    claims = get_jwt()
    store_code = claims.get('store_code', 'STORE')
    data = request.get_json() or {}

    items = data.get('items', [])
    if not items:
        return jsonify({"error": "Order must contain at least one item"}), 400

    try:
        order = CheckoutService.create_order(
            store_id=store_id,
            user_id=user_id,
            store_code=store_code,
            items_data=items,
            order_type=data.get('order_type', 'RETAIL_QUICK'),
            table_number=data.get('table_number'),
            guest_count=int(data.get('guest_count', 1)),
            customer_name=data.get('customer_name'),
            customer_phone=data.get('customer_phone'),
            discount_amount=float(data.get('discount_amount', 0.00)),
            notes=data.get('notes'),
            status=data.get('status', OrderStatus.PENDING_PAYMENT)
        )
        db.session.commit()
        return jsonify({
            "message": "Order created successfully",
            "order": order.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@order_bp.route('/<order_id>/pay', methods=['POST'])
@jwt_required()
@active_license_required
def pay_order(order_id):
    """Process full or split payments (Spec Section 4: /api/v1/orders/<id>/pay)."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    payments = data.get('payments', []) # [{'method': 'CASH', 'amount': 25.00, 'amount_tendered': 30.00}]

    if not payments:
        # Fallback to single payment payload format
        method = data.get('payment_method', 'CASH')
        amount = data.get('amount')
        tendered = data.get('amount_tendered', amount)
        reference = data.get('transaction_reference')
        if amount is not None:
            payments = [{'method': method, 'amount': amount, 'amount_tendered': tendered, 'reference': reference}]

    if not payments:
        return jsonify({"error": "Payment details required"}), 400

    try:
        order = CheckoutService.process_payment(
            order_id=order_id,
            user_id=user_id,
            payments_data=payments
        )
        db.session.commit()
        return jsonify({
            "message": f"Payment processed successfully for order {order.order_number}",
            "order": order.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

@order_bp.route('', methods=['GET'])
@jwt_required()
@active_license_required
def list_orders():
    """List orders with filtering."""
    store_id = get_current_tenant_id()
    query = Order.query.filter_by(store_id=store_id)

    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)

    order_type = request.args.get('order_type')
    if order_type:
        query = query.filter_by(order_type=order_type)

    table_number = request.args.get('table_number')
    if table_number:
        query = query.filter_by(table_number=table_number)

    orders = query.order_by(Order.created_at.desc()).limit(100).all()
    return jsonify({"orders": [o.to_dict() for o in orders]}), 200

@order_bp.route('/<order_id>', methods=['GET'])
@jwt_required()
@active_license_required
def get_order(order_id):
    """Get single order details."""
    store_id = get_current_tenant_id()
    order = Order.query.filter_by(id=order_id, store_id=store_id).first()
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify({"order": order.to_dict()}), 200

@order_bp.route('/<order_id>/void', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def void_order(order_id):
    """Manager override: Void an order."""
    store_id = get_current_tenant_id()
    order = Order.query.filter_by(id=order_id, store_id=store_id).first()
    if not order:
        return jsonify({"error": "Order not found"}), 404

    order.status = OrderStatus.VOIDED
    db.session.commit()
    return jsonify({"message": f"Order {order.order_number} has been voided", "order": order.to_dict()}), 200
