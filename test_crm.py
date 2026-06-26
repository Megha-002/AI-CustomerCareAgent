# test_crm.py
"""Integration test for crm_lookup.py using actual string IDs."""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tools"))
from crm_lookup import (
    get_customer,
    get_order,
    get_refund_request,
    get_refund_history,
    get_complete_case,
    get_customer_orders,
    get_customer_refund_requests,
    get_all_pending_requests
)


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ─── Helper: Get all IDs from a table ───────────────────────
def get_all_ids(table: str, id_column: str) -> list:
    db_path = str(Path(__file__).parent / "data" / "crm.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(f"SELECT {id_column} FROM {table}")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids


# ─── Test 1: Database Overview ──────────────────────────────
print_section("TEST 1: Database Overview")

db_path = str(Path(__file__).parent / "data" / "crm.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
for table in ["customers", "orders", "refund_requests", "refund_history"]:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")
conn.close()

# Get actual IDs
customer_ids = get_all_ids("customers", "customer_id")
order_ids = get_all_ids("orders", "order_id")
request_ids = get_all_ids("refund_requests", "request_id")

print(f"\n  Sample Customer IDs: {customer_ids[:3]}...")
print(f"  Sample Order IDs: {order_ids[:3]}...")
print(f"  Sample Request IDs: {request_ids[:3]}...")


# ─── Test 2: Customer Lookups ───────────────────────────────
print_section("TEST 2: Customer Lookups")

# Test first 5 customers
for cid in customer_ids[:5]:
    customer = get_customer(cid)
    if customer:
        print(f"  ✅ {cid}: {customer['name']} ({customer['tier']})")
    else:
        print(f"  ❌ {cid}: FAILED")

# Test edge case
print(f"\n  Non-existent: {get_customer('CUST-9999')}")


# ─── Test 3: Order Lookups ──────────────────────────────────
print_section("TEST 3: Order Lookups")

categories_seen = set()
for oid in order_ids[:10]:
    order = get_order(oid)
    if order:
        categories_seen.add(order['product_category'])
        print(f"  ✅ {oid}: {order['product_category']} | ${order['purchase_amount']:.2f} | {order['shipping_status']}")
    else:
        print(f"  ❌ {oid}: FAILED")

print(f"\n  Categories found: {categories_seen}")


# ─── Test 4: Refund Request Lookups ─────────────────────────
print_section("TEST 4: Refund Request Lookups")

decision_counts = {}
for rid in request_ids:
    req = get_refund_request(rid)
    if req:
        decision = req.get('ai_decision') or 'NULL'
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

for decision, count in sorted(decision_counts.items()):
    print(f"  {decision}: {count}")

# Show first 3 in detail
for rid in request_ids[:3]:
    req = get_refund_request(rid)
    print(f"\n  {rid}: {req['refund_reason']} → {req['ai_decision']} ({req['status']})")


# ─── Test 5: Refund History ─────────────────────────────────
print_section("TEST 5: Refund History Lookups")

for cid in customer_ids[:5]:
    history = get_refund_history(cid)
    if history:
        print(f"  ✅ {cid}: {history['refund_count']} refunds, fraud={history['fraud_flag']}")
    else:
        print(f"  ❌ {cid}: No history found")


# ─── Test 6: Complete Case (Critical Path) ──────────────────
print_section("TEST 6: Complete Case")

for rid in request_ids[:5]:
    case = get_complete_case(rid)
    if case:
        c = case['customer']
        o = case['order']
        r = case['refund_request']
        h = case['refund_history']
        print(f"\n  ✅ {rid}:")
        print(f"     Customer: {c['name']} ({c['tier']})")
        print(f"     Order: {o['order_id']} | {o['product_category']} | ${o['purchase_amount']:.2f}")
        print(f"     Reason: {r['refund_reason']}")
        print(f"     Decision: {r['ai_decision']} | Status: {r['status']}")
        print(f"     Fraud: {h['fraud_flag']} | Prior Refunds: {h['refund_count']}")
    else:
        print(f"  ❌ {rid}: FAILED")

print(f"\n  Non-existent: {get_complete_case('REF-9999')}")


# ─── Test 7: Customer Orders ────────────────────────────────
print_section("TEST 7: Customer Orders")

for cid in customer_ids[:3]:
    orders = get_customer_orders(cid)
    print(f"  {cid}: {len(orders)} orders")
    for o in orders[:3]:
        print(f"    {o['order_id']} | {o['product_category']} | ${o['purchase_amount']:.2f}")


# ─── Test 8: Customer Refund Requests ───────────────────────
print_section("TEST 8: Customer Refund Requests")

for cid in customer_ids[:3]:
    requests = get_customer_refund_requests(cid)
    print(f"  {cid}: {len(requests)} refund requests")
    for r in requests[:3]:
        print(f"    {r['request_id']} | {r['refund_reason']} | {r['status']}")


# ─── Test 9: Pending Requests ───────────────────────────────
print_section("TEST 9: Pending Requests")

pending = get_all_pending_requests()
print(f"  Pending requests: {len(pending)}")
for case in pending[:5]:
    print(f"    {case['refund_request']['request_id']}: {case['refund_request']['refund_reason']}")


# ─── Summary ────────────────────────────────────────────────
print_section("SUMMARY")
print("\n  If you see ✅ for all lookups, crm_lookup.py is working correctly.")
print("  Any ❌ means there's still a mismatch to fix.")