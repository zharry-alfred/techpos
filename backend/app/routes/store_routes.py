from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.tenant import Store, User, UserRole, BusinessType
from app.models.hardware import StoreHardwareConfig
from app.utils.auth_guards import role_required, get_current_tenant_id
from app.utils.hardware_fingerprint import get_hardware_fingerprint
from app.services.licensing_service import LicensingService

store_bp = Blueprint('stores', __name__, url_prefix='/api/v1/stores')

@store_bp.route('/hardware-fingerprint', methods=['GET'])
def get_fingerprint():
    """Retrieve host machine hardware fingerprint for license binding."""
    fingerprint = get_hardware_fingerprint()
    return jsonify({"hardware_fingerprint": fingerprint}), 200

@store_bp.route('', methods=['GET'])
@jwt_required()
def list_stores():
    """List stores: Super Admin sees all tenants, others see only their own store."""
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    role = claims.get('role')
    user_store_id = claims.get('store_id')

    if role == UserRole.SUPER_ADMIN:
        stores = Store.query.all()
    else:
        stores = Store.query.filter_by(id=user_store_id).all()

    return jsonify({"stores": [s.to_dict() for s in stores]}), 200

@store_bp.route('', methods=['POST'])
@jwt_required()
@role_required(UserRole.SUPER_ADMIN)
def create_store():
    """Super Admin: Provision a new merchant store / tenant."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip().upper()
    business_type = data.get('business_type', BusinessType.RETAIL)

    if not name or not code:
        return jsonify({"error": "Store name and unique code are required"}), 400

    if business_type not in BusinessType.ALL:
        return jsonify({"error": f"Invalid business_type. Must be one of: {BusinessType.ALL}"}), 400

    if Store.query.filter_by(code=code).first():
        return jsonify({"error": f"Store code '{code}' is already in use"}), 409

    store = Store(
        name=name,
        code=code,
        business_type=business_type,
        currency_code=data.get('currency_code', 'USD'),
        tax_number=data.get('tax_number'),
        address=data.get('address'),
        phone=data.get('phone'),
        receipt_header=data.get('receipt_header', f"=== {name} ==="),
        receipt_footer=data.get('receipt_footer', "Thank you for your business!")
    )
    db.session.add(store)
    db.session.flush()

    # Create default hardware config
    hw_config = StoreHardwareConfig(
        store_id=store.id,
        printer_interface='USB',
        cash_drawer_pin=2,
        enable_scale_reader=False,
        enable_cfd=True
    )
    db.session.add(hw_config)

    # If admin credentials provided, create initial Store Admin user
    admin_email = data.get('admin_email')
    admin_password = data.get('admin_password')
    admin_name = data.get('admin_name', f"{name} Admin")
    if admin_email and admin_password:
        admin_user = User(
            store_id=store.id,
            email=admin_email.strip().lower(),
            full_name=admin_name,
            role=UserRole.STORE_ADMIN
        )
        admin_user.set_password(admin_password)
        db.session.add(admin_user)

    db.session.commit()
    return jsonify({
        "message": "Store provisioned successfully",
        "store": store.to_dict()
    }), 201

@store_bp.route('/<store_id>', methods=['GET'])
@jwt_required()
def get_store(store_id):
    """Get single store details."""
    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404
    return jsonify({"store": store.to_dict()}), 200

@store_bp.route('/<store_id>', methods=['PUT'])
@jwt_required()
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN)
def update_store(store_id):
    """Update store details."""
    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404

    data = request.get_json() or {}
    if 'name' in data:
        store.name = data['name'].strip()
    if 'business_type' in data and data['business_type'] in BusinessType.ALL:
        store.business_type = data['business_type']
    if 'currency_code' in data:
        store.currency_code = data['currency_code']
    if 'tax_number' in data:
        store.tax_number = data['tax_number']
    if 'address' in data:
        store.address = data['address']
    if 'phone' in data:
        store.phone = data['phone']
    if 'receipt_header' in data:
        store.receipt_header = data['receipt_header']
    if 'receipt_footer' in data:
        store.receipt_footer = data['receipt_footer']

    db.session.commit()
    return jsonify({"message": "Store updated successfully", "store": store.to_dict()}), 200

@store_bp.route('/<store_id>/license/issue', methods=['POST'])
@jwt_required()
@role_required(UserRole.SUPER_ADMIN)
def issue_store_license(store_id):
    """Super Admin: Issue a cryptographically signed Ed25519 license key."""
    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404

    data = request.get_json() or {}
    hw_fingerprint = data.get('hardware_fingerprint') or get_hardware_fingerprint()
    days_valid = int(data.get('days_valid', 365))
    tier = data.get('tier', 'ENTERPRISE')
    allowed_modules = data.get('allowed_modules', ["RETAIL", "FOOD_BEVERAGE", "INVENTORY", "KDS", "CFD", "OFFLINE_SYNC"])
    max_terminals = int(data.get('max_terminals', 10))

    priv_key_path = current_app.config["ED25519_PRIVATE_KEY_PATH"]
    
    license_result = LicensingService.issue_license(
        store_id=store.id,
        store_code=store.code,
        hardware_fingerprint=hw_fingerprint,
        private_key_path=priv_key_path,
        days_valid=days_valid,
        tier=tier,
        allowed_modules=allowed_modules,
        max_terminals=max_terminals
    )

    return jsonify({
        "message": f"License certificate issued for store '{store.name}'",
        "store_id": str(store.id),
        "license_key": license_result["license_key"],
        "certificate": license_result["certificate"],
        "expires_at": license_result["expires_at"]
    }), 200

@store_bp.route('/<store_id>/license/activate', methods=['POST'])
@jwt_required()
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN)
def activate_store_license(store_id):
    """Validate and activate cryptographic license locally on the store terminal."""
    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404

    data = request.get_json() or {}
    license_input = data.get('license_key') or data.get('certificate')
    enforce_hardware = data.get('enforce_hardware', True)

    if not license_input:
        return jsonify({"error": "License key or certificate payload is required"}), 400

    pub_key_path = current_app.config["ED25519_PUBLIC_KEY_PATH"]
    validation = LicensingService.verify_license(
        license_data=license_input,
        public_key_path=pub_key_path,
        expected_store_id=str(store.id),
        enforce_hardware=enforce_hardware
    )

    if not validation.get("valid"):
        return jsonify({
            "error": "License activation rejected",
            "reason": validation.get("error")
        }), 400

    # Activate store license
    payload = validation["payload"]
    store.license_key = data.get('license_key') if isinstance(license_input, str) else str(license_input)
    store.is_license_active = True
    store.hardware_fingerprint = payload.get("hardware_fingerprint")
    store.license_expires_at = validation["expires_at"]
    db.session.commit()

    return jsonify({
        "message": f"Store '{store.name}' license activated successfully!",
        "is_license_active": True,
        "expires_at": store.license_expires_at.isoformat(),
        "tier": payload.get("tier"),
        "allowed_modules": payload.get("allowed_modules")
    }), 200

@store_bp.route('/<store_id>/users', methods=['GET'])
@jwt_required()
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def list_store_users(store_id):
    """List staff members of a specific store."""
    users = User.query.filter_by(store_id=store_id).all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200

@store_bp.route('/<store_id>/users', methods=['POST'])
@jwt_required()
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN)
def create_store_user(store_id):
    """Create a new user (Manager, Cashier, Staff) for a store."""
    store = Store.query.get(store_id)
    if not store:
        return jsonify({"error": "Store not found"}), 404

    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    role = data.get('role', UserRole.CASHIER)
    pin = data.get('pin')

    if not email or not password or not full_name:
        return jsonify({"error": "Email, password, and full name are required"}), 400

    if role not in UserRole.ALL or role == UserRole.SUPER_ADMIN:
        return jsonify({"error": f"Invalid role: {role}"}), 400

    if User.query.filter_by(store_id=store_id, email=email).first():
        return jsonify({"error": f"User with email '{email}' already exists in this store"}), 409

    user = User(
        store_id=store.id,
        email=email,
        full_name=full_name,
        role=role
    )
    user.set_password(password)
    if pin:
        user.set_pin(pin)

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": f"User '{user.full_name}' ({user.role}) created successfully",
        "user": user.to_dict()
    }), 201
