import pytest
import os
import tempfile
from pathlib import Path
from app import create_app
from app.extensions import db
from app.models.tenant import Store, User, UserRole, BusinessType
from app.services.licensing_service import LicensingService
from app.utils.hardware_fingerprint import get_hardware_fingerprint

@pytest.fixture
def app():
    # Use temporary test keys dir
    temp_dir = tempfile.mkdtemp()
    keys_dir = Path(temp_dir) / "test_keys"
    LicensingService.ensure_keys_exist(keys_dir)

    app = create_app("testing")
    app.config["ED25519_PRIVATE_KEY_PATH"] = str(keys_dir / "license_private_ed25519.pem")
    app.config["ED25519_PUBLIC_KEY_PATH"] = str(keys_dir / "license_public_ed25519.pem")
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()
        
        # Seed test store & users
        test_store = Store(
            name="Test Mart",
            code="TEST-01",
            business_type=BusinessType.RETAIL,
            is_license_active=True
        )
        db.session.add(test_store)
        db.session.flush()

        super_store = Store(
            name="Platform Super Store",
            code="SUPER-TEST",
            business_type=BusinessType.SERVICE,
            is_license_active=True
        )
        db.session.add(super_store)
        db.session.flush()

        super_admin = User(
            store_id=super_store.id,
            email="superadmin@test.local",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN
        )
        super_admin.set_password("SuperPass123!")
        db.session.add(super_admin)

        store_admin = User(
            store_id=test_store.id,
            email="admin@test.local",
            full_name="Store Admin",
            role=UserRole.STORE_ADMIN
        )
        store_admin.set_password("AdminPass123!")
        db.session.add(store_admin)

        cashier = User(
            store_id=test_store.id,
            email="cashier@test.local",
            full_name="Cashier Bob",
            role=UserRole.CASHIER
        )
        cashier.set_password("CashierPass123!")
        cashier.set_pin("1234")
        db.session.add(cashier)

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def superadmin_token(client):
    res = client.post('/api/v1/auth/login', json={
        'email': 'superadmin@test.local',
        'password': 'SuperPass123!'
    })
    return res.get_json()['access_token']

@pytest.fixture
def admin_token(client):
    res = client.post('/api/v1/auth/login', json={
        'email': 'admin@test.local',
        'password': 'AdminPass123!'
    })
    return res.get_json()['access_token']

@pytest.fixture
def cashier_token(client):
    res = client.post('/api/v1/auth/login', json={
        'email': 'cashier@test.local',
        'password': 'CashierPass123!'
    })
    return res.get_json()['access_token']
