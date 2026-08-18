from app.extensions import db
from app.models.base import GUID, CrossJSON, generate_uuid, utc_now

class ItemType:
    PHYSICAL = 'PHYSICAL'
    SERVICE = 'SERVICE'
    COMPOSITE_RECIPE = 'COMPOSITE_RECIPE'
    ALL = [PHYSICAL, SERVICE, COMPOSITE_RECIPE]

class ItemCategory(db.Model):
    __tablename__ = 'item_categories'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(GUID, db.ForeignKey('item_categories.id', ondelete='SET NULL'), nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    parent = db.relationship('ItemCategory', remote_side=[id], backref='children')
    items = db.relationship('Item', back_populates='category')

    def to_dict(self):
        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'name': self.name,
            'parent_id': str(self.parent_id) if self.parent_id else None,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    store_id = db.Column(GUID, db.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(GUID, db.ForeignKey('item_categories.id', ondelete='SET NULL'), nullable=True)
    
    sku = db.Column(db.String(100), nullable=True)
    barcode = db.Column(db.String(100), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    item_type = db.Column(db.String(50), default=ItemType.PHYSICAL, nullable=False) # PHYSICAL, SERVICE, COMPOSITE_RECIPE
    base_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.00)
    cost_price = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    track_inventory = db.Column(db.Boolean, default=True, nullable=False)
    tax_rate = db.Column(db.Numeric(5, 2), default=0.00, nullable=False) # e.g. 16.00 for 16% VAT
    
    # Metadata for SKU variants, F&B station routing (Grill, Bar), modifiers, images
    metadata_json = db.Column('metadata', CrossJSON, default=dict, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    category = db.relationship('ItemCategory', back_populates='items')
    stock_levels = db.relationship('StockLevel', back_populates='item', cascade='all, delete-orphan')
    recipe_ingredients = db.relationship('RecipeIngredient', foreign_keys='RecipeIngredient.composite_item_id', back_populates='composite_item', cascade='all, delete-orphan')

    def to_dict(self, include_stock=True):
        stock_qty = 0.0
        low_stock_threshold = 5.0
        if include_stock and self.stock_levels:
            stock_qty = sum(float(sl.current_stock) for sl in self.stock_levels)
            low_stock_threshold = float(self.stock_levels[0].low_stock_threshold) if self.stock_levels else 5.0

        return {
            'id': str(self.id),
            'store_id': str(self.store_id),
            'category_id': str(self.category_id) if self.category_id else None,
            'category_name': self.category.name if self.category else None,
            'sku': self.sku,
            'barcode': self.barcode,
            'name': self.name,
            'description': self.description,
            'item_type': self.item_type,
            'base_price': float(self.base_price),
            'cost_price': float(self.cost_price),
            'track_inventory': self.track_inventory,
            'tax_rate': float(self.tax_rate),
            'metadata': self.metadata_json or {},
            'is_active': self.is_active,
            'current_stock': stock_qty,
            'low_stock_threshold': low_stock_threshold,
            'is_low_stock': stock_qty <= low_stock_threshold if self.track_inventory and self.item_type == ItemType.PHYSICAL else False,
            'ingredients': [ing.to_dict() for ing in self.recipe_ingredients] if self.item_type == ItemType.COMPOSITE_RECIPE else [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class RecipeIngredient(db.Model):
    """Composite Recipe ingredient mapping: defines raw materials deducted when composite item is ordered."""
    __tablename__ = 'recipe_ingredients'

    id = db.Column(GUID, primary_key=True, default=generate_uuid)
    composite_item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    ingredient_item_id = db.Column(GUID, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    quantity_required = db.Column(db.Numeric(10, 4), nullable=False, default=1.0)
    unit_of_measure = db.Column(db.String(50), default='units', nullable=False) # e.g. 'g', 'ml', 'pcs', 'slice'

    composite_item = db.relationship('Item', foreign_keys=[composite_item_id], back_populates='recipe_ingredients')
    ingredient_item = db.relationship('Item', foreign_keys=[ingredient_item_id])

    def to_dict(self):
        return {
            'id': str(self.id),
            'composite_item_id': str(self.composite_item_id),
            'ingredient_item_id': str(self.ingredient_item_id),
            'ingredient_name': self.ingredient_item.name if self.ingredient_item else None,
            'quantity_required': float(self.quantity_required),
            'unit_of_measure': self.unit_of_measure
        }
