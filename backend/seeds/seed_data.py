import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models.tenant import Store, User, UserRole, BusinessType
from app.models.hardware import StoreHardwareConfig
from app.models.item import Item, ItemCategory, ItemType, RecipeIngredient
from app.models.stock import StockLevel
from app.models.procurement import Supplier
from app.services.licensing_service import LicensingService
from app.utils.hardware_fingerprint import get_hardware_fingerprint

def seed_database():
    app = create_app("development")
    with app.app_context():
        print("[SEED] Resetting and initializing database...")
        db.create_all()

        # 1. Super Admin Store & User
        super_store = Store.query.filter_by(code="SUPER-TENANT").first()
        if not super_store:
            super_store = Store(
                name="Platform Administration",
                code="SUPER-TENANT",
                business_type=BusinessType.SERVICE,
                is_license_active=True
            )
            db.session.add(super_store)
            db.session.flush()

        super_admin = User.query.filter_by(email="superadmin@pos.local").first()
        if not super_admin:
            super_admin = User(
                store_id=super_store.id,
                email="superadmin@pos.local",
                full_name="Global Super Administrator",
                role=UserRole.SUPER_ADMIN
            )
            super_admin.set_password("Admin@12345")
            super_admin.set_pin("9999")
            db.session.add(super_admin)
            print("  Created Super Admin: superadmin@pos.local (Password: Admin@12345)")

        # 2. Demo Retail Store: Apex Retail Mart
        apex_store = Store.query.filter_by(code="APEX-01").first()
        if not apex_store:
            apex_store = Store(
                name="Apex Retail Mart",
                code="APEX-01",
                business_type=BusinessType.RETAIL,
                currency_code="USD",
                tax_number="TAX-US-987654321",
                address="100 Innovation Way, Silicon Valley, CA",
                phone="+1 555 019 2834",
                receipt_header="*** APEX RETAIL MART ***\nYour One-Stop Premium Outlet",
                receipt_footer="Thank you for shopping at Apex!\nReturn policy: 14 days with receipt."
            )
            db.session.add(apex_store)
            db.session.flush()

            # Hardware config
            apex_hw = StoreHardwareConfig(
                store_id=apex_store.id,
                printer_interface="USB",
                cash_drawer_pin=2,
                enable_scale_reader=True,
                scale_port="COM3",
                enable_cfd=True
            )
            db.session.add(apex_hw)

            # Issue & Activate Cryptographic License
            hw_fingerprint = get_hardware_fingerprint()
            priv_key_path = app.config["ED25519_PRIVATE_KEY_PATH"]
            license_data = LicensingService.issue_license(
                store_id=apex_store.id,
                store_code=apex_store.code,
                hardware_fingerprint=hw_fingerprint,
                private_key_path=priv_key_path,
                days_valid=365,
                tier="ENTERPRISE",
                allowed_modules=["RETAIL", "INVENTORY", "CFD", "OFFLINE_SYNC"]
            )
            apex_store.license_key = license_data["license_key"]
            apex_store.is_license_active = True
            apex_store.hardware_fingerprint = hw_fingerprint
            apex_store.license_expires_at = db.func.now()

            # Store Admin & Staff
            apex_admin = User(
                store_id=apex_store.id,
                email="admin@apex.local",
                full_name="Sarah Jenkins (Store Admin)",
                role=UserRole.STORE_ADMIN
            )
            apex_admin.set_password("Apex@12345")
            apex_admin.set_pin("1111")
            db.session.add(apex_admin)

            apex_mgr = User(
                store_id=apex_store.id,
                email="manager@apex.local",
                full_name="Marcus Vance (Shift Supervisor)",
                role=UserRole.STORE_MANAGER
            )
            apex_mgr.set_password("Apex@12345")
            apex_mgr.set_pin("2222")
            db.session.add(apex_mgr)

            apex_cashier = User(
                store_id=apex_store.id,
                email="cashier@apex.local",
                full_name="Alice Wang (Cashier 1)",
                role=UserRole.CASHIER
            )
            apex_cashier.set_password("Apex@12345")
            apex_cashier.set_pin("1234")
            db.session.add(apex_cashier)

            # Seed Retail Categories & Items
            cat_beverages = ItemCategory(store_id=apex_store.id, name="Beverages", sort_order=1)
            cat_snacks = ItemCategory(store_id=apex_store.id, name="Snacks & Bakery", sort_order=2)
            cat_electronics = ItemCategory(store_id=apex_store.id, name="Electronics", sort_order=3)
            db.session.add_all([cat_beverages, cat_snacks, cat_electronics])
            db.session.flush()

            # Items
            items_apex = [
                Item(store_id=apex_store.id, category_id=cat_beverages.id, name="Organic Cold Brew Coffee 330ml", sku="COF-001", barcode="1001", base_price=4.50, cost_price=2.00, tax_rate=16.00, item_type=ItemType.PHYSICAL),
                Item(store_id=apex_store.id, category_id=cat_beverages.id, name="Sparkling Mineral Water 500ml", sku="WAT-002", barcode="1002", base_price=2.25, cost_price=0.80, tax_rate=16.00, item_type=ItemType.PHYSICAL),
                Item(store_id=apex_store.id, category_id=cat_snacks.id, name="Artisan Dark Chocolate 85%", sku="CHO-003", barcode="1003", base_price=5.00, cost_price=2.50, tax_rate=16.00, item_type=ItemType.PHYSICAL),
                Item(store_id=apex_store.id, category_id=cat_snacks.id, name="Organic Almond Granola Bar", sku="GRN-004", barcode="1004", base_price=3.00, cost_price=1.20, tax_rate=16.00, item_type=ItemType.PHYSICAL),
                Item(store_id=apex_store.id, category_id=cat_electronics.id, name="USB-C Fast Charging Cable 2m", sku="CAB-005", barcode="1005", base_price=15.00, cost_price=5.00, tax_rate=16.00, item_type=ItemType.PHYSICAL),
                Item(store_id=apex_store.id, category_id=cat_electronics.id, name="Wireless Ergonomic Mouse", sku="MOU-006", barcode="1006", base_price=29.99, cost_price=12.00, tax_rate=16.00, item_type=ItemType.PHYSICAL),
                Item(store_id=apex_store.id, name="Express Device Repair / Diagnostic", sku="SRV-001", barcode="9001", base_price=45.00, cost_price=0.00, tax_rate=16.00, track_inventory=False, item_type=ItemType.SERVICE),
            ]
            db.session.add_all(items_apex)
            db.session.flush()

            for item in items_apex:
                if item.track_inventory:
                    stock = StockLevel(store_id=apex_store.id, item_id=item.id, current_stock=50.0, low_stock_threshold=10.0)
                    db.session.add(stock)

            # Supplier
            supplier1 = Supplier(
                store_id=apex_store.id,
                name="Global Beverage Distributors Ltd",
                contact_name="Dave Miller",
                email="orders@globalbev.com",
                phone="+1 555 444 3333",
                payment_terms_days=30
            )
            db.session.add(supplier1)

            print("  Created Apex Retail Store & Catalog")

        # 3. Demo F&B Store: Bistro Deluxe (with Composite Recipes & Tables)
        bistro_store = Store.query.filter_by(code="BISTRO-01").first()
        if not bistro_store:
            bistro_store = Store(
                name="Bistro Deluxe Cafe & Bar",
                code="BISTRO-01",
                business_type=BusinessType.FOOD_BEVERAGE,
                currency_code="USD",
                tax_number="TAX-FB-123456789",
                address="45 Gourmet Avenue, Downtown",
                phone="+1 555 888 9999",
                receipt_header="*** BISTRO DELUXE ***\nArtisan Coffee & Fine Dining",
                receipt_footer="Tips are appreciated! Follow us @BistroDeluxe"
            )
            db.session.add(bistro_store)
            db.session.flush()

            # Hardware config
            bistro_hw = StoreHardwareConfig(
                store_id=bistro_store.id,
                printer_interface="NETWORK",
                printer_address="192.168.1.150:9100",
                cash_drawer_pin=2,
                enable_scale_reader=False,
                enable_cfd=True
            )
            db.session.add(bistro_hw)

            # Issue & Activate Cryptographic License
            hw_fingerprint = get_hardware_fingerprint()
            priv_key_path = app.config["ED25519_PRIVATE_KEY_PATH"]
            license_data = LicensingService.issue_license(
                store_id=bistro_store.id,
                store_code=bistro_store.code,
                hardware_fingerprint=hw_fingerprint,
                private_key_path=priv_key_path,
                days_valid=365,
                tier="RESTAURANT_PRO",
                allowed_modules=["FOOD_BEVERAGE", "KDS", "CFD", "INVENTORY", "OFFLINE_SYNC"]
            )
            bistro_store.license_key = license_data["license_key"]
            bistro_store.is_license_active = True
            bistro_store.hardware_fingerprint = hw_fingerprint

            # Users
            bistro_admin = User(
                store_id=bistro_store.id,
                email="admin@bistro.local",
                full_name="Chef Jean-Luc (Owner)",
                role=UserRole.STORE_ADMIN
            )
            bistro_admin.set_password("Bistro@12345")
            bistro_admin.set_pin("3333")
            db.session.add(bistro_admin)

            bistro_waiter = User(
                store_id=bistro_store.id,
                email="waiter@bistro.local",
                full_name="Elena Gomez (Floor Staff)",
                role=UserRole.CASHIER
            )
            bistro_waiter.set_password("Bistro@12345")
            bistro_waiter.set_pin("5678")
            db.session.add(bistro_waiter)

            bistro_kitchen = User(
                store_id=bistro_store.id,
                email="kitchen@bistro.local",
                full_name="Kitchen Display Terminal",
                role=UserRole.STAFF
            )
            bistro_kitchen.set_password("Bistro@12345")
            bistro_kitchen.set_pin("0000")
            db.session.add(bistro_kitchen)

            # F&B Categories
            cat_mains = ItemCategory(store_id=bistro_store.id, name="Mains & Grills", sort_order=1)
            cat_drinks = ItemCategory(store_id=bistro_store.id, name="Cocktails & Drinks", sort_order=2)
            cat_raw = ItemCategory(store_id=bistro_store.id, name="Raw Ingredients (Pantry)", sort_order=3)
            db.session.add_all([cat_mains, cat_drinks, cat_raw])
            db.session.flush()

            # Raw ingredients (Physical)
            ing_bun = Item(store_id=bistro_store.id, category_id=cat_raw.id, name="Brioche Burger Buns", sku="RAW-BUN", barcode="8001", base_price=0.50, cost_price=0.30, item_type=ItemType.PHYSICAL)
            ing_patty = Item(store_id=bistro_store.id, category_id=cat_raw.id, name="Angus Beef Patty 180g", sku="RAW-PATTY", barcode="8002", base_price=3.50, cost_price=2.20, item_type=ItemType.PHYSICAL)
            ing_cheese = Item(store_id=bistro_store.id, category_id=cat_raw.id, name="Aged Cheddar Cheese Slice", sku="RAW-CHEESE", barcode="8003", base_price=0.40, cost_price=0.20, item_type=ItemType.PHYSICAL)
            
            # Composite Menu Items (Composite Recipe)
            burger = Item(
                store_id=bistro_store.id,
                category_id=cat_mains.id,
                name="Deluxe Angus Cheeseburger",
                sku="REC-BURGER",
                barcode="2001",
                base_price=16.50,
                cost_price=4.50,
                tax_rate=16.00,
                item_type=ItemType.COMPOSITE_RECIPE,
                metadata_json={"kds_station": "GRILL", "modifiers": [{"name": "Extra Cheese", "price": 1.50}, {"name": "Add Bacon", "price": 2.00}, {"name": "No Onion", "price": 0.00}]}
            )

            cocktail = Item(
                store_id=bistro_store.id,
                category_id=cat_drinks.id,
                name="Smoked Bourbon Old Fashioned",
                sku="REC-OLD-FASHION",
                barcode="2002",
                base_price=14.00,
                cost_price=3.00,
                tax_rate=16.00,
                item_type=ItemType.PHYSICAL,
                metadata_json={"kds_station": "BAR"}
            )

            db.session.add_all([ing_bun, ing_patty, ing_cheese, burger, cocktail])
            db.session.flush()

            # Set raw ingredient stock
            db.session.add(StockLevel(store_id=bistro_store.id, item_id=ing_bun.id, current_stock=100.0, low_stock_threshold=20.0))
            db.session.add(StockLevel(store_id=bistro_store.id, item_id=ing_patty.id, current_stock=80.0, low_stock_threshold=15.0))
            db.session.add(StockLevel(store_id=bistro_store.id, item_id=ing_cheese.id, current_stock=150.0, low_stock_threshold=30.0))
            db.session.add(StockLevel(store_id=bistro_store.id, item_id=cocktail.id, current_stock=50.0, low_stock_threshold=10.0))

            # Composite recipe ingredient mappings for Burger
            db.session.add(RecipeIngredient(composite_item_id=burger.id, ingredient_item_id=ing_bun.id, quantity_required=1.0, unit_of_measure="pcs"))
            db.session.add(RecipeIngredient(composite_item_id=burger.id, ingredient_item_id=ing_patty.id, quantity_required=1.0, unit_of_measure="pcs"))
            db.session.add(RecipeIngredient(composite_item_id=burger.id, ingredient_item_id=ing_cheese.id, quantity_required=2.0, unit_of_measure="slice"))

            print("  Created Bistro Deluxe, F&B Composite Recipes & Inventory")

        db.session.commit()
        print("[SEED] All seed records populated successfully!")

if __name__ == "__main__":
    seed_database()
