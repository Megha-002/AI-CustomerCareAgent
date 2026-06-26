"""Discover the correct ID combinations for demo scenarios."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tools.crm_lookup import get_customer, get_order, get_refund_request, get_refund_history, get_complete_case

print("=" * 80)
print("CUSTOMER LIST (with fraud/refund info)")
print("=" * 80)
for i in range(15):
    cid = f"CUST-{1000+i}"
    customer = get_customer(cid)
    history = get_refund_history(cid)
    if customer and history:
        print(f"{customer['customer_id']} | {customer['name']:<12} | Tier: {customer['tier']:<8} | Fraud: {history['fraud_flag']} | Refunds: {history['refund_count']}")

print()
print("=" * 80)
print("REFUND REQUESTS (with key flags)")
print("=" * 80)
for i in range(34):
    rid = f"REF-{7000+i}"
    req = get_refund_request(rid)
    if req:
        order = get_order(req['order_id'])
        customer = get_customer(order['customer_id']) if order else None
        print(f"{req['request_id']} | Order: {req['order_id']} | {req['refund_reason']:<20} | Damage: {req['damage_reported']} | Wrong: {req['wrong_item_received']} | Receipt: {req['receipt_available']} | Status: {req['status']} | Tier: {customer['tier'] if customer else '?'}")

print()
print("=" * 80)
print("HIGH VALUE ORDERS (> ₹50,000)")
print("=" * 80)
for i in range(50):
    oid = f"ORD-{5000+i}"
    order = get_order(oid)
    if order and order['purchase_amount'] > 50000:
        print(f"{order['order_id']} | {order['product_category']} | ₹{order['purchase_amount']:,.2f} | {order['shipping_status']}")

print()
print("=" * 80)
print("SAMPLE COMPLETE CASES")
print("=" * 80)
sample_ids = ["REF-7000", "REF-7005", "REF-7010", "REF-7015", "REF-7020", "REF-7025", "REF-7030"]
for rid in sample_ids:
    case = get_complete_case(rid)
    if case:
        c = case['customer']
        o = case['order']
        r = case['refund_request']
        h = case['refund_history']
        print(f"\n{rid}: {c['name']} ({c['tier']}) | {o['product_category']} | ₹{o['purchase_amount']:,.2f}")
        print(f"  Reason: {r['refund_reason']} | Damage: {r['damage_reported']} | Receipt: {r['receipt_available']} | Fraud: {h['fraud_flag']} | Refunds: {h['refund_count']}")