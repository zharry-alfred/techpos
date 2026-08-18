from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.models.sync import OfflineSyncQueue
from app.services.sync_service import SyncService
from app.utils.auth_guards import get_current_tenant_id, active_license_required

sync_bp = Blueprint('sync', __name__, url_prefix='/api/v1/sync')

@sync_bp.route('/push', methods=['POST'])
@jwt_required()
@active_license_required
def push_sync_queue():
    """Receive offline transactions queue batch and process them idempotently."""
    store_id = get_current_tenant_id()
    data = request.get_json() or {}
    items = data.get('items', [])

    if not items:
        return jsonify({"message": "No sync items provided", "synced_count": 0}), 200

    result = SyncService.process_sync_batch(store_id=store_id, queue_items=items)
    return jsonify({
        "message": f"Sync batch processed: {result['synced_count']} synced, {result['failed_count']} failed",
        "result": result
    }), 200

@sync_bp.route('/queue', methods=['GET'])
@jwt_required()
@active_license_required
def get_sync_queue_status():
    """Check sync queue records."""
    store_id = get_current_tenant_id()
    records = OfflineSyncQueue.query.filter_by(store_id=store_id).order_by(OfflineSyncQueue.created_at.desc()).limit(100).all()
    return jsonify({"queue": [r.to_dict() for r in records]}), 200
