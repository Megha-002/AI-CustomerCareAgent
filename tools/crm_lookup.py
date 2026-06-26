# tools/crm_lookup.py
"""
CRM Lookup Tool - Single source of truth for all CRM database queries.
Each function is independent and returns structured data for downstream tools.
"""

import sqlite3
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from pathlib import Path


# ─── Data Classes ───────────────────────────────────────────

@dataclass
class Customer:
    customer_id: str
    name: str
    email: str
    tier: str

@dataclass
class Order:
    order_id: str
    customer_id: str
    order_date: str
    product_category: str
    purchase_amount: float
    shipping_status: str
    return_window_days: int

@dataclass
class RefundRequest:
    request_id: str
    order_id: str
    request_date: str
    refund_reason: str
    product_condition: str
    package_opened: bool
    receipt_available: bool
    damage_reported: bool
    wrong_item_received: bool
    delivery_issue: str          # VARCHAR in DB: 'none', 'lost', 'delayed', etc.
    customer_comments: Optional[str]
    ai_decision: Optional[str]
    manual_review_required: bool
    status: str
    created_at: str

@dataclass
class RefundHistory:
    customer_id: str
    refund_count: int
    last_refund_date: Optional[str]
    fraud_flag: bool

@dataclass
class CompleteCase:
    """Aggregated case data for downstream decision-making."""
    customer: Customer
    order: Order
    refund_request: RefundRequest
    refund_history: RefundHistory


# ─── Database Connection ────────────────────────────────────

def _get_db_path() -> str:
    """Resolve database path relative to project root."""
    return str(Path(__file__).parent.parent / "data" / "crm.db")


def _get_connection():
    """Create a new database connection with row factory for dict-like access."""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# ─── Individual Lookup Functions ─────────────────────────────

def get_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a customer by ID.
    
    Args:
        customer_id: String ID like 'CUST-1000'
    
    Returns:
        Dictionary with customer data or None if not found.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT customer_id, name, email, tier FROM customers WHERE customer_id = ?",
            (customer_id,)
        )
        row = cursor.fetchone()
        
    if not row:
        return None
    
    return asdict(Customer(
        customer_id=row["customer_id"],
        name=row["name"],
        email=row["email"],
        tier=row["tier"]
    ))


def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve an order by ID.
    
    Args:
        order_id: String ID like 'ORD-5000'
    
    Returns:
        Dictionary with order data or None if not found.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            """SELECT order_id, customer_id, order_date, product_category, 
                      purchase_amount, shipping_status, return_window_days 
               FROM orders WHERE order_id = ?""",
            (order_id,)
        )
        row = cursor.fetchone()
        
    if not row:
        return None
    
    return asdict(Order(
        order_id=row["order_id"],
        customer_id=row["customer_id"],
        order_date=row["order_date"],
        product_category=row["product_category"],
        purchase_amount=row["purchase_amount"],
        shipping_status=row["shipping_status"],
        return_window_days=row["return_window_days"]
    ))


def get_refund_request(request_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a refund request by ID.
    
    Args:
        request_id: String ID like 'REF-7000'
    
    Returns:
        Dictionary with refund request data or None if not found.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            """SELECT request_id, order_id, request_date, refund_reason, 
                      product_condition, package_opened, receipt_available,
                      damage_reported, wrong_item_received, delivery_issue,
                      customer_comments, ai_decision, manual_review_required,
                      status, created_at
               FROM refund_requests WHERE request_id = ?""",
            (request_id,)
        )
        row = cursor.fetchone()
        
    if not row:
        return None
    
    return asdict(RefundRequest(
        request_id=row["request_id"],
        order_id=row["order_id"],
        request_date=row["request_date"],
        refund_reason=row["refund_reason"],
        product_condition=row["product_condition"],
        package_opened=bool(row["package_opened"]),
        receipt_available=bool(row["receipt_available"]),
        damage_reported=bool(row["damage_reported"]),
        wrong_item_received=bool(row["wrong_item_received"]),
        delivery_issue=row["delivery_issue"],
        customer_comments=row["customer_comments"],
        ai_decision=row["ai_decision"],
        manual_review_required=bool(row["manual_review_required"]),
        status=row["status"],
        created_at=row["created_at"]
    ))


