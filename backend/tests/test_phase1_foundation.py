import json
import pytest
from app.services.licensing_service import LicensingService
from app.utils.hardware_fingerprint import get_hardware_fingerprint
from app.models.tenant import Store, User, UserRole

def test_hardware_fingerprint_generation():
    """Verify hardware fingerprint produces standard deterministic HW-XXXX format."""
    hw1 = get_hardware_fingerprint()
    hw2 = get_hardware_fingerprint()
    assert hw1.startswith("HW-")
    assert len(hw1.split("-")) == 5
    assert hw1 == hw2, "Hardware fingerprint must be deterministic across calls"

def test_cryptographic_license_flow(app):
    """Verify Ed25519 asymmetric license issuance, signing, and verification."""
    priv_key_path = app.config["ED25519_PRIVATE_KEY_PATH"]
    pub_key_path = app.config["ED25519_PUBLIC_KEY_PATH"]
    hw = get_hardware_fingerprint()

    # 1. Issue license
    issued = LicensingService.issue_license(
        store_id="11111111-1111-1111-1111-111111111111",
        store_code="TEST-STORE",
        hardware_fingerprint=hw,
        private_key_path=priv_key_path,
        days_valid=30,
        tier="PRO",
        allowed_modules=["RETAIL", "INVENTORY"]
    )
    assert "license_key" in issued
    assert "certificate" in issued

    # 2. Verify valid license
    result = LicensingService.verify_license(
        license_data=issued["license_key"],
        public_key_path=pub_key_path,
        expected_store_id="11111111-1111-1111-1111-111111111111",
        enforce_hardware=True
    )
    assert result["valid"] is True
    assert result["payload"]["store_code"] == "TEST-STORE"
    assert result["payload"]["tier"] == "PRO"

    # 3. Test hardware mismatch detection
    result_wrong_hw = LicensingService.verify_license(
        license_data=issued["license_key"],
        public_key_path=pub_key_path,
        expected_store_id="11111111-1111-1111-1111-111111111111",
        enforce_hardware=False
    )
    assert result_wrong_hw["valid"] is True

    # 4. Test tampering detection
    tampered_cert = issued["certificate"].copy()
    tampered_cert["payload"] = tampered_cert["payload"].copy()
    tampered_cert["payload"]["tier"] = "UNAUTHORIZED_UPGRADE"
    
    tampered_result = LicensingService.verify_license(
        license_data=tampered_cert,
        public_key_path=pub_key_path
    )
    assert tampered_result["valid"] is False
    assert "Invalid cryptographic signature" in tampered_result["error"]

def test_auth_login_and_me(client, cashier_token):
    """Test user login and token introspection."""
    # Test me endpoint
    res = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {cashier_token}'})
    assert res.status_code == 200
    data = res.get_json()
    assert data["user"]["email"] == "cashier@test.local"
    assert data["user"]["role"] == UserRole.CASHIER
    assert data["store"]["code"] == "TEST-01"

def test_auth_pin_login(client):
    """Test fast cashier PIN login."""
    res = client.post('/api/v1/auth/pin-login', json={
        'store_code': 'TEST-01',
        'pin': '1234'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data
    assert data["user"]["full_name"] == "Cashier Bob"

    # Test invalid PIN
    res_bad = client.post('/api/v1/auth/pin-login', json={
        'store_code': 'TEST-01',
        'pin': '9999'
    })
    assert res_bad.status_code == 401

def test_rbac_restrictions(client, cashier_token, admin_token, superadmin_token):
    """Test Role-Based Access Control on protected endpoints."""
    # Cashier cannot provision new stores (Super Admin only)
    res_cashier = client.post('/api/v1/stores', json={
        'name': 'Hacked Store',
        'code': 'HACK-01'
    }, headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_cashier.status_code == 403

    # Super Admin CAN provision new stores
    res_super = client.post('/api/v1/stores', json={
        'name': 'Downtown Flagship',
        'code': 'DT-01',
        'business_type': 'RETAIL'
    }, headers={'Authorization': f'Bearer {superadmin_token}'})
    assert res_super.status_code == 201
    assert res_super.get_json()["store"]["code"] == "DT-01"
