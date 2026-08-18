from decimal import Decimal
import time, random
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.document import CommercialDocument, DocumentType
from app.models.sales import Order
from app.utils.auth_guards import get_current_tenant_id, active_license_required

document_bp = Blueprint('documents', __name__, url_prefix='/api/v1/documents')

@document_bp.route('', methods=['POST'])
@jwt_required()
@active_license_required
def create_document():
    """Create Pro-forma, formal Quote, Tax Invoice, or Goods Issued Note (GIN)."""
    store_id = get_current_tenant_id()
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    doc_type = data.get('doc_type', DocumentType.TAX_INVOICE)
    if doc_type not in DocumentType.ALL:
        return jsonify({"error": f"Invalid doc_type. Must be one of: {DocumentType.ALL}"}), 400

    prefix = "INV" if doc_type == DocumentType.TAX_INVOICE else ("QUO" if doc_type == DocumentType.FORMAL_QUOTE else ("GIN" if doc_type == DocumentType.GOODS_ISSUED_NOTE else "DOC"))
    doc_number = f"{prefix}-{int(time.time())}-{random.randint(100, 999)}"

    items_data = data.get('items', [])
    subtotal = Decimal(str(data.get('subtotal', 0.00)))
    tax_amount = Decimal(str(data.get('tax_amount', 0.00)))
    discount_amount = Decimal(str(data.get('discount_amount', 0.00)))
    total_amount = (subtotal + tax_amount) - discount_amount

    doc = CommercialDocument(
        store_id=store_id,
        created_by=user_id,
        doc_type=doc_type,
        doc_number=doc_number,
        order_id=data.get('order_id'),
        customer_name=data.get('customer_name', 'Walk-in Customer'),
        customer_email=data.get('customer_email'),
        customer_phone=data.get('customer_phone'),
        customer_address=data.get('customer_address'),
        customer_tax_pin=data.get('customer_tax_pin'),
        vehicle_registration=data.get('vehicle_registration'),
        driver_name=data.get('driver_name'),
        delivery_destination=data.get('delivery_destination'),
        subtotal=subtotal,
        tax_amount=tax_amount,
        discount_amount=discount_amount,
        total_amount=total_amount,
        items_data=items_data,
        terms_and_conditions=data.get('terms_and_conditions'),
        notes=data.get('notes')
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({
        "message": f"Document {doc.doc_number} ({doc.doc_type}) created successfully",
        "document": doc.to_dict()
    }), 201

@document_bp.route('/<doc_id>', methods=['GET'])
@jwt_required()
@active_license_required
def get_document(doc_id):
    """Retrieve commercial document."""
    store_id = get_current_tenant_id()
    doc = CommercialDocument.query.filter_by(id=doc_id, store_id=store_id).first()
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({"document": doc.to_dict()}), 200

@document_bp.route('', methods=['GET'])
@jwt_required()
@active_license_required
def list_documents():
    """List commercial documents with filtering."""
    store_id = get_current_tenant_id()
    query = CommercialDocument.query.filter_by(store_id=store_id)

    doc_type = request.args.get('doc_type')
    if doc_type:
        query = query.filter_by(doc_type=doc_type)

    docs = query.order_by(CommercialDocument.created_at.desc()).limit(100).all()
    return jsonify({"documents": [d.to_dict() for d in docs]}), 200
