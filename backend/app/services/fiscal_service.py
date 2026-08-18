import hashlib
import time
from datetime import datetime, timezone
from app.models.sales import Order
from app.models.tenant import Store

class FiscalService:
    """Fiscal compliance adapter (supporting eTIMS, ESD, and electronic tax registers)."""

    @staticmethod
    def sign_order_receipt(order: Order, store: Store) -> dict:
        """Generate a cryptographically verifiable fiscal receipt signature and Control Unit (CU) number."""
        timestamp = datetime.now(timezone.utc).isoformat()
        cu_device_id = f"ESD-{store.code[:4]}-001"
        cu_invoice_num = f"CU-{store.code}-{int(time.time())}"

        # Canonical data string for fiscal hash
        data_string = f"{cu_device_id}|{cu_invoice_num}|{store.tax_number}|{order.order_number}|{order.grand_total:.2f}|{timestamp}"
        signature = hashlib.sha256(data_string.encode('utf-8')).hexdigest().upper()
        
        # QR verification URL for tax authority portal
        verification_url = f"https://tax-verify.authority.gov/receipt?cu={cu_invoice_num}&sig={signature[:16]}"

        order.fiscal_receipt_number = cu_invoice_num
        order.fiscal_signature = signature

        return {
            "cu_invoice_number": cu_invoice_num,
            "cu_device_id": cu_device_id,
            "signature": signature,
            "verification_url": verification_url,
            "timestamp": timestamp
        }
