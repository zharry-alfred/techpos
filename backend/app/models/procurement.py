from app.extensions import db
from app.models.base import GUID, generate_uuid, utc_now

class POStatus:
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    PARTIALLY_RECEIVED = 'PARTIALLY_RECEIVED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'

class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    contact_name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    tax_pin = db.Column(db.String(100), nullable=True)
    payment_terms_days = db.Column(db.Integer, default=30, nullable=False)
    current_balance = db.Column(db.Numeric(12, 2), default=0.00, nullable=False) # Accounts Payable
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    purchase_orders = db.relationship('PurchaseOrder', back_populates='supplier')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'name': self.name,
            'contact_name': self.contact_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'tax_pin': self.tax_pin,
            'payment_terms_days': self.payment_terms_days,
            'current_balance': float(self.current_balance),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    supplier_id = db.Column(GUID, db.ForeignKey('suppliers.id', ondelete='RESTRICT'), nullable=False)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(50), default=POStatus.DRAFT, nullable=False)
    expected_delivery_date = db.Column(db.DateTime(timezone=True), nullable=True)
    total_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    created_by = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    supplier = db.relationship('Supplier', back_populates='purchase_orders')
    creator = db.relationship('User')
    items = db.relationship('PurchaseOrderItem', back_populates='purchase_order', cascade='all, delete-orphan')
    grns = db.relationship('GoodsReceivedNote', back_populates='purchase_order')

    def to_dict(self):
        return {
            'id': str(self.id),
            'po_number': self.po_number,
            'store_id': str(self.store_id),
            'supplier_id': str(self.supplier_id),
            'supplier_name': self.supplier.name if self.supplier else None,
            'status': self.status,
            'expected_delivery_date': self.expected_delivery_date.isoformat() if self.expected_delivery_date else None,
            'total_amount': float(self.total_amount),
            'notes': self.notes,
            'created_by': self.creator.full_name if self.creator else None,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    purchase_order_id = db.Column(GUID, db.ForeignKey('purchase_orders.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    quantity_ordered = db.Column(db.Numeric(12, 4), nullable=False)
    quantity_received = db.Column(db.Numeric(12, 4), default=0.00, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False)

    purchase_order = db.relationship('PurchaseOrder', back_populates='items')
    item = db.relationship('Item')

    def to_dict(self):
        return {
            'id': str(self.id),
            'item_id': str(self.item_id),
            'item_name': self.item.name if self.item else None,
            'sku': self.item.sku if self.item else None,
            'quantity_ordered': float(self.quantity_ordered),
            'quantity_received': float(self.quantity_received),
            'unit_cost': float(self.unit_cost),
            'total_cost': float(self.total_cost),
        }

class GoodsReceivedNote(db.Model):
    """GRN representing physical stock delivery verification and entry."""
    __tablename__ = 'goods_received_notes'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    supplier_id = db.Column(GUID, db.ForeignKey('suppliers.id', ondelete='RESTRICT'), nullable=False)
    purchase_order_id = db.Column(GUID, db.ForeignKey('purchase_orders.id', ondelete='SET NULL'), nullable=True)
    grn_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_invoice_number = db.Column(db.String(100), nullable=True)
    total_value = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    received_by = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    received_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    supplier = db.relationship('Supplier')
    purchase_order = db.relationship('PurchaseOrder', back_populates='grns')
    receiver = db.relationship('User')
    items = db.relationship('GRNItem', back_populates='grn', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'grn_number': self.grn_number,
            'store_id': str(self.store_id),
            'supplier_id': str(self.supplier_id),
            'supplier_name': self.supplier.name if self.supplier else None,
            'purchase_order_id': str(self.purchase_order_id) if self.purchase_order_id else None,
            'supplier_invoice_number': self.supplier_invoice_number,
            'total_value': float(self.total_value),
            'received_by': self.receiver.full_name if self.receiver else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'items': [i.to_dict() for i in self.items]
        }

class GRNItem(db.Model):
    __tablename__ = 'grn_items'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    grn_id = db.Column(GUID, db.ForeignKey('goods_received_notes.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    quantity_received = db.Column(db.Numeric(12, 4), nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    batch_number = db.Column(db.String(100), default='DEFAULT', nullable=False)
    expiry_date = db.Column(db.DateTime(timezone=True), nullable=True)

    grn = db.relationship('GoodsReceivedNote', back_populates='items')
    item = db.relationship('Item')

    def to_dict(self):
        return {
            'id': str(self.id),
            'item_id': str(self.item_id),
            'item_name': self.item.name if self.item else None,
            'quantity_received': float(self.quantity_received),
            'unit_cost': float(self.unit_cost),
            'batch_number': self.batch_number,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
        }
