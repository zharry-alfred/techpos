from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.base import GUID, generate_uuid, utc_now

class BusinessType:
    RETAIL = 'RETAIL'
    FOOD_BEVERAGE = 'FOOD_BEVERAGE'
    SERVICE = 'SERVICE'
    WHOLESALE = 'WHOLESALE'
    ALL = [RETAIL, FOOD_BEVERAGE, SERVICE, WHOLESALE]

class UserRole:
    SUPER_ADMIN = 'SUPER_ADMIN'
    STORE_ADMIN = 'STORE_ADMIN'
    STORE_MANAGER = 'STORE_MANAGER'
    CASHIER = 'CASHIER'
    STAFF = 'STAFF'
    ALL = [SUPER_ADMIN, STORE_ADMIN, STORE_MANAGER, CASHIER, STAFF]

class Store(db.Model):
    __tablename__ = 'stores'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    business_type = db.Column(db.String(50), nullable=False, default=BusinessType.RETAIL)
    
    license_key = db.Column(db.Text, nullable=True)
    is_license_active = db.Column(db.Boolean, default=False, nullable=False)
    hardware_fingerprint = db.Column(db.String(255), nullable=True)
    license_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    currency_code = db.Column(db.String(10), default='USD', nullable=False)
    tax_number = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    receipt_header = db.Column(db.Text, nullable=True)
    receipt_footer = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    users = db.relationship('User', back_populates='store', cascade='all, delete-orphan')
    hardware_configs = db.relationship('StoreHardwareConfig', back_populates='store', uselist=False, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'code': self.code,
            'business_type': self.business_type,
            'is_license_active': self.is_license_active,
            'license_expires_at': self.license_expires_at.isoformat() if self.license_expires_at else None,
            'currency_code': self.currency_code,
            'tax_number': self.tax_number,
            'address': self.address,
            'phone': self.phone,
            'receipt_header': self.receipt_header,
            'receipt_footer': self.receipt_footer,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.UniqueConstraint('store_id', 'email', name='uq_store_user_email'),
    )

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default=UserRole.CASHIER)
    pin_code = db.Column(db.String(10), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    store = db.relationship('Store', back_populates='users')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def set_pin(self, pin: str):
        self.pin_code = generate_password_hash(pin) if pin else None

    def check_pin(self, pin: str) -> bool:
        if not self.pin_code:
            return False
        return check_password_hash(self.pin_code, pin)

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'has_pin': bool(self.pin_code),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
