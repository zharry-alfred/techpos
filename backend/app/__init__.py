from pathlib import Path
from flask import Flask, jsonify
from app.config import config_by_name
from app.extensions import db, migrate, jwt, ma, cors
from app.services.licensing_service import LicensingService

def create_app(config_name="development"):
    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Ensure cryptographic licensing keys exist
    LicensingService.ensure_keys_exist(Path(app.config["KEYS_DIR"]))

    # Import and register all blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.store_routes import store_bp
    from app.routes.item_routes import item_bp
    from app.routes.inventory_routes import inventory_bp
    from app.routes.procurement_routes import procurement_bp
    from app.routes.order_routes import order_bp
    from app.routes.shift_routes import shift_bp
    from app.routes.document_routes import document_bp
    from app.routes.kds_routes import kds_bp
    from app.routes.hardware_routes import hardware_bp
    from app.routes.sync_routes import sync_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(item_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(shift_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(kds_bp)
    app.register_blueprint(hardware_bp)
    app.register_blueprint(sync_bp)

    # Global Health Check & Spec Info
    @app.route('/api/v1/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status": "healthy",
            "version": "6.0",
            "specification": "Digital POS and Business Management Software Master Specification (v6.0)",
            "author": "Harrison Alfred Ombwayo"
        }), 200

    # JWT Error handlers
    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        return jsonify({"error": "Authorization token missing or invalid", "code": "token_missing"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired. Please log in or refresh.", "code": "token_expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(callback):
        return jsonify({"error": "Signature verification failed. Invalid token.", "code": "token_invalid"}), 401

    # Database initialization helper
    with app.app_context():
        # Auto-create tables for SQLite / Development
        db.create_all()

    return app
