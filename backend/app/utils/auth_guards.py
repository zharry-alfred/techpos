from functools import wraps
from flask import jsonify, current_app, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from app.models.tenant import Store, User, UserRole

def get_current_user_id() -> str:
    """Return the user ID from the verified JWT identity."""
    return get_jwt_identity()

def get_current_claims() -> dict:
    """Return the decoded JWT claims dictionary."""
    return get_jwt()

def get_current_tenant_id() -> str:
    """Return the store_id (tenant ID) associated with the current request."""
    claims = get_jwt()
    return claims.get("store_id")

def role_required(*allowed_roles):
    """Decorator to enforce Role-Based Access Control (RBAC).
    If SUPER_ADMIN is among allowed_roles or the user is SUPER_ADMIN, access is granted.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_role = claims.get("role")
            
            # Super Admin has global bypass
            if user_role == UserRole.SUPER_ADMIN:
                return fn(*args, **kwargs)
            
            if allowed_roles and user_role not in allowed_roles:
                return jsonify({
                    "error": "Forbidden: Insufficient permissions for this resource",
                    "required_roles": list(allowed_roles),
                    "user_role": user_role
                }), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def active_license_required(fn):
    """Decorator to verify that the target store has an active cryptographic license.
    Super Admins are exempt from license checks.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        user_role = claims.get("role")
        
        if user_role == UserRole.SUPER_ADMIN:
            return fn(*args, **kwargs)
            
        store_id = claims.get("store_id")
        if not store_id:
            return jsonify({"error": "Unauthorized: No tenant store associated with token"}), 401
            
        store = Store.query.get(store_id)
        if not store:
            return jsonify({"error": "Store not found"}), 404
            
        if not store.is_license_active:
            return jsonify({
                "error": "License Inactive: This store does not have an active POS license. Contact Super Admin."
            }), 403
            
        return fn(*args, **kwargs)
    return wrapper
