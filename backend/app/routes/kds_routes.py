from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.sales import Order, OrderItem, OrderStatus
from app.utils.auth_guards import get_current_tenant_id, active_license_required

kds_bp = Blueprint('kds', __name__, url_prefix='/api/v1/kds')

@kds_bp.route('/tickets', methods=['GET'])
@jwt_required()
@active_license_required
def get_kds_tickets():
    """Retrieve active kitchen display tickets (Spec Section 4: /api/v1/kds/tickets)."""
    store_id = get_current_tenant_id()
    station = request.args.get('station') # Filter by station: GRILL, BAR, PIZZA, KITCHEN

    # Query active orders that are in preparation or pending kitchen
    active_orders = Order.query.filter(
        Order.store_id == store_id,
        Order.status.in_([OrderStatus.PENDING_PAYMENT, OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.COMPLETED])
    ).order_by(Order.created_at.asc()).limit(50).all()

    tickets = []
    for o in active_orders:
        order_items = []
        for item in o.items:
            if item.kds_status == 'SERVED':
                continue
            if station and item.kds_station != station:
                continue

            order_items.append({
                "item_id": str(item.id),
                "name": item.item_name,
                "quantity": float(item.quantity),
                "station": item.kds_station,
                "status": item.kds_status,
                "modifiers": item.modifiers,
                "notes": item.notes
            })

        if order_items:
            tickets.append({
                "order_id": str(o.id),
                "order_number": o.order_number,
                "order_type": o.order_type,
                "table_number": o.table_number,
                "customer_name": o.customer_name,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "items": order_items
            })

    return jsonify({"tickets": tickets, "count": len(tickets)}), 200

@kds_bp.route('/tickets/<item_id>/bump', methods=['PUT'])
@jwt_required()
@active_license_required
def bump_ticket_item(item_id):
    """Kitchen Staff: Bump an item status (PENDING -> PREPARING -> READY -> SERVED)."""
    data = request.get_json() or {}
    new_status = data.get('status') # PREPARING, READY, SERVED

    item = OrderItem.query.get(item_id)
    if not item:
        return jsonify({"error": "Ticket item not found"}), 404

    if not new_status:
        # Auto-advance
        if item.kds_status == 'PENDING':
            item.kds_status = 'PREPARING'
        elif item.kds_status == 'PREPARING':
            item.kds_status = 'READY'
        elif item.kds_status == 'READY':
            item.kds_status = 'SERVED'
    else:
        item.kds_status = new_status

    db.session.commit()
    return jsonify({
        "message": f"Item '{item.item_name}' updated to {item.kds_status}",
        "item_id": str(item.id),
        "status": item.kds_status
    }), 200
