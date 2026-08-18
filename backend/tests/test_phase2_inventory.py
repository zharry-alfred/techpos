import pytest
from decimal import Decimal
from app.extensions import db
from app.models.tenant import Store, User, UserRole, BusinessType
from app.models.item import Item, ItemType, RecipeIngredient
from app.models.stock import StockLevel, StockTransfer, TransferStatus
from app.services.inventory_service import InventoryService

def test_item_creation_and_catalog(client, admin_token):
    """Test creating physical, service, and composite recipe items."""
    res = client.post('/api/v1/items', json={
        'name': 'Matcha Green Tea Latte',
        'sku': 'TEA-001',
        'barcode': '3001',
        'base_price': 5.50,
        'cost_price': 1.50,
        'tax_rate': 16.00,
        'item_type': 'PHYSICAL',
        'initial_stock': 40.0,
        'low_stock_threshold': 8.0
    }, headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 201
    data = res.get_json()
    assert data["item"]["name"] == "Matcha Green Tea Latte"
    assert data["item"]["current_stock"] == 40.0

def test_composite_recipe_deduction(app, client, admin_token):
    """Verify that composite recipe items automatically deduct raw ingredient inventory."""
    with app.app_context():
        store = Store.query.filter_by(code="TEST-01").first()
        admin_user = User.query.filter_by(store_id=store.id, role=UserRole.STORE_ADMIN).first()

        # Raw ingredients
        bun = Item(store_id=store.id, name="Test Bun", sku="TBUN", base_price=1.0, item_type=ItemType.PHYSICAL)
        patty = Item(store_id=store.id, name="Test Patty", sku="TPATTY", base_price=2.0, item_type=ItemType.PHYSICAL)
        db.session.add_all([bun, patty])
        db.session.flush()

        db.session.add(StockLevel(store_id=store.id, item_id=bun.id, current_stock=20.0))
        db.session.add(StockLevel(store_id=store.id, item_id=patty.id, current_stock=20.0))

        # Composite recipe
        burger = Item(store_id=store.id, name="Test Burger", sku="TBURGER", base_price=8.0, item_type=ItemType.COMPOSITE_RECIPE)
        db.session.add(burger)
        db.session.flush()

        db.session.add(RecipeIngredient(composite_item_id=burger.id, ingredient_item_id=bun.id, quantity_required=1.0))
        db.session.add(RecipeIngredient(composite_item_id=burger.id, ingredient_item_id=patty.id, quantity_required=2.0))
        db.session.commit()

        # Deduct 3 burgers (3 buns, 6 patties)
        InventoryService.deduct_recipe_ingredients(
            store_id=store.id,
            composite_item_id=burger.id,
            quantity_sold=3.0,
            user_id=admin_user.id,
            order_reference="ORD-TEST-001"
        )
        db.session.commit()

        # Verify stock levels
        bun_stock = StockLevel.query.filter_by(store_id=store.id, item_id=bun.id).first()
        patty_stock = StockLevel.query.filter_by(store_id=store.id, item_id=patty.id).first()

        assert float(bun_stock.current_stock) == 17.0 # 20 - 3
        assert float(patty_stock.current_stock) == 14.0 # 20 - 6

def test_inter_store_transfer_flow(app):
    """Test Inter-Store Stock Transfer workflow (Requested -> In Transit -> Received)."""
    with app.app_context():
        store_a = Store(name="Store Alpha", code="ALPHA", business_type=BusinessType.RETAIL, is_license_active=True)
        store_b = Store(name="Store Beta", code="BETA", business_type=BusinessType.RETAIL, is_license_active=True)
        db.session.add_all([store_a, store_b])
        db.session.flush()

        user_a = User(store_id=store_a.id, email="a@alpha.local", full_name="Alpha Staff", role=UserRole.STORE_ADMIN)
        user_a.set_password("pass")
        user_b = User(store_id=store_b.id, email="b@beta.local", full_name="Beta Staff", role=UserRole.STORE_ADMIN)
        user_b.set_password("pass")
        db.session.add_all([user_a, user_b])
        db.session.flush()

        item = Item(store_id=store_a.id, name="Shared Widget", sku="WIDGET-01", base_price=10.0, item_type=ItemType.PHYSICAL)
        db.session.add(item)
        db.session.flush()

        # Store A has 100 widgets
        db.session.add(StockLevel(store_id=store_a.id, item_id=item.id, current_stock=100.0))
        db.session.commit()

        # 1. Create transfer request: 30 widgets from A to B
        transfer = InventoryService.create_transfer(
            source_store_id=store_a.id,
            destination_store_id=store_b.id,
            items=[{'item_id': item.id, 'quantity': 30.0}],
            user_id=user_a.id,
            notes="Transfer for weekend promotion"
        )
        db.session.commit()
        assert transfer.status == TransferStatus.REQUESTED

        # 2. Dispatch transfer from Alpha
        dispatched = InventoryService.dispatch_transfer(transfer.id, user_a.id)
        db.session.commit()
        assert dispatched.status == TransferStatus.IN_TRANSIT
        
        stock_a = StockLevel.query.filter_by(store_id=store_a.id, item_id=item.id).first()
        assert float(stock_a.current_stock) == 70.0 # 100 - 30

        # 3. Receive transfer at Beta
        received = InventoryService.receive_transfer(transfer.id, user_b.id)
        db.session.commit()
        assert received.status == TransferStatus.RECEIVED

        stock_b = StockLevel.query.filter_by(store_id=store_b.id, item_id=item.id).first()
        assert float(stock_b.current_stock) == 30.0
