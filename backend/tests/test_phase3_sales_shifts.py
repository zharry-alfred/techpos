import pytest
from app.extensions import db
from app.models.tenant import Store, User, UserRole
from app.models.item import Item, ItemType
from app.models.stock import StockLevel
from app.models.sales import OrderStatus

def test_full_checkout_and_shift_reconciliation_flow(client, cashier_token, app):
    """End-to-end test of Cash Shift -> Order Creation -> Split Payment -> Mid-shift Drop -> Shift Close with Z-report."""
    
    # 1. Open shift with $50 opening float
    res_open = client.post('/api/v1/shifts/open', json={
        'opening_float': 50.00,
        'terminal_id': 'POS-01'
    }, headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_open.status_code == 201
    shift_id = res_open.get_json()['shift']['id']

    # Get an item to sell
    with app.app_context():
        store = Store.query.filter_by(code="TEST-01").first()
        item = Item(store_id=store.id, name="Energy Drink", sku="NRG-01", base_price=10.00, tax_rate=10.00, item_type=ItemType.PHYSICAL)
        db.session.add(item)
        db.session.flush()
        db.session.add(StockLevel(store_id=store.id, item_id=item.id, current_stock=20.0))
        db.session.commit()
        item_id = str(item.id)

    # 2. Create Order for 2 Energy Drinks ($20 + $2 tax = $22)
    res_order = client.post('/api/v1/orders', json={
        'items': [{'item_id': item_id, 'quantity': 2, 'unit_price': 10.00}],
        'order_type': 'RETAIL_QUICK'
    }, headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_order.status_code == 201
    order_data = res_order.get_json()['order']
    order_id = order_data['id']
    assert order_data['subtotal'] == 20.00
    assert order_data['tax_amount'] == 2.00
    assert order_data['grand_total'] == 22.00

    # 3. Pay Order with Split Payment: $12 Cash ($20 tendered -> $8 change) + $10 Card
    res_pay = client.post(f'/api/v1/orders/{order_id}/pay', json={
        'payments': [
            {'method': 'CASH', 'amount': 12.00, 'amount_tendered': 20.00},
            {'method': 'CARD', 'amount': 10.00, 'amount_tendered': 10.00, 'reference': 'CARD-AUTH-9988'}
        ]
    }, headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_pay.status_code == 200
    paid_order = res_pay.get_json()['order']
    assert paid_order['status'] == OrderStatus.COMPLETED
    assert len(paid_order['payments']) == 2
    assert paid_order['payments'][0]['change_returned'] == 8.00

    # 4. Check stock deduction: 20 - 2 = 18
    with app.app_context():
        stock = StockLevel.query.filter_by(item_id=item_id).first()
        assert float(stock.current_stock) == 18.0

    # 5. Log mid-shift Cash Drop ($10 moved to safe)
    res_drop = client.post('/api/v1/shifts/drop', json={
        'movement_type': 'CASH_DROP',
        'amount': 10.00,
        'reason': 'Excess drawer cash dropped to safe'
    }, headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_drop.status_code == 201
    # Expected cash: Opening Float (50) + Cash Sales (12) - Drop (10) = 52.00
    assert res_drop.get_json()['expected_cash'] == 52.00

    # 6. Check interim X-Report
    res_x = client.get('/api/v1/shifts/current', headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_x.status_code == 200
    x_rep = res_x.get_json()['x_report']
    assert x_rep['total_cash_sales'] == 12.00
    assert x_rep['total_card_sales'] == 10.00
    assert x_rep['expected_in_drawer'] == 52.00

    # 7. Close Shift with counted cash $52.00 (Balanced Z-Report)
    res_close = client.post('/api/v1/shifts/close', json={
        'closing_cash_actual': 52.00,
        'closing_notes': 'Drawer perfectly balanced'
    }, headers={'Authorization': f'Bearer {cashier_token}'})
    assert res_close.status_code == 200
    z_rep = res_close.get_json()['z_report']
    assert z_rep['status'] == 'BALANCED'
    assert z_rep['discrepancy'] == 0.00
    assert z_rep['gross_sales'] == 22.00
