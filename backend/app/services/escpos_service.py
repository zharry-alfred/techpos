import io
from app.models.sales import Order, PaymentMethod
from app.models.tenant import Store

class ESCPOSBuilder:
    """ESC/POS command generator for standard 80mm and 58mm thermal POS printers."""
    ESC = b'\x1b'
    GS = b'\x1d'
    
    # Initialize printer
    INIT = ESC + b'@'
    
    # Text Alignment
    ALIGN_LEFT = ESC + b'a\x00'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_RIGHT = ESC + b'a\x02'
    
    # Formatting
    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'
    DOUBLE_WIDTH_ON = ESC + b'!\x20'
    DOUBLE_HEIGHT_ON = ESC + b'!\x10'
    DOUBLE_SIZE_ON = ESC + b'!\x30'
    NORMAL_SIZE = ESC + b'!\x00'
    
    # Paper Cut
    FEED_AND_CUT = GS + b'V\x42\x00'
    
    # Cash Drawer Kick
    DRAWER_KICK_PIN2 = ESC + b'p\x00\x19\xfa'
    DRAWER_KICK_PIN5 = ESC + b'p\x01\x19\xfa'

    @classmethod
    def build_receipt_bytes(cls, order: Order, store: Store, width_chars: int = 42) -> bytes:
        """Generate raw ESC/POS bytes for a customer order receipt."""
        buf = io.BytesIO()

        # Initialize
        buf.write(cls.INIT)
        
        # 1. Header (Centered, Bold)
        buf.write(cls.ALIGN_CENTER)
        buf.write(cls.BOLD_ON + cls.DOUBLE_SIZE_ON)
        buf.write(f"{store.name}\n".encode('latin-1', 'replace'))
        buf.write(cls.NORMAL_SIZE + cls.BOLD_OFF)
        
        if store.address:
            buf.write(f"{store.address}\n".encode('latin-1', 'replace'))
        if store.phone:
            buf.write(f"Tel: {store.phone}\n".encode('latin-1', 'replace'))
        if store.tax_number:
            buf.write(f"PIN/VAT No: {store.tax_number}\n".encode('latin-1', 'replace'))

        buf.write(f"{'-' * width_chars}\n".encode('latin-1'))
        
        # 2. Receipt metadata
        buf.write(cls.ALIGN_LEFT)
        buf.write(f"Receipt #: {order.order_number}\n".encode('latin-1'))
        buf.write(f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n".encode('latin-1'))
        buf.write(f"Cashier: {order.cashier.full_name if order.cashier else 'Staff'}\n".encode('latin-1'))
        if order.table_number:
            buf.write(f"Table: {order.table_number} | Guests: {order.guest_count}\n".encode('latin-1'))
        if order.customer_name:
            buf.write(f"Customer: {order.customer_name}\n".encode('latin-1'))
            
        buf.write(f"{'=' * width_chars}\n".encode('latin-1'))

        # 3. Line Items Table
        # Format: Item Name (22 chars) | Qty (4) | Price (6) | Total (8)
        buf.write(cls.BOLD_ON)
        header_line = f"{'ITEM':<20} {'QTY':>4} {'PRICE':>7} {'TOTAL':>8}\n"
        buf.write(header_line.encode('latin-1'))
        buf.write(cls.BOLD_OFF)
        buf.write(f"{'-' * width_chars}\n".encode('latin-1'))

        for item in order.items:
            name = item.item_name[:20]
            qty_str = f"{item.quantity:.0f}"
            price_str = f"{item.unit_price:.2f}"
            tot_str = f"{item.subtotal:.2f}"
            
            line = f"{name:<20} {qty_str:>4} {price_str:>7} {tot_str:>8}\n"
            buf.write(line.encode('latin-1', 'replace'))

            # Print modifiers if any
            if item.modifiers:
                for mod in item.modifiers:
                    mod_line = f"  + {mod.get('name')} (+{mod.get('price', 0):.2f})\n"
                    buf.write(mod_line.encode('latin-1', 'replace'))

        buf.write(f"{'-' * width_chars}\n".encode('latin-1'))

        # 4. Totals (Right Aligned)
        buf.write(cls.ALIGN_RIGHT)
        buf.write(f"Subtotal:  {store.currency_code} {order.subtotal:.2f}\n".encode('latin-1'))
        if order.tax_amount > 0:
            buf.write(f"Tax/VAT:  {store.currency_code} {order.tax_amount:.2f}\n".encode('latin-1'))
        if order.discount_amount > 0:
            buf.write(f"Discount: -{store.currency_code} {order.discount_amount:.2f}\n".encode('latin-1'))
            
        buf.write(cls.BOLD_ON + cls.DOUBLE_HEIGHT_ON)
        buf.write(f"TOTAL: {store.currency_code} {order.grand_total:.2f}\n".encode('latin-1'))
        buf.write(cls.NORMAL_SIZE + cls.BOLD_OFF)
        buf.write(f"{'-' * width_chars}\n".encode('latin-1'))

        # 5. Payment Details
        buf.write(cls.ALIGN_LEFT)
        for p in order.payments:
            buf.write(f"Paid ({p.payment_method}): {store.currency_code} {p.amount_paid:.2f}".encode('latin-1'))
            if p.transaction_reference:
                buf.write(f" [Ref: {p.transaction_reference}]".encode('latin-1'))
            buf.write(b"\n")
            if p.change_returned > 0:
                buf.write(f"Change Returned: {store.currency_code} {p.change_returned:.2f}\n".encode('latin-1'))

        # 6. Fiscal Signature / QR code string if present
        if order.fiscal_receipt_number or order.fiscal_signature:
            buf.write(f"{'-' * width_chars}\n".encode('latin-1'))
            buf.write(cls.ALIGN_CENTER)
            buf.write(cls.BOLD_ON + b"FISCAL COMPLIANCE RECEIPT\n" + cls.BOLD_OFF)
            if order.fiscal_receipt_number:
                buf.write(f"CU Inv No: {order.fiscal_receipt_number}\n".encode('latin-1'))
            if order.fiscal_signature:
                buf.write(f"Signature: {order.fiscal_signature[:32]}...\n".encode('latin-1'))

        # 7. Footer
        buf.write(f"{'=' * width_chars}\n".encode('latin-1'))
        buf.write(cls.ALIGN_CENTER)
        if store.receipt_footer:
            buf.write(f"{store.receipt_footer}\n".encode('latin-1', 'replace'))
        else:
            buf.write(b"Thank you for your business!\n")

        # 8. Drawer kick & cut paper
        buf.write(cls.DRAWER_KICK_PIN2)
        buf.write(b"\n\n\n")
        buf.write(cls.FEED_AND_CUT)

        return buf.getvalue()
