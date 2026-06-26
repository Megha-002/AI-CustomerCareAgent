# reset_demo.py
"""Reset demo records for clean Loom video recording."""
import sqlite3
from pathlib import Path

db_path = str(Path(__file__).parent / "data" / "crm.db")
conn = sqlite3.connect(db_path)

# 1. Standard Approval - reset to pending, clear previous decision
#    ORD-5003 | Customer 4 (Bronze) | No fraud, 2 refunds
conn.execute("""
    UPDATE refund_requests 
    SET status = 'pending', ai_decision = NULL, manual_review_required = 0
    WHERE request_id = 'REF-7003'
""")

# 2. Fraud Rejection - keep fraud flag, ensure it's pending
#    ORD-5010 | Customer 11 (Gold) | Fraud=True, 4 refunds
conn.execute("""
    UPDATE refund_requests 
    SET status = 'pending', ai_decision = NULL
    WHERE request_id = 'REF-7010'
""")

# 3. High Value Escalation - clear fraud so it escalates for RIGHT reason
#    ORD-5025 | Customer 11 (Gold) | ₹72,000
conn.execute("""
    UPDATE refund_history 
    SET fraud_flag = 0, refund_count = 1
    WHERE customer_id = 'CUST-1010'
""")
conn.execute("""
    UPDATE refund_requests 
    SET status = 'pending', ai_decision = NULL
    WHERE request_id = 'REF-7025'
""")

# 4. Damaged Product Escalation - clear fraud so it escalates for damage
#    ORD-5027 | Customer 13 (Gold) | damage_reported=True
conn.execute("""
    UPDATE refund_history 
    SET fraud_flag = 0, refund_count = 1
    WHERE customer_id = 'CUST-1012'
""")
conn.execute("""
    UPDATE refund_requests 
    SET status = 'pending', ai_decision = NULL
    WHERE request_id = 'REF-7027'
""")

# Clear escalation queue from previous test runs
conn.execute("DELETE FROM escalation_queue")

conn.commit()
conn.close()
print("Done! Demo records reset.")
print()
print("Standard Approval: REF-7003 → pending, clean")
print("Fraud Rejection:    REF-7010 → pending, fraud=TRUE")
print("High Value:         REF-7025 → pending, fraud=FALSE, ₹72,000")
print("Damaged Product:    REF-7027 → pending, fraud=FALSE, damage=TRUE")