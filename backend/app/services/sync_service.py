from datetime import datetime, timezone
from app.extensions import db
from app.models.sync import OfflineSyncQueue, SyncStatus
from app.models.sales import Order, OrderItem, Payment, OrderStatus
from app.models.item import Item, ItemType
from app.services.inventory_service import InventoryService

class SyncService:
    """Bi-directional offline-to-online transaction replay and conflict resolution engine."""

    @classmethod
    def process_sync_batch(cls, store_id: str, queue_items: list) -> dict:
        """Process a list of queued offline records idempotently."""
        synced_ids = []
        failed_items = []

        for item_data in queue_items:
            client_id = item_data.get('client_id')
            entity_name = item_data.get('entity_name')
            action = item_data.get('action', 'CREATE')
            payload = item_data.get('payload', {})

            # Record in offline_sync_queue table
            queue_record = OfflineSyncQueue(
                store_id=store_id,
                entity_name=entity_name,
                entity_id=client_id,
                payload=payload,
                action_type=action,
                status=SyncStatus.PENDING
            )
            db.session.add(queue_record)

            try:
                if entity_name == 'orders':
                    cls._sync_order(store_id, payload)
                elif entity_name == 'inventory_adjustments':
                    cls._sync_inventory(store_id, payload)

                queue_record.status = SyncStatus.SYNCED
                queue_record.synced_at = datetime.now(timezone.utc)
                synced_ids.append(client_id)
            except Exception as e:
                queue_record.status = SyncStatus.FAILED
                queue_record.error_message = str(e)
                failed_items.append({"client_id": client_id, "error": str(e)})

        db.session.commit()
        return {
            "synced_count": len(synced_ids),
            "failed_count": len(failed_items),
            "synced_ids": synced_ids,
            "failed_items": failed_items
        }

    @classmethod
    def _sync_order(cls, store_id: str, payload: dict):
        """Replay offline order creation idempotently without duplicate charges."""
        order_number = payload.get('order_number')
        existing = Order.query.filter_by(store_id=store_id, order_number=order_number).first()
        if existing:
            return existing # Already synced

        order = Order(
            store_id=store_id,
            user_id=payload.get('user_id'),
            order_number=order_number,
            order_type=payload.get('order_type', 'RETAIL_QUICK'),
            table_number=payload.get('table_number'),
            guest_count=int(payload.get('guest_count', 1)),
            customer_name=payload.get('customer_name'),
            status=payload.get('status', OrderStatus.COMPLETED),
            subtotal=payload.get('subtotal', 0.00),
            tax_amount=payload.get('tax_amount', 0.00),
            discount_amount=payload.get('discount_amount', 0.00),
            grand_total=payload.get('grand_total', 0.00),
            notes=payload.get('notes')
        )
        db.session.add(order)
        db.session.flush()

        for item_data in payload.get('items', []):
            order_item = OrderItem(
                order_id=order.id,
                item_id=item_data['item_id'],
                item_name=item_data['item_name'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                tax_rate=item_data.get('tax_rate', 0.00),
                tax_amount=item_data.get('tax_amount', 0.00),
                discount_amount=item_data.get('discount_amount', 0.00),
                subtotal=item_data['subtotal'],
                modifiers=item_data.get('modifiers', []),
                notes=item_data.get('notes')
            )
            db.session.add(order_item)

            # Reconcile inventory deduction
            item = Item.query.get(item_data['item_id'])
            if item and item.track_inventory and item.item_type == ItemType.PHYSICAL:
                InventoryService.adjust_stock(
                    store_id=store_id,
                    item_id=item.id,
                    quantity_delta=-float(item_data['quantity']),
                    reason=f"OFFLINE_SYNC_SALE:{order_number}",
                    user_id=payload.get('user_id'),
                    notes="Reconciled from offline sync queue"
                )

        for p_data in payload.get('payments', []):
            payment = Payment(
                order_id=order.id,
                store_id=store_id,
                user_id=payload.get('user_id'),
                payment_method=p_data.get('payment_method', 'CASH'),
                amount_tendered=p_data.get('amount_tendered', p_data.get('amount', 0.00)),
                amount_paid=p_data.get('amount_paid', p_data.get('amount', 0.00)),
                change_returned=p_data.get('change_returned', 0.00),
                transaction_reference=p_data.get('transaction_reference'),
                status='SUCCESS'
            )
            db.session.add(payment)

    @classmethod
    def _sync_inventory(cls, store_id: str, payload: dict):
        InventoryService.adjust_stock(
            store_id=store_id,
            item_id=payload['item_id'],
            quantity_delta=payload['quantity_delta'],
            reason=f"OFFLINE_SYNC_ADJUST:{payload.get('reason', 'MANUAL')}",
            user_id=payload.get('user_id'),
            notes=payload.get('notes')
        )
