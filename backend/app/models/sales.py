from app.extensions import db
from app.models.base import GUID, CrossJSON, generate_uuid, utc_now

class OrderStatus:
    DRAFT = 'DRAFT'
    HELD = 'HELD'
    PENDING_PAYMENT = 'PENDING_PAYMENT'
    PAID = 'PAID'
    PREPARING = 'PREPARING'
    COMPLETED = 'COMPLETED'
    VOIDED = 'VOIDED'
    REFUNDED = 'REFUNDED'
    ALL = [DRAFT, HELD, PENDING_PAYMENT, PAID, PREPARING, COMPLETED, VOIDED, REFUNDED]

class PaymentMethod:
    CASH = 'CASH'
    CARD = 'CARD'
    MOBILE_MONEY = 'MOBILE_MONEY' # e.g. M-Pesa
    CREDIT_ACCOUNT = 'CREDIT_ACCOUNT'
    SPLIT = 'SPLIT'
    ALL = [CASH, CARD, MOBILE_MONEY, CREDIT_ACCOUNT, SPLIT]

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(GUID, db.ForeignKey('users.id'), nullable=False) # Cashier / Waiter
    shift_id = db.Column(GUID, db.ForeignKey('cash_shifts.id'), nullable=True)
    
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    order_type = db.Column(db.String(50), default='RETAIL_QUICK', nullable=False) # RETAIL_QUICK, DINE_IN, TAKEAWAY, DELIVERY
    table_number = db.Column(db.String(50), nullable=True) # F&B table mapping
    guest_count = db.Column(db.Integer, default=1, nullable=False)
    
    customer_name = db.Column(db.String(255), nullable=True)
    customer_phone = db.Column(db.String(50), nullable=True)
    
    status = db.Column(db.String(50), default=OrderStatus.PENDING_PAYMENT, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    grand_total = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    
    fiscal_receipt_number = db.Column(db.String(100), nullable=True)
    fiscal_signature = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    cashier = db.relationship('User', foreign_keys=[user_id])
    store = db.relationship('Store')
    items = db.relationship('OrderItem', back_populates='order', cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='order', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'order_number': self.order_number,
            'store_id': str(self.store_id),
            'user_id': str(self.user_id),
            'cashier_name': self.cashier.full_name if self.cashier else None,
            'shift_id': str(self.shift_id) if self.shift_id else None,
            'order_type': self.order_type,
            'table_number': self.table_number,
            'guest_count': self.guest_count,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'status': self.status,
            'subtotal': float(self.subtotal),
            'tax_amount': float(self.tax_amount),
            'discount_amount': float(self.discount_amount),
            'grand_total': float(self.grand_total),
            'fiscal_receipt_number': self.fiscal_receipt_number,
            'fiscal_signature': self.fiscal_signature,
            'notes': self.notes,
            'items': [item.to_dict() for item in self.items],
            'payments': [p.to_dict() for p in self.payments],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    order_id = db.Column(GUID, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(GUID, db.ForeignKey('items.id'), nullable=False)
    
    item_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1.0)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    tax_rate = db.Column(db.Numeric(5, 2), default=0.00, nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Modifiers: JSON array e.g. [{"name": "Extra Shot", "price": 0.50}, {"name": "Oat Milk", "price": 0.75}]
    modifiers = db.Column(CrossJSON, default=list, nullable=False)
    kds_status = db.Column(db.String(50), default='PENDING', nullable=False) # PENDING, PREPARING, READY, SERVED
    kds_station = db.Column(db.String(50), default='KITCHEN', nullable=False) # GRILL, BAR, PIZZA, KITCHEN
    notes = db.Column(db.String(255), nullable=True)

    order = db.relationship('Order', back_populates='items')
    item = db.relationship('Item')

    def to_dict(self):
        return {
            'id': str(self.id),
            'order_id': str(self.order_id),
            'item_id': str(self.item_id),
            'item_name': self.item_name,
            'quantity': float(self.quantity),
            'unit_price': float(self.unit_price),
            'tax_rate': float(self.tax_rate),
            'tax_amount': float(self.tax_amount),
            'discount_amount': float(self.discount_amount),
            'subtotal': float(self.subtotal),
            'modifiers': self.modifiers or [],
            'kds_status': self.kds_status,
            'kds_station': self.kds_station,
            'notes': self.notes,
        }

class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    order_id = db.Column(GUID, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    
    payment_method = db.Column(db.String(50), default=PaymentMethod.CASH, nullable=False) # CASH, CARD, MOBILE_MONEY
    amount_tendered = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    change_returned = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    transaction_reference = db.Column(db.String(100), nullable=True) # e.g. M-Pesa receipt # or Card Approval Code
    status = db.Column(db.String(50), default='SUCCESS', nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    order = db.relationship('Order', back_populates='payments')
    cashier = db.relationship('User')

    def to_dict(self):
        return {
            'id': str(self.id),
            'order_id': str(self.order_id),
            'payment_method': self.payment_method,
            'amount_tendered': float(self.amount_tendered),
            'amount_paid': float(self.amount_paid),
            'change_returned': float(self.change_returned),
            'transaction_reference': self.transaction_reference,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
