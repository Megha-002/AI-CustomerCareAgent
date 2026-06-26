# tools/crm_update.py
"""
CRM Update Tool - Writes agent decisions back to the database.

Updates refund_requests (status, ai_decision) and refund_history 
(refund_count, last_refund_date, fraud_flag) after a decision is made.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


# ─── Database Connection ────────────────────────────────────

def _get_db_path() -> str:
    """Resolve database path relative to project root."""
    return str(Path(__file__).parent.parent / "data" / "crm.db")


def _get_connection():
    """Create a new database connection."""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ─── Update Functions ───────────────────────────────────────

def update_refund_request_status(
    request_id: str,
    decision: str,
    status: str
) -> bool:
    """
    Update the refund request with the agent's decision.
    
    Args:
        request_id: String ID like 'REF-7000'
        decision: 'approve', 'reject', or 'escalate'
        status: 'approved', 'rejected', or 'pending' (for escalated)
    
    Returns:
        True if update succeeded, False otherwise.
    """
    valid_decisions = {"approve", "reject", "escalate"}
    valid_statuses = {"approved", "rejected", "pending"}
    
    if decision not in valid_decisions:
        raise ValueError(f"Invalid decision: {decision}. Must be one of {valid_decisions}")
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
    
    with _get_connection() as conn:
        cursor = conn.execute(
            """UPDATE refund_requests 
               SET ai_decision = ?, status = ?, manual_review_required = ?
               WHERE request_id = ?""",
            (decision, status, False, request_id)  # Clear manual review flag on decision
        )
        conn.commit()
        return cursor.rowcount > 0


def update_refund_history_after_approval(customer_id: str) -> bool:
    """
    Increment refund count and update last_refund_date after approval.
    
    Args:
        customer_id: String ID like 'CUST-1000'
    
    Returns:
        True if update succeeded.
    """
    with _get_connection() as conn:
        # Check if history record exists
        cursor = conn.execute(
            "SELECT customer_id FROM refund_history WHERE customer_id = ?",
            (customer_id,)
        )
        exists = cursor.fetchone()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        if exists:
            cursor = conn.execute(
                """UPDATE refund_history 
                   SET refund_count = refund_count + 1,
                       last_refund_date = ?
                   WHERE customer_id = ?""",
                (now, customer_id)
            )
        else:
            cursor = conn.execute(
                """INSERT INTO refund_history (customer_id, refund_count, last_refund_date, fraud_flag)
                   VALUES (?, 1, ?, 0)""",
                (customer_id, now)
            )
        
        conn.commit()
        return cursor.rowcount > 0


def update_fraud_flag(customer_id: str, fraud_flag: bool) -> bool:
    """
    Set or clear the fraud flag for a customer.
    Called when suspicious behavior is detected.
    
    Args:
        customer_id: String ID like 'CUST-1000'
        fraud_flag: True to flag, False to clear
    
    Returns:
        True if update succeeded.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            "UPDATE refund_history SET fraud_flag = ? WHERE customer_id = ?",
            (int(fraud_flag), customer_id)
        )
        
        if cursor.rowcount == 0:
            # No history record exists, create one
            cursor = conn.execute(
                """INSERT INTO refund_history (customer_id, refund_count, last_refund_date, fraud_flag)
                   VALUES (?, 0, NULL, ?)""",
                (customer_id, int(fraud_flag))
            )
        
        conn.commit()
        return cursor.rowcount > 0


def process_decision(
    request_id: str,
    customer_id: str,
    decision: str
) -> Dict[str, Any]:
    """
    Process the final decision - updates both refund_requests and refund_history.
    
    This is the main function called by the LangGraph action node.
    
    Args:
        request_id: String ID like 'REF-7000'
        customer_id: String ID like 'CUST-1000'
        decision: 'approve', 'reject', or 'escalate'
    
    Returns:
        Dict with update results
    """
    results = {
        "request_updated": False,
        "history_updated": False,
        "fraud_updated": False,
        "status": "",
        "error": None
    }
    
    try:
        if decision == "approve":
            # Update request status
            results["request_updated"] = update_refund_request_status(
                request_id, decision="approve", status="approved"
            )
            # Increment refund count
            results["history_updated"] = update_refund_history_after_approval(customer_id)
            results["status"] = "approved"
            
        elif decision == "reject":
            # Update request status only (no history change)
            results["request_updated"] = update_refund_request_status(
                request_id, decision="reject", status="rejected"
            )
            results["status"] = "rejected"
            
        elif decision == "escalate":
            # Keep as pending, mark for manual review
            with _get_connection() as conn:
                cursor = conn.execute(
                    """UPDATE refund_requests 
                       SET ai_decision = 'escalate', 
                           status = 'pending', 
                           manual_review_required = 1
                       WHERE request_id = ?""",
                    (request_id,)
                )
                conn.commit()
                results["request_updated"] = cursor.rowcount > 0
            results["status"] = "pending_escalation"
    
    except Exception as e:
        results["error"] = str(e)
    
    return results


