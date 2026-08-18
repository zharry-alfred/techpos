from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
from app.extensions import db
from app.models.tenant import Store, User, UserRole

auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user with email and password, returning JWT access & refresh tokens."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    store_code = data.get('store_code', '').strip().upper()

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    query = User.query.filter_by(email=email)
    if store_code:
        store = Store.query.filter_by(code=store_code).first()
        if not store:
            return jsonify({"error": "Store code not found"}), 404
        query = query.filter_by(store_id=store.id)

    user = query.first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    if not user.is_active:
        return jsonify({"error": "User account is deactivated"}), 403

    store = Store.query.get(user.store_id)

    # Prepare claims
    additional_claims = {
        "store_id": str(user.store_id),
        "store_code": store.code if store else None,
        "store_name": store.name if store else None,
        "business_type": store.business_type if store else None,
        "role": user.role,
        "email": user.email,
        "full_name": user.full_name,
        "is_license_active": store.is_license_active if store else False,
    }

    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=additional_claims)

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
        "store": store.to_dict() if store else None
    }), 200

@auth_bp.route('/pin-login', methods=['POST'])
def pin_login():
    """Fast PIN login for POS terminals (Cashiers/Managers switching on same terminal)."""
    data = request.get_json() or {}
    store_code = data.get('store_code', '').strip().upper()
    pin = data.get('pin', '').strip()

    if not store_code or not pin:
        return jsonify({"error": "Store code and PIN are required"}), 400

    store = Store.query.filter_by(code=store_code).first()
    if not store:
        return jsonify({"error": "Store not found"}), 404

    users = User.query.filter_by(store_id=store.id, is_active=True).all()
    matched_user = None
    for u in users:
        if u.check_pin(pin):
            matched_user = u
            break

    if not matched_user:
        return jsonify({"error": "Invalid PIN"}), 401

    additional_claims = {
        "store_id": str(matched_user.store_id),
        "store_code": store.code,
        "store_name": store.name,
        "business_type": store.business_type,
        "role": matched_user.role,
        "email": matched_user.email,
        "full_name": matched_user.full_name,
        "is_license_active": store.is_license_active,
    }

    access_token = create_access_token(identity=str(matched_user.id), additional_claims=additional_claims)

    return jsonify({
        "message": f"PIN login successful for {matched_user.full_name}",
        "access_token": access_token,
        "user": matched_user.to_dict(),
        "store": store.to_dict()
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using a valid refresh token."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return jsonify({"error": "User no longer active"}), 401

    store = Store.query.get(user.store_id)
    additional_claims = {
        "store_id": str(user.store_id),
        "store_code": store.code if store else None,
        "store_name": store.name if store else None,
        "business_type": store.business_type if store else None,
        "role": user.role,
        "email": user.email,
        "full_name": user.full_name,
        "is_license_active": store.is_license_active if store else False,
    }

    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    return jsonify({"access_token": access_token}), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """Retrieve the current user profile and tenant store details."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    store = Store.query.get(user.store_id)
    return jsonify({
        "user": user.to_dict(),
        "store": store.to_dict() if store else None
    }), 200
