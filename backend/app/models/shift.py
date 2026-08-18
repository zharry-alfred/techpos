from app.extensions import db
from app.models.base import GUID, CrossJSON, generate_uuid, utc_now

class ShiftStatus:
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'

class CashShift(db.Model):
    """Drawer float tracking and cash reconciliation at shift open/close."""
    __tablename__ = 'cash_shifts'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    terminal_id = db.Column(db.String(50), default='POS-01', nullable=False)
    status = db.Column(db.String(20), default=ShiftStatus.OPEN, nullable=False)
    
    opening_float = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    expected_cash = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    closing_cash_actual = db.Column(db.Numeric(12, 2), nullable=True)
    discrepancy = db.Column(db.Numeric(12, 2), default=0.00, nullable=False) # positive = overage, negative = shortage
    
    total_cash_sales = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    total_card_sales = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    total_mobile_sales = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    total_drops = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    total_payouts = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    
    x_report_json = db.Column(CrossJSON, default=dict, nullable=False) # Interim snapshot
    z_report_json = db.Column(CrossJSON, default=dict, nullable=False) # Final closing report
    closing_notes = db.Column(db.Text, nullable=True)
    
    opened_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    cashier = db.relationship('User', foreign_keys=[user_id])
    movements = db.relationship('CashMovement', back_populates='shift', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'user_id': str(self.user_id),
            'cashier_name': self.cashier.full_name if self.cashier else None,
            'terminal_id': self.terminal_id,
            'status': self.status,
            'opening_float': float(self.opening_float),
            'expected_cash': float(self.expected_cash),
            'closing_cash_actual': float(self.closing_cash_actual) if self.closing_cash_actual is not None else None,
            'discrepancy': float(self.discrepancy),
            'total_cash_sales': float(self.total_cash_sales),
            'total_card_sales': float(self.total_card_sales),
            'total_mobile_sales': float(self.total_mobile_sales),
            'total_drops': float(self.total_drops),
            'total_payouts': float(self.total_payouts),
            'x_report': self.x_report_json or {},
            'z_report': self.z_report_json or {},
            'closing_notes': self.closing_notes,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
        }

class CashMovement(db.Model):
    __tablename__ = 'cash_movements'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    shift_id = db.Column(GUID, db.ForeignKey('cash_shifts.id', ondelete='CASCADE'), nullable=False)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(GUID, db.ForeignKey('users.id'), nullable=False)
    
    movement_type = db.Column(db.String(50), nullable=False) # CASH_DROP, PAYOUT, FLOAT_ADD, PETTY_CASH
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    shift = db.relationship('CashShift', back_populates='movements')
    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': str(self.id),
            'shift_id': str(self.shift_id),
            'movement_type': self.movement_type,
            'amount': float(self.amount),
            'reason': self.reason,
            'notes': self.notes,
            'cashier_name': self.user.full_name if self.user else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
