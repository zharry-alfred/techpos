from decimal import Decimal
from datetime import datetime, timezone
from app.extensions import db
from app.models.item import Item, ItemType, RecipeIngredient
from app.models.stock import StockLevel, StockTransfer, StockTransferItem, StockAdjustmentLog, TransferStatus

class InventoryService:
    @staticmethod
    def adjust_stock(
        store_id: str,
        item_id: str,
        quantity_delta: float,
        reason: str,
        user_id: str,
        batch_number: str = "DEFAULT",
        notes: str = None,
        expiry_date: datetime = None
    ) -> StockLevel:
        """Atomically adjust stock level for an item and write to audit log."""
        stock = StockLevel.query.filter_by(
            store_id=store_id,
            item_id=item_id,
            batch_number=batch_number
        ).first()

        if not stock:
            stock = StockLevel(
                store_id=store_id,
                item_id=item_id,
                batch_number=batch_number,
                current_stock=0.00,
                expiry_date=expiry_date
            )
            db.session.add(stock)
            db.session.flush()

        stock.current_stock = Decimal(str(stock.current_stock)) + Decimal(str(quantity_delta))
        if expiry_date:
            stock.expiry_date = expiry_date

        log = StockAdjustmentLog(
            store_id=store_id,
            item_id=item_id,
            user_id=user_id,
            quantity_delta=quantity_delta,
            resulting_stock=float(stock.current_stock),
            reason=reason,
            notes=notes
        )
        db.session.add(log)
        return stock

    @classmethod
    def deduct_recipe_ingredients(
        cls,
        store_id: str,
        composite_item_id: str,
        quantity_sold: float,
        user_id: str,
        order_reference: str = None
    ):
        """When a composite recipe item (e.g., Burger or Cocktail) is ordered,
        atomically deduct its raw ingredients from current stock levels.
        """
        ingredients = RecipeIngredient.query.filter_by(composite_item_id=composite_item_id).all()
        for ing in ingredients:
            required_qty = Decimal(str(ing.quantity_required)) * Decimal(str(quantity_sold))
            cls.adjust_stock(
                store_id=store_id,
                item_id=ing.ingredient_item_id,
                quantity_delta=-float(required_qty),
                reason=f"RECIPE_DEDUCTION:{order_reference or 'SALE'}",
                user_id=user_id,
                notes=f"Auto-deducted {required_qty} {ing.unit_of_measure} for recipe {composite_item_id}"
            )

    @staticmethod
    def get_low_stock_items(store_id: str) -> list:
        """Return list of physical items that have fallen below low-stock threshold."""
        items = Item.query.filter_by(
            store_id=store_id,
            track_inventory=True,
            item_type=ItemType.PHYSICAL,
            is_active=True
        ).all()

        low_stock_items = []
        for item in items:
            total_stock = sum(float(sl.current_stock) for sl in item.stock_levels)
            threshold = float(item.stock_levels[0].low_stock_threshold) if item.stock_levels else 5.0
            if total_stock <= threshold:
                item_data = item.to_dict()
                item_data['shortage'] = threshold - total_stock
                low_stock_items.append(item_data)

        return low_stock_items

    @classmethod
    def create_transfer(
        cls,
        source_store_id: str,
        destination_store_id: str,
        items: list, # [{'item_id': str, 'quantity': float}]
        user_id: str,
        notes: str = None
    ) -> StockTransfer:
        """Initiate Inter-Store Stock Transfer."""
        import random, time
        transfer_num = f"IST-{int(time.time())}-{random.randint(100, 999)}"

        transfer = StockTransfer(
            source_store_id=source_store_id,
            destination_store_id=destination_store_id,
            status=TransferStatus.REQUESTED,
            transfer_number=transfer_num,
            created_by=user_id,
            notes=notes
        )
        db.session.add(transfer)
        db.session.flush()

        for item_data in items:
            transfer_item = StockTransferItem(
                transfer_id=transfer.id,
                item_id=item_data['item_id'],
                quantity=item_data['quantity']
            )
            db.session.add(transfer_item)

        return transfer

    @classmethod
    def dispatch_transfer(cls, transfer_id: str, user_id: str) -> StockTransfer:
        """Dispatch transfer: deducts stock from source store and sets IN_TRANSIT."""
        transfer = StockTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError("Stock transfer not found")
        if transfer.status != TransferStatus.REQUESTED:
            raise ValueError(f"Cannot dispatch transfer in status '{transfer.status}'")

        for item in transfer.items:
            cls.adjust_stock(
                store_id=transfer.source_store_id,
                item_id=item.item_id,
                quantity_delta=-float(item.quantity),
                reason=f"TRANSFER_DISPATCH:{transfer.transfer_number}",
                user_id=user_id,
                notes=f"Dispatched in transfer {transfer.transfer_number}"
            )

        transfer.status = TransferStatus.IN_TRANSIT
        transfer.dispatched_at = datetime.now(timezone.utc)
        return transfer

    @classmethod
    def receive_transfer(cls, transfer_id: str, receiver_user_id: str, received_items: list = None) -> StockTransfer:
        """Receive transfer: credits stock into destination store and marks RECEIVED."""
        transfer = StockTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError("Stock transfer not found")
        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ValueError(f"Cannot receive transfer in status '{transfer.status}'. Must be IN_TRANSIT.")

        received_map = {item['item_id']: item['quantity'] for item in received_items} if received_items else {}

        for item in transfer.items:
            qty_received = received_map.get(str(item.item_id), float(item.quantity))
            item.received_quantity = qty_received

            cls.adjust_stock(
                store_id=transfer.destination_store_id,
                item_id=item.item_id,
                quantity_delta=qty_received,
                reason=f"TRANSFER_RECEIVE:{transfer.transfer_number}",
                user_id=receiver_user_id,
                notes=f"Received in transfer {transfer.transfer_number}"
            )

        transfer.status = TransferStatus.RECEIVED
        transfer.received_by = receiver_user_id
        transfer.received_at = datetime.now(timezone.utc)
        return transfer
