from app.extensions import db
from app.models.base import GUID, CrossJSON, generate_uuid, utc_now

class DocumentType:
    PRO_FORMA = 'PRO_FORMA'
    FORMAL_QUOTE = 'FORMAL_QUOTE'
    TAX_INVOICE = 'TAX_INVOICE'
    GOODS_ISSUED_NOTE = 'GOODS_ISSUED_NOTE' # GIN
    DELIVERY_NOTE = 'DELIVERY_NOTE'
    ALL = [PRO_FORMA, FORMAL_QUOTE, TAX_INVOICE, GOODS_ISSUED_NOTE, DELIVERY_NOTE]

class CommercialDocument(db.Model):
    """Pro-forma invoices, formal price quotes, tax invoices, and Goods Issued Notes (GIN)."""
    __tablename__ = 'commercial_documents'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    order_id = db.Column(GUID, db.ForeignKey('orders.id', ondelete='SET NULL'), nullable=True)
    created_by = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    
    doc_type = db.Column(db.String(50), default=DocumentType.TAX_INVOICE, nullable=False)
    doc_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(50), default='ISSUED', nullable=False)
    
    customer_name = db.Column(db.String(255), nullable=False)
    customer_email = db.Column(db.String(255), nullable=True)
    customer_phone = db.Column(db.String(50), nullable=True)
    customer_address = db.Column(db.Text, nullable=True)
    customer_tax_pin = db.Column(db.String(100), nullable=True)
    
    # Logistics / GIN details
    vehicle_registration = db.Column(db.String(50), nullable=True)
    driver_name = db.Column(db.String(100), nullable=True)
    delivery_destination = db.Column(db.Text, nullable=True)
    
    subtotal = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    
    items_data = db.Column(CrossJSON, default=list, nullable=False)
    terms_and_conditions = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    valid_until = db.Column(db.DateTime(timezone=True), nullable=True) # For quotes
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    creator = db.relationship('User')
    store = db.relationship('Store')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'doc_type': self.doc_type,
            'doc_number': self.doc_number,
            'order_id': str(self.order_id) if self.order_id else None,
            'customer_name': self.customer_name,
            'customer_email': self.customer_email,
            'customer_phone': self.customer_phone,
            'customer_address': self.customer_address,
            'customer_tax_pin': self.customer_tax_pin,
            'vehicle_registration': self.vehicle_registration,
            'driver_name': self.driver_name,
            'delivery_destination': self.delivery_destination,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount),
            'discount_amount': float(self.discount_amount),
            'total_amount': float(self.total_amount),
            'items': self.items_data or [],
            'terms_and_conditions': self.terms_and_conditions,
            'notes': self.notes,
            'created_by': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