def get_refund_history(customer_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve refund history for a customer.
    
    Args:
        customer_id: String ID like 'CUST-1000'
    
    Returns:
        Dictionary with refund history or None if not found.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            """SELECT customer_id, refund_count, last_refund_date, fraud_flag 
               FROM refund_history WHERE customer_id = ?""",
            (customer_id,)
        )
        row = cursor.fetchone()
        
    if not row:
        return None
    
    return asdict(RefundHistory(
        customer_id=row["customer_id"],
        refund_count=row["refund_count"],
        last_refund_date=row["last_refund_date"],
        fraud_flag=bool(row["fraud_flag"])
    ))


def get_complete_case(request_id: str) -> Optional[Dict[str, Any]]:
    """
    Aggregate all CRM data for a refund request into a complete case.
    
    Args:
        request_id: String ID like 'REF-7000'
    
    Returns:
        Dictionary with customer, order, refund_request, and refund_history.
    """
    refund_req = get_refund_request(request_id)
    if not refund_req:
        return None
    
    order = get_order(refund_req["order_id"])
    if not order:
        return None
    
    customer = get_customer(order["customer_id"])
    if not customer:
        return None
    
    refund_hist = get_refund_history(customer["customer_id"])
    if not refund_hist:
        refund_hist = asdict(RefundHistory(
            customer_id=customer["customer_id"],
            refund_count=0,
            last_refund_date=None,
            fraud_flag=False
        ))
    
    return asdict(CompleteCase(
        customer=customer,
        order=order,
        refund_request=refund_req,
        refund_history=refund_hist
    ))


def get_customer_orders(customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent orders for a customer."""
    with _get_connection() as conn:
        cursor = conn.execute(
            """SELECT order_id, customer_id, order_date, product_category, 
                      purchase_amount, shipping_status, return_window_days 
               FROM orders 
               WHERE customer_id = ?
               ORDER BY order_date DESC
               LIMIT ?""",
            (customer_id, limit)
        )
        rows = cursor.fetchall()
    
    return [asdict(Order(
        order_id=row["order_id"],
        customer_id=row["customer_id"],
        order_date=row["order_date"],
        product_category=row["product_category"],
        purchase_amount=row["purchase_amount"],
        shipping_status=row["shipping_status"],
        return_window_days=row["return_window_days"]
    )) for row in rows]


def get_customer_refund_requests(customer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve recent refund requests for a customer."""
    with _get_connection() as conn:
        cursor = conn.execute(
            """SELECT rr.* 
               FROM refund_requests rr
               JOIN orders o ON rr.order_id = o.order_id
               WHERE o.customer_id = ?
               ORDER BY rr.created_at DESC
               LIMIT ?""",
            (customer_id, limit)
        )
        rows = cursor.fetchall()
    
    return [asdict(RefundRequest(
        request_id=row["request_id"],
        order_id=row["order_id"],
        request_date=row["request_date"],
        refund_reason=row["refund_reason"],
        product_condition=row["product_condition"],
        package_opened=bool(row["package_opened"]),
        receipt_available=bool(row["receipt_available"]),
        damage_reported=bool(row["damage_reported"]),
        wrong_item_received=bool(row["wrong_item_received"]),
        delivery_issue=row["delivery_issue"],
        customer_comments=row["customer_comments"],
        ai_decision=row["ai_decision"],
        manual_review_required=bool(row["manual_review_required"]),
        status=row["status"],
        created_at=row["created_at"]
    )) for row in rows]


def get_all_pending_requests() -> List[Dict[str, Any]]:
    """Retrieve all refund requests with status 'pending'."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT request_id FROM refund_requests WHERE status = 'pending'"
        )
        rows = cursor.fetchall()
    
    return [get_complete_case(row["request_id"]) for row in rows]


# ─── Tool Metadata ──────────────────────────────────────────

TOOL_METADATA = {
    "get_customer": {
        "description": "Retrieve customer details by ID (e.g., 'CUST-1000')",
        "parameters": {"customer_id": "str"},
        "returns": "Customer dict or None"
    },
    "get_order": {
        "description": "Retrieve order details by ID (e.g., 'ORD-5000')",
        "parameters": {"order_id": "str"},
        "returns": "Order dict or None"
    },
    "get_refund_request": {
        "description": "Retrieve refund request details by ID (e.g., 'REF-7000')",
        "parameters": {"request_id": "str"},
        "returns": "RefundRequest dict or None"
    },
    "get_refund_history": {
        "description": "Retrieve refund history for a customer",
        "parameters": {"customer_id": "str"},
        "returns": "RefundHistory dict or None"
    },
    "get_complete_case": {
        "description": "Build complete case with all CRM data for a refund request",
        "parameters": {"request_id": "str"},
        "returns": "CompleteCase dict or None"
    }
}