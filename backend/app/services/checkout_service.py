from decimal import Decimal
from datetime import datetime, timezone
import time, random
from app.extensions import db
from app.models.sales import Order, OrderItem, Payment, OrderStatus, PaymentMethod
from app.models.item import Item, ItemType
from app.models.shift import CashShift, ShiftStatus
from app.services.inventory_service import InventoryService

class CheckoutService:
    @staticmethod
    def generate_order_number(store_code: str) -> str:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_suffix = random.randint(1000, 9999)
        return f"ORD-{store_code}-{date_str}-{rand_suffix}"

    @classmethod
    def create_order(
        cls,
        store_id: str,
        user_id: str,
        store_code: str,
        items_data: list,
        order_type: str = "RETAIL_QUICK",
        table_number: str = None,
        guest_count: int = 1,
        customer_name: str = None,
        customer_phone: str = None,
        discount_amount: float = 0.0,
        notes: str = None,
        status: str = OrderStatus.PENDING_PAYMENT
    ) -> Order:
        """Create a new checkout order with line items, tax calculation, and modifiers."""
        # Find active shift if any
        active_shift = CashShift.query.filter_by(
            store_id=store_id,
            user_id=user_id,
            status=ShiftStatus.OPEN
        ).first()

        order_number = cls.generate_order_number(store_code)
        subtotal = Decimal("0.00")
        total_tax = Decimal("0.00")

        order = Order(
            store_id=store_id,
            user_id=user_id,
            shift_id=active_shift.id if active_shift else None,
            order_number=order_number,
            order_type=order_type,
            table_number=table_number,
            guest_count=guest_count,
            customer_name=customer_name,
            customer_phone=customer_phone,
            status=status,
            discount_amount=Decimal(str(discount_amount)),
            notes=notes
        )
        db.session.add(order)
        db.session.flush()

        for item_data in items_data:
            item_id = item_data['item_id']
            item = Item.query.get(item_id)
            if not item:
                raise ValueError(f"Item not found: {item_id}")

            qty = Decimal(str(item_data.get('quantity', 1)))
            unit_price = Decimal(str(item_data.get('unit_price', item.base_price)))
            item_disc = Decimal(str(item_data.get('discount_amount', 0.00)))
            
            # Base item subtotal
            line_subtotal = (qty * unit_price) - item_disc
            
            # Modifiers add-on prices if any
            modifiers = item_data.get('modifiers', [])
            mod_total = Decimal("0.00")
            for mod in modifiers:
                mod_price = Decimal(str(mod.get('price', 0.00)))
                mod_total += (qty * mod_price)
            line_subtotal += mod_total

            # Tax calculation
            tax_rate = Decimal(str(item.tax_rate))
            line_tax = (line_subtotal * (tax_rate / Decimal("100.00"))).quantize(Decimal("0.01"))

            subtotal += line_subtotal
            total_tax += line_tax

            # Station routing for KDS
            station = item.metadata_json.get('kds_station', 'KITCHEN') if item.metadata_json else 'KITCHEN'

            order_item = OrderItem(
                order_id=order.id,
                item_id=item.id,
                item_name=item.name,
                quantity=qty,
                unit_price=unit_price,
                tax_rate=tax_rate,
                tax_amount=line_tax,
                discount_amount=item_disc,
                subtotal=line_subtotal,
                modifiers=modifiers,
                kds_station=station,
                kds_status='PENDING',
                notes=item_data.get('notes')
            )
            db.session.add(order_item)

        order.subtotal = subtotal
        order.tax_amount = total_tax
        order.grand_total = (subtotal + total_tax) - order.discount_amount
        return order

    @classmethod
    def process_payment(
        cls,
        order_id: str,
        user_id: str,
        payments_data: list # [{'method': 'CASH'|'CARD'|'MOBILE_MONEY', 'amount': float, 'reference': str}]
    ) -> Order:
        """Process full or split payments, record shift cash flow, and deduct inventory."""
        order = Order.query.get(order_id)
        if not order:
            raise ValueError("Order not found")
        if order.status in [OrderStatus.PAID, OrderStatus.COMPLETED]:
            raise ValueError(f"Order is already paid ({order.status})")

        total_paid = Decimal("0.00")
        total_tendered = Decimal("0.00")

        # Active shift
        shift = CashShift.query.filter_by(
            store_id=order.store_id,
            user_id=user_id,
            status=ShiftStatus.OPEN
        ).first()

        for p_data in payments_data:
            method = p_data.get('method', PaymentMethod.CASH)
            amount_tendered = Decimal(str(p_data.get('amount_tendered', p_data.get('amount', 0.00))))
            amount_to_pay = Decimal(str(p_data.get('amount', amount_tendered)))
            ref_code = p_data.get('reference')

            change = Decimal("0.00")
            if method == PaymentMethod.CASH and amount_tendered > amount_to_pay:
                change = amount_tendered - amount_to_pay

            payment = Payment(
                order_id=order.id,
                store_id=order.store_id,
                user_id=user_id,
                payment_method=method,
                amount_tendered=amount_tendered,
                amount_paid=amount_to_pay,
                change_returned=change,
                transaction_reference=ref_code,
                status='SUCCESS'
            )
            db.session.add(payment)

            total_paid += amount_to_pay
            total_tendered += amount_tendered

            # Shift cash drawer updates
            if shift:
                if method == PaymentMethod.CASH:
                    shift.total_cash_sales = Decimal(str(shift.total_cash_sales)) + amount_to_pay
                    shift.expected_cash = Decimal(str(shift.expected_cash)) + amount_to_pay
                elif method == PaymentMethod.CARD:
                    shift.total_card_sales = Decimal(str(shift.total_card_sales)) + amount_to_pay
                elif method == PaymentMethod.MOBILE_MONEY:
                    shift.total_mobile_sales = Decimal(str(shift.total_mobile_sales)) + amount_to_pay

        if total_paid < order.grand_total:
            order.status = OrderStatus.PENDING_PAYMENT # partial payment recorded
        else:
            order.status = OrderStatus.COMPLETED
            order.completed_at = datetime.now(timezone.utc)

            # Deduct inventory atomically
            for o_item in order.items:
                item = Item.query.get(o_item.item_id)
                if not item:
                    continue

                if item.item_type == ItemType.COMPOSITE_RECIPE:
                    InventoryService.deduct_recipe_ingredients(
                        store_id=order.store_id,
                        composite_item_id=item.id,
                        quantity_sold=float(o_item.quantity),
                        user_id=user_id,
                        order_reference=order.order_number
                    )
                elif item.item_type == ItemType.PHYSICAL and item.track_inventory:
                    InventoryService.adjust_stock(
                        store_id=order.store_id,
                        item_id=item.id,
                        quantity_delta=-float(o_item.quantity),
                        reason=f"SALE:{order.order_number}",
                        user_id=user_id,
                        notes=f"Sold in order {order.order_number}"
                    )

        return order
