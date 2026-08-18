from decimal import Decimal
import time, random
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.tenant import UserRole
from app.models.procurement import Supplier, PurchaseOrder, PurchaseOrderItem, GoodsReceivedNote, GRNItem, POStatus
from app.services.inventory_service import InventoryService
from app.utils.auth_guards import role_required, get_current_tenant_id, active_license_required

procurement_bp = Blueprint('procurement', __name__, url_prefix='/api/v1/procurement')

@procurement_bp.route('/suppliers', methods=['GET'])
@jwt_required()
@active_license_required
def list_suppliers():
    store_id = get_current_tenant_id()
    suppliers = Supplier.query.filter_by(store_id=store_id).order_by(Supplier.name).all()
    return jsonify({"suppliers": [s.to_dict() for s in suppliers]}), 200

@procurement_bp.route('/suppliers', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN)
def create_supplier():
    store_id = get_current_tenant_id()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Supplier name is required"}), 400

    supplier = Supplier(
        store_id=store_id,
        name=name,
        contact_name=data.get('contact_name'),
        email=data.get('email'),
        phone=data.get('phone'),
        address=data.get('address'),
        tax_pin=data.get('tax_pin'),
        payment_terms_days=int(data.get('payment_terms_days', 30))
    )
    db.session.add(supplier)
    db.session.commit()
    return jsonify({"message": "Supplier created", "supplier": supplier.to_dict()}), 201

@procurement_bp.route('/orders', methods=['GET'])
@jwt_required()
@active_license_required
def list_purchase_orders():
    store_id = get_current_tenant_id()
    orders = PurchaseOrder.query.filter_by(store_id=store_id).order_by(PurchaseOrder.created_at.desc()).all()
    return jsonify({"orders": [o.to_dict() for o in orders]}), 200

@procurement_bp.route('/orders', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def create_purchase_order():
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    supplier_id = data.get('supplier_id')
    items_data = data.get('items', [])
    if not supplier_id or not items_data:
        return jsonify({"error": "supplier_id and items are required"}), 400

    po_number = f"PO-{int(time.time())}-{random.randint(100, 999)}"
    total_amount = Decimal("0.00")

    po = PurchaseOrder(
        store_id=store_id,
        supplier_id=supplier_id,
        po_number=po_number,
        status=POStatus.SUBMITTED,
        expected_delivery_date=data.get('expected_delivery_date'),
        notes=data.get('notes'),
        created_by=user_id
    )
    db.session.add(po)
    db.session.flush()

    for item_in in items_data:
        qty = Decimal(str(item_in['quantity']))
        unit_cost = Decimal(str(item_in['unit_cost']))
        total_cost = qty * unit_cost
        total_amount += total_cost

        po_item = PurchaseOrderItem(
            purchase_order_id=po.id,
            item_id=item_in['item_id'],
            quantity_ordered=qty,
            unit_cost=unit_cost,
            total_cost=total_cost
        )
        db.session.add(po_item)

    po.total_amount = total_amount
    db.session.commit()
    return jsonify({"message": "Purchase order created", "order": po.to_dict()}), 201

@procurement_bp.route('/grn', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def create_grn():
    """Receive Goods Received Note (GRN): updates physical stock and supplier balances."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    supplier_id = data.get('supplier_id')
    po_id = data.get('purchase_order_id')
    items_data = data.get('items', [])

    if not supplier_id or not items_data:
        return jsonify({"error": "supplier_id and items are required"}), 400

    grn_number = f"GRN-{int(time.time())}-{random.randint(100, 999)}"
    total_val = Decimal("0.00")

    grn = GoodsReceivedNote(
        store_id=store_id,
        supplier_id=supplier_id,
        purchase_order_id=po_id,
        grn_number=grn_number,
        supplier_invoice_number=data.get('supplier_invoice_number'),
        notes=data.get('notes'),
        received_by=user_id
    )
    db.session.add(grn)
    db.session.flush()

    for item_in in items_data:
        qty = Decimal(str(item_in['quantity_received']))
        cost = Decimal(str(item_in['unit_cost']))
        total_val += (qty * cost)

        grn_item = GRNItem(
            grn_id=grn.id,
            item_id=item_in['item_id'],
            quantity_received=qty,
            unit_cost=cost,
            batch_number=item_in.get('batch_number', 'DEFAULT')
        )
        db.session.add(grn_item)

        # Increment physical stock in inventory
        InventoryService.adjust_stock(
            store_id=store_id,
            item_id=item_in['item_id'],
            quantity_delta=float(qty),
            reason=f"GRN_RECEIPT:{grn_number}",
            user_id=user_id,
            batch_number=item_in.get('batch_number', 'DEFAULT'),
            notes=f"Received via GRN {grn_number}"
        )

    grn.total_value = total_val

    # Update supplier accounts payable balance
    supplier = Supplier.query.get(supplier_id)
    if supplier:
        supplier.current_balance = Decimal(str(supplier.current_balance)) + total_val

    # If linked to PO, update PO status
    if po_id:
        po = PurchaseOrder.query.get(po_id)
        if po:
            po.status = POStatus.COMPLETED

    db.session.commit()
    return jsonify({"message": f"GRN {grn_number} processed. Stock updated.", "grn": grn.to_dict()}), 201
