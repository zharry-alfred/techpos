from app.extensions import db
from app.models.base import GUID, generate_uuid, utc_now

class TransferStatus:
    REQUESTED = 'REQUESTED'
    IN_TRANSIT = 'IN_TRANSIT'
    RECEIVED = 'RECEIVED'
    CANCELLED = 'CANCELLED'
    ALL = [REQUESTED, IN_TRANSIT, RECEIVED, CANCELLED]

class StockLevel(db.Model):
    __tablename__ = 'stock_levels'
    __table_args__ = (
        db.UniqueConstraint('store_id', 'item_id', 'batch_number', name='uq_store_item_batch'),
    )

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    current_stock = db.Column(db.Numeric(12, 4), default=0.00, nullable=False)
    low_stock_threshold = db.Column(db.Numeric(12, 4), default=5.00, nullable=False)
    batch_number = db.Column(db.String(100), default='DEFAULT', nullable=False)
    expiry_date = db.Column(db.DateTime(timezone=True), nullable=True)
    location_bin = db.Column(db.String(100), nullable=True) # Warehouse aisle/bin
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    item = db.relationship('Item', back_populates='stock_levels')
    store = db.relationship('Store')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'item_id': str(self.item_id),
            'item_name': self.item.name if self.item else None,
            'current_stock': float(self.current_stock),
            'low_stock_threshold': float(self.low_stock_threshold),
            'batch_number': self.batch_number,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'location_bin': self.location_bin,
            'is_low_stock': float(self.current_stock) <= float(self.low_stock_threshold),
        }

class StockTransfer(db.Model):
    __tablename__ = 'stock_transfers'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    source_store_id = db.Column(GUID, db.ForeignKey('stores.id'), nullable=False)
    destination_store_id = db.Column(GUID, db.ForeignKey('stores.id'), nullable=False)
    status = db.Column(db.String(50), default=TransferStatus.REQUESTED, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    transfer_number = db.Column(db.String(50), unique=True, nullable=False)
    
    created_by = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    received_by = db.Column(GUID, db.ForeignKey('users.id'), nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    dispatched_at = db.Column(db.DateTime(timezone=True), nullable=True)
    received_at = db.Column(db.DateTime(timezone=True), nullable=True)

    source_store = db.relationship('Store', foreign_keys=[source_store_id])
    destination_store = db.relationship('Store', foreign_keys=[destination_store_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    receiver = db.relationship('User', foreign_keys=[received_by])
    items = db.relationship('StockTransferItem', back_populates='transfer', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'transfer_number': self.transfer_number,
            'source_store_id': str(self.source_store_id),
            'source_store_name': self.source_store.name if self.source_store else None,
            'destination_store_id': str(self.destination_store_id),
            'destination_store_name': self.destination_store.name if self.destination_store else None,
            'status': self.status,
            'notes': self.notes,
            'created_by': self.creator.full_name if self.creator else None,
            'received_by': self.receiver.full_name if self.receiver else None,
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'dispatched_at': self.dispatched_at.isoformat() if self.dispatched_at else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
        }

class StockTransferItem(db.Model):
    __tablename__ = 'stock_transfer_items'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    transfer_id = db.Column(GUID, db.ForeignKey('stock_transfers.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Numeric(12, 4), nullable=False)
    received_quantity = db.Column(db.Numeric(12, 4), default=0.00, nullable=False)

    transfer = db.relationship('StockTransfer', back_populates='items')
    item = db.relationship('Item')

    def to_dict(self):
        return {
            'id': str(self.id),
            'transfer_id': str(self.transfer_id),
            'item_id': str(self.item_id),
            'item_name': self.item.name if self.item else None,
            'sku': self.item.sku if self.item else None,
            'quantity': float(self.quantity),
            'received_quantity': float(self.received_quantity),
        }

class StockAdjustmentLog(db.Model):
    __tablename__ = 'stock_adjustment_logs'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    
    quantity_delta = db.Column(db.Numeric(12, 4), nullable=False) # e.g. +10 or -3
    resulting_stock = db.Column(db.Numeric(12, 4), nullable=False)
    reason = db.Column(db.String(100), nullable=False) # DAMAGE, SPOILAGE, PHYSICAL_COUNT_RECONCILIATION, RETURN, MANUAL_RECEIPT
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    item = db.relationship('Item')
    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'item_id': str(self.item_id),
            'item_name': self.item.name if self.item else None,
            'user_name': self.user.full_name if self.user else None,
            'quantity_delta': float(self.quantity_delta),
            'resulting_stock': float(self.resulting_stock),
            'reason': self.reason,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
