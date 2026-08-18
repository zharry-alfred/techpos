from app.extensions import db
from app.models.base import GUID, CrossJSON, generate_uuid, utc_now

class SyncActionType:
    CREATE = 'CREATE'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    ALL = [CREATE, UPDATE, DELETE]

class SyncStatus:
    PENDING = 'PENDING'
    SYNCED = 'SYNCED'
    FAILED = 'FAILED'
    ALL = [PENDING, SYNCED, FAILED]

class OfflineSyncQueue(db.Model):
    __tablename__ = 'offline_sync_queue'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=True)
    entity_name = db.Column(db.String(100), nullable=False) # e.g. 'orders', 'shifts', 'inventory_adjustments'
    entity_id = db.Column(db.String(36), nullable=True) # local client ID
    payload = db.Column(CrossJSON, nullable=False)
    action_type = db.Column(db.String(20), default=SyncActionType.CREATE, nullable=False)
    status = db.Column(db.String(20), default=SyncStatus.PENDING, nullable=False)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    synced_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id) if self.store_id else None,
            'entity_name': self.entity_name,
            'entity_id': self.entity_id,
            'payload': self.payload,
            'action_type': self.action_type,
            'status': self.status,
            'retry_count': self.retry_count,
            'error_message': self.error_message,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
