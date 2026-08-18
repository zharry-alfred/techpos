from app.extensions import db
from app.models.base import GUID, generate_uuid, utc_now

class StoreHardwareConfig(db.Model):
    __tablename__ = 'store_hardware_configs'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    printer_interface = db.Column(db.String(50), default='USB', nullable=False) # USB, NETWORK, SERIAL, BLUETOOTH
    printer_address = db.Column(db.String(255), nullable=True) # e.g. 192.168.1.200:9100 or COM3
    cash_drawer_pin = db.Column(db.Integer, default=2, nullable=False) # Pin 2 or Pin 5
    enable_scale_reader = db.Column(db.Boolean, default=False, nullable=False)
    scale_port = db.Column(db.String(50), default='COM1', nullable=True)
    scale_baud_rate = db.Column(db.Integer, default=9600, nullable=True)
    enable_cfd = db.Column(db.Boolean, default=True, nullable=False)
    fiscal_device_url = db.Column(db.String(255), nullable=True) # eTIMS / ESD fiscal device endpoint
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    store = db.relationship('Store', back_populates='hardware_configs')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'printer_interface': self.printer_interface,
            'printer_address': self.printer_address,
            'cash_drawer_pin': self.cash_drawer_pin,
            'enable_scale_reader': self.enable_scale_reader,
            'scale_port': self.scale_port,
            'scale_baud_rate': self.scale_baud_rate,
            'enable_cfd': self.enable_cfd,
            'fiscal_device_url': self.fiscal_device_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