def auto_flag_fraud_if_exceeded(customer_id: str, max_refunds: int = 3) -> bool:
    """
    Automatically flag a customer for fraud if they exceed the refund limit.
    
    Args:
        customer_id: String ID like 'CUST-1000'
        max_refunds: Threshold for auto-flagging
    
    Returns:
        True if fraud flag was set, False otherwise.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT refund_count FROM refund_history WHERE customer_id = ?",
            (customer_id,)
        )
        row = cursor.fetchone()
        
        if row and row["refund_count"] > max_refunds:
            return update_fraud_flag(customer_id, True)
    
    return False


# ─── Tool Metadata ──────────────────────────────────────────

TOOL_METADATA = {
    "update_refund_request_status": {
        "description": "Update refund request with agent decision and status",
        "parameters": {"request_id": "str", "decision": "str", "status": "str"},
        "returns": "bool"
    },
    "update_refund_history_after_approval": {
        "description": "Increment refund count after approval",
        "parameters": {"customer_id": "str"},
        "returns": "bool"
    },
    "update_fraud_flag": {
        "description": "Set or clear fraud flag for a customer",
        "parameters": {"customer_id": "str", "fraud_flag": "bool"},
        "returns": "bool"
    },
    "process_decision": {
        "description": "Process final decision - update all relevant tables",
        "parameters": {"request_id": "str", "customer_id": "str", "decision": "str"},
        "returns": "Dict with update results"
    },
    "auto_flag_fraud_if_exceeded": {
        "description": "Auto-flag customer if refund count exceeds threshold",
        "parameters": {"customer_id": "str", "max_refunds": "int"},
        "returns": "bool"
    }
}


# ─── Self-Test ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from crm_lookup import get_complete_case, get_refund_request
    
    print("=" * 60)
    print("CRM Update Tool - Self Test")
    print("=" * 60)
    
    # Test 1: Check current state of a request
    print("\n--- Test 1: Read current state ---")
    case = get_complete_case("REF-7000")
    if case:
        req = case["refund_request"]
        print(f"  Request: {req['request_id']}")
        print(f"  Current Status: {req['status']}")
        print(f"  Current Decision: {req['ai_decision']}")
    
    # Test 2: Test process_decision (approve)
    print("\n--- Test 2: Process APPROVE decision ---")
    if case:
        result = process_decision(
            request_id=case["refund_request"]["request_id"],
            customer_id=case["customer"]["customer_id"],
            decision="approve"
        )
        print(f"  Result: {result}")
        
        # Verify update
        updated = get_refund_request(case["refund_request"]["request_id"])
        print(f"  New Status: {updated['status']}")
        print(f"  New Decision: {updated['ai_decision']}")
        
        # REVERT the change so seeded data stays clean
        print("\n  Reverting changes...")
        with sqlite3.connect(_get_db_path()) as conn:
            conn.execute(
                "UPDATE refund_requests SET ai_decision = 'approve', status = 'approved', manual_review_required = 0 WHERE request_id = ?",
                (case["refund_request"]["request_id"],)
            )
            # Reset refund history too
            conn.execute(
                "UPDATE refund_history SET refund_count = MAX(0, refund_count - 1) WHERE customer_id = ?",
                (case["customer"]["customer_id"],)
            )
            conn.commit()
        print("  Reverted.")
    
    # Test 3: Test fraud auto-flagging
    print("\n--- Test 3: Auto-fraud flag check ---")
    flagged = auto_flag_fraud_if_exceeded("CUST-1000", max_refunds=3)
    print(f"  CUST-1000 flagged: {flagged}")
    
    print(f"\n{'=' * 60}")
    print("Self-test complete")