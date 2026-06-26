# tools/escalation.py
"""
Escalation Tool - Creates and manages escalation records for human review.

Triggered when the eligibility checker returns decision='escalate'.
Creates a structured escalation case with all relevant context.
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path


# ─── Database Setup ─────────────────────────────────────────

def _get_db_path() -> str:
    return str(Path(__file__).parent.parent / "data" / "crm.db")


def _get_connection():
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_escalation_table():
    """Create escalation table if it doesn't exist."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS escalation_queue (
                escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id VARCHAR NOT NULL,
                customer_id VARCHAR NOT NULL,
                order_id VARCHAR NOT NULL,
                escalation_reason VARCHAR NOT NULL,
                priority VARCHAR DEFAULT 'medium',
                status VARCHAR DEFAULT 'open',
                agent_notes TEXT,
                context_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_by VARCHAR,
                resolution_notes TEXT,
                FOREIGN KEY (request_id) REFERENCES refund_requests(request_id)
            )
        """)
        conn.commit()


# ─── Data Classes ───────────────────────────────────────────

@dataclass
class EscalationRecord:
    escalation_id: Optional[int]
    request_id: str
    customer_id: str
    order_id: str
    escalation_reason: str
    priority: str
    status: str
    agent_notes: str
    context: Dict[str, Any]
    created_at: str
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None


# ─── Priority Mapping ───────────────────────────────────────

PRIORITY_MAP = {
    "legal_threat": "critical",
    "fraud_flag": "critical",
    "high_value_order": "high",
    "lost_shipment": "high",
    "damage_reported": "high",
    "wrong_item_received": "high",
    "boundary_time": "medium",
    "missing_receipt": "medium",
    "goodwill_request": "medium",
    "manual_review_required": "medium",
    "policy_dispute": "medium",
    "unknown_category": "low",
    "date_parse_error": "low",
    "unknown_shipping_status": "low",
}


# ─── Escalation Functions ───────────────────────────────────

def create_escalation(
    request_id: str,
    customer_id: str,
    order_id: str,
    escalation_reason: str,
    agent_notes: str = "",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create an escalation record for human review.
    
    Args:
        request_id: Refund request ID (REF-7000)
        customer_id: Customer ID (CUST-1000)
        order_id: Order ID (ORD-5000)
        escalation_reason: Reason from eligibility checker
        agent_notes: Additional notes from the agent
        context: Full context dict (CRM data, policy retrieved, eligibility details)
    
    Returns:
        Dict with escalation record details
    """
    _ensure_escalation_table()
    
    priority = PRIORITY_MAP.get(escalation_reason, "medium")
    context_json = json.dumps(context) if context else "{}"
    
    with _get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO escalation_queue 
               (request_id, customer_id, order_id, escalation_reason, 
                priority, status, agent_notes, context_json)
               VALUES (?, ?, ?, ?, ?, 'open', ?, ?)""",
            (request_id, customer_id, order_id, escalation_reason,
             priority, agent_notes, context_json)
        )
        conn.commit()
        escalation_id = cursor.lastrowid
        
        # Also update the refund request status
        conn.execute(
            """UPDATE refund_requests 
               SET ai_decision = 'escalate', 
                   status = 'pending', 
                   manual_review_required = 1
               WHERE request_id = ?""",
            (request_id,)
        )
        conn.commit()
    
    return {
        "escalation_id": escalation_id,
        "request_id": request_id,
        "priority": priority,
        "reason": escalation_reason,
        "status": "open",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_open_escalations(priority: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve all open escalations, optionally filtered by priority.
    
    Args:
        priority: Filter by priority level (critical, high, medium, low)
    
    Returns:
        List of escalation records
    """
    _ensure_escalation_table()
    
    with _get_connection() as conn:
        if priority:
            cursor = conn.execute(
                """SELECT * FROM escalation_queue 
                   WHERE status = 'open' AND priority = ?
                   ORDER BY created_at DESC""",
                (priority,)
            )
        else:
            cursor = conn.execute(
                """SELECT * FROM escalation_queue 
                   WHERE status = 'open'
                   ORDER BY 
                       CASE priority 
                           WHEN 'critical' THEN 1 
                           WHEN 'high' THEN 2 
                           WHEN 'medium' THEN 3 
                           WHEN 'low' THEN 4 
                       END,
                       created_at ASC"""
            )
        
        rows = cursor.fetchall()
    
    return [dict(row) for row in rows]


def resolve_escalation(
    escalation_id: int,
    resolved_by: str,
    resolution_notes: str,
    final_decision: str  # 'approved' or 'rejected'
) -> bool:
    """
    Mark an escalation as resolved.
    
    Args:
        escalation_id: The escalation record ID
        resolved_by: Name/ID of human agent who resolved it
        resolution_notes: Notes from the human agent
        final_decision: 'approved' or 'rejected'
    
    Returns:
        True if resolved successfully
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with _get_connection() as conn:
        # Get the request_id for this escalation
        cursor = conn.execute(
            "SELECT request_id FROM escalation_queue WHERE escalation_id = ?",
            (escalation_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return False
        
        request_id = row["request_id"]
        
        # Update escalation record
        cursor = conn.execute(
            """UPDATE escalation_queue 
               SET status = 'resolved', 
                   resolved_by = ?, 
                   resolution_notes = ?,
                   updated_at = ?
               WHERE escalation_id = ?""",
            (resolved_by, resolution_notes, now, escalation_id)
        )
        
        # Update refund request with final decision
        new_status = "approved" if final_decision == "approved" else "rejected"
        conn.execute(
            """UPDATE refund_requests 
               SET status = ?, manual_review_required = 0
               WHERE request_id = ?""",
            (new_status, request_id)
        )
        
        conn.commit()
        return True


def get_escalation_by_request(request_id: str) -> Optional[Dict[str, Any]]:
    """
    Check if a refund request has an active escalation.
    
    Args:
        request_id: Refund request ID
    
    Returns:
        Escalation record dict or None
    """
    _ensure_escalation_table()
    
    with _get_connection() as conn:
        cursor = conn.execute(
            """SELECT * FROM escalation_queue 
               WHERE request_id = ? AND status = 'open'
               ORDER BY created_at DESC LIMIT 1""",
            (request_id,)
        )
        row = cursor.fetchone()
    
    return dict(row) if row else None


def get_escalation_stats() -> Dict[str, Any]:
    """
    Get summary statistics for the escalation queue.
    
    Returns:
        Dict with counts by priority and status
    """
    _ensure_escalation_table()
    
    with _get_connection() as conn:
        # Count by priority
        cursor = conn.execute(
            """SELECT priority, COUNT(*) as count 
               FROM escalation_queue WHERE status = 'open' 
               GROUP BY priority"""
        )
        by_priority = {row["priority"]: row["count"] for row in cursor.fetchall()}
        
        # Count by status
        cursor = conn.execute(
            """SELECT status, COUNT(*) as count 
               FROM escalation_queue GROUP BY status"""
        )
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # Total open
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM escalation_queue WHERE status = 'open'"
        )
        total_open = cursor.fetchone()["count"]
    
    return {
        "total_open": total_open,
        "by_priority": by_priority,
        "by_status": by_status
    }


# ─── Build Escalation Context ────────────────────────────────

def build_escalation_context(
    customer: Dict[str, Any],
    order: Dict[str, Any],
    refund_request: Dict[str, Any],
    refund_history: Dict[str, Any],
    eligibility_result: Dict[str, Any],
    policy_chunks: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Build a comprehensive context package for the human agent.
    
    This gives the human agent everything they need to make a decision
    without hunting through multiple systems.
    
    Args:
        customer: Customer dict
        order: Order dict
        refund_request: RefundRequest dict
        refund_history: RefundHistory dict
        eligibility_result: Result from eligibility_checker
        policy_chunks: Relevant policy sections from RAG
    
    Returns:
        Dict with full context
    """
    return {
        "summary": {
            "customer_name": customer.get("name"),
            "customer_tier": customer.get("tier"),
            "order_id": order.get("order_id"),
            "product": order.get("product_category"),
            "amount": order.get("purchase_amount"),
            "refund_reason": refund_request.get("refund_reason"),
            "escalation_reason": eligibility_result.get("escalation_reason"),
            "agent_confidence": eligibility_result.get("confidence")
        },
        "customer": customer,
        "order": order,
        "refund_request": refund_request,
        "refund_history": refund_history,
        "eligibility_details": eligibility_result.get("details", {}),
        "policy_referenced": policy_chunks or [],
        "customer_comments": refund_request.get("customer_comments", ""),
        "escalated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# ─── Tool Metadata ──────────────────────────────────────────

TOOL_METADATA = {
    "create_escalation": {
        "description": "Create escalation record for human review",
        "parameters": {
            "request_id": "str",
            "customer_id": "str", 
            "order_id": "str",
            "escalation_reason": "str",
            "agent_notes": "str",
            "context": "dict"
        },
        "returns": "Dict with escalation details"
    },
    "get_open_escalations": {
        "description": "Get all open escalations, optionally filtered by priority",
        "parameters": {"priority": "str (optional)"},
        "returns": "List of escalation records"
    },
    "resolve_escalation": {
        "description": "Resolve an escalation with human agent decision",
        "parameters": {
            "escalation_id": "int",
            "resolved_by": "str",
            "resolution_notes": "str",
            "final_decision": "str"
        },
        "returns": "bool"
    },
    "get_escalation_stats": {
        "description": "Get escalation queue statistics",
        "parameters": {},
        "returns": "Dict with counts by priority and status"
    },
    "build_escalation_context": {
        "description": "Build comprehensive context package for human review",
        "parameters": {
            "customer": "dict",
            "order": "dict",
            "refund_request": "dict",
            "refund_history": "dict",
            "eligibility_result": "dict",
            "policy_chunks": "list (optional)"
        },
        "returns": "Dict with full context"
    }
}


# ─── Self-Test ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from crm_lookup import get_complete_case
    
    print("=" * 60)
    print("Escalation Tool - Self Test")
    print("=" * 60)
    
    # Ensure table exists
    _ensure_escalation_table()
    print("\n✅ Escalation table ready")
    
    # Test: Create escalation
    print("\n--- Test: Create Escalation ---")
    result = create_escalation(
        request_id="REF-7005",
        customer_id="CUST-1005",
        order_id="ORD-5005",
        escalation_reason="high_value_order",
        agent_notes="Order exceeds ₹50,000 threshold. Requires manager approval.",
        context={"test": True}
    )
    print(f"  Created: {result}")
    
    # Test: Get open escalations
    print("\n--- Test: Open Escalations ---")
    open_cases = get_open_escalations()
    for case in open_cases:
        print(f"  #{case['escalation_id']}: {case['escalation_reason']} ({case['priority']})")
    
    # Test: Stats
    print("\n--- Test: Escalation Stats ---")
    stats = get_escalation_stats()
    print(f"  Total Open: {stats['total_open']}")
    print(f"  By Priority: {stats['by_priority']}")
    
    # Test: Resolve (clean up test data)
    if result.get("escalation_id"):
        print("\n--- Test: Resolve Escalation ---")
        resolved = resolve_escalation(
            escalation_id=result["escalation_id"],
            resolved_by="Test Agent",
            resolution_notes="Test resolution - cleaning up.",
            final_decision="approved"
        )
        print(f"  Resolved: {resolved}")
    
    print(f"\n{'=' * 60}")
    print("Self-test complete")