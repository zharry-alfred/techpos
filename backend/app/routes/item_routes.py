from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models.tenant import UserRole
from app.models.item import Item, ItemCategory, ItemType, RecipeIngredient
from app.models.stock import StockLevel
from app.utils.auth_guards import role_required, get_current_tenant_id, active_license_required

item_bp = Blueprint('items', __name__, url_prefix='/api/v1/items')

@item_bp.route('/categories', methods=['GET'])
@jwt_required()
@active_license_required
def list_categories():
    """List item categories for the store."""
    store_id = get_current_tenant_id()
    categories = ItemCategory.query.filter_by(store_id=store_id).order_by(ItemCategory.sort_order).all()
    return jsonify({"categories": [c.to_dict() for c in categories]}), 200

@item_bp.route('/categories', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def create_category():
    """Create a new item category."""
    store_id = get_current_tenant_id()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"error": "Category name is required"}), 400

    category = ItemCategory(
        store_id=store_id,
        name=name,
        parent_id=data.get('parent_id'),
        sort_order=data.get('sort_order', 0)
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({"message": "Category created", "category": category.to_dict()}), 201

@item_bp.route('', methods=['GET'])
@jwt_required()
@active_license_required
def list_items():
    """Fetch merchant catalog with filtering (search, barcode, category, item_type)."""
    store_id = get_current_tenant_id()
    query = Item.query.filter_by(store_id=store_id, is_active=True)

    barcode = request.args.get('barcode')
    if barcode:
        item = query.filter_by(barcode=barcode.strip()).first()
        if item:
            return jsonify({"item": item.to_dict()}), 200
        return jsonify({"error": "Item not found for barcode"}), 404

    search = request.args.get('search')
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter((Item.name.ilike(search_term)) | (Item.sku.ilike(search_term)) | (Item.barcode.ilike(search_term)))

    category_id = request.args.get('category_id')
    if category_id:
        query = query.filter_by(category_id=category_id)

    item_type = request.args.get('item_type')
    if item_type and item_type in ItemType.ALL:
        query = query.filter_by(item_type=item_type)

    items = query.order_by(Item.name).all()
    return jsonify({"items": [item.to_dict() for item in items]}), 200

@item_bp.route('', methods=['POST'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def create_item():
    """Create a new item/service/composite recipe in the merchant catalog."""
    store_id = get_current_tenant_id()
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    base_price = data.get('base_price')

    if not name or base_price is None:
        return jsonify({"error": "Item name and base_price are required"}), 400

    item_type = data.get('item_type', ItemType.PHYSICAL)
    if item_type not in ItemType.ALL:
        return jsonify({"error": f"Invalid item_type. Must be one of: {ItemType.ALL}"}), 400

    item = Item(
        store_id=store_id,
        category_id=data.get('category_id'),
        sku=data.get('sku'),
        barcode=data.get('barcode'),
        name=name,
        description=data.get('description'),
        item_type=item_type,
        base_price=float(base_price),
        cost_price=float(data.get('cost_price', 0.00)),
        track_inventory=bool(data.get('track_inventory', True)),
        tax_rate=float(data.get('tax_rate', 0.00)),
        metadata_json=data.get('metadata', {})
    )
    db.session.add(item)
    db.session.flush()

    # Initial stock level if physical item
    initial_stock = data.get('initial_stock')
    low_stock_threshold = data.get('low_stock_threshold', 5.0)
    if item.track_inventory and item.item_type == ItemType.PHYSICAL:
        stock = StockLevel(
            store_id=store_id,
            item_id=item.id,
            current_stock=float(initial_stock) if initial_stock is not None else 0.0,
            low_stock_threshold=float(low_stock_threshold),
            batch_number=data.get('batch_number', 'DEFAULT')
        )
        db.session.add(stock)

    # Ingredients if composite recipe
    ingredients = data.get('ingredients', [])
    if item.item_type == ItemType.COMPOSITE_RECIPE and ingredients:
        for ing in ingredients:
            recipe_ing = RecipeIngredient(
                composite_item_id=item.id,
                ingredient_item_id=ing['ingredient_item_id'],
                quantity_required=float(ing.get('quantity_required', 1.0)),
                unit_of_measure=ing.get('unit_of_measure', 'units')
            )
            db.session.add(recipe_ing)

    db.session.commit()
    return jsonify({
        "message": f"Item '{item.name}' created successfully",
        "item": item.to_dict()
    }), 201

@item_bp.route('/<item_id>', methods=['GET'])
@jwt_required()
@active_license_required
def get_item(item_id):
    """Retrieve single item details."""
    store_id = get_current_tenant_id()
    item = Item.query.filter_by(id=item_id, store_id=store_id).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    return jsonify({"item": item.to_dict()}), 200

@item_bp.route('/<item_id>', methods=['PUT'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN, UserRole.STORE_MANAGER)
def update_item(item_id):
    """Update item catalog details and recipe formulas."""
    store_id = get_current_tenant_id()
    item = Item.query.filter_by(id=item_id, store_id=store_id).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json() or {}
    if 'name' in data:
        item.name = data['name'].strip()
    if 'sku' in data:
        item.sku = data['sku']
    if 'barcode' in data:
        item.barcode = data['barcode']
    if 'description' in data:
        item.description = data['description']
    if 'base_price' in data:
        item.base_price = float(data['base_price'])
    if 'cost_price' in data:
        item.cost_price = float(data['cost_price'])
    if 'track_inventory' in data:
        item.track_inventory = bool(data['track_inventory'])
    if 'tax_rate' in data:
        item.tax_rate = float(data['tax_rate'])
    if 'category_id' in data:
        item.category_id = data['category_id']
    if 'metadata' in data:
        item.metadata_json = data['metadata']

    # Update recipe ingredients if provided
    if item.item_type == ItemType.COMPOSITE_RECIPE and 'ingredients' in data:
        RecipeIngredient.query.filter_by(composite_item_id=item.id).delete()
        for ing in data['ingredients']:
            recipe_ing = RecipeIngredient(
                composite_item_id=item.id,
                ingredient_item_id=ing['ingredient_item_id'],
                quantity_required=float(ing.get('quantity_required', 1.0)),
                unit_of_measure=ing.get('unit_of_measure', 'units')
            )
            db.session.add(recipe_ing)

    db.session.commit()
    return jsonify({"message": "Item updated successfully", "item": item.to_dict()}), 200

@item_bp.route('/<item_id>', methods=['DELETE'])
@jwt_required()
@active_license_required
@role_required(UserRole.SUPER_ADMIN, UserRole.STORE_ADMIN)
def delete_item(item_id):
    """Soft-delete item."""
    store_id = get_current_tenant_id()
    item = Item.query.filter_by(id=item_id, store_id=store_id).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    item.is_active = False
    db.session.commit()
    return jsonify({"message": f"Item '{item.name}' deleted"}), 200
