# check_demo_cases.py
from tools.crm_lookup import get_complete_case

cases = [
    ('REF-7003', 'Standard Approval'),
    ('REF-7010', 'Fraud Rejection'),
    ('REF-7025', 'High Value'),
    ('REF-7027', 'Damaged Product'),
]

for rid, label in cases:
    case = get_complete_case(rid)
    if case:
        c = case['customer']
        o = case['order']
        r = case['refund_request']
        h = case['refund_history']
        print(f'=== {label} ===')
        print(f'Request: {rid} | Order: {o["order_id"]} | Customer: {c["name"]} ({c["tier"]})')
        print(f'Product: {o["product_category"]} | Amount: {o["purchase_amount"]:,.2f} | Shipping: {o["shipping_status"]}')
        print(f'Reason: {r["refund_reason"]} | Damage: {r["damage_reported"]} | Receipt: {r["receipt_available"]}')
        print(f'Fraud: {h["fraud_flag"]} | Refunds: {h["refund_count"]} | Status: {r["status"]}')
        print(f'Return Window: {o["return_window_days"]} days')
        print()
    else:
        print(f'=== {label} ===')
        print(f'NOT FOUND: {rid}')
        print()