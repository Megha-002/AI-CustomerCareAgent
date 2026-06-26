"""
CRM Lookup Node

Fetches customer/order/refund data from SQLite AND formats it
as readable text context for the LLM decision node.

Uses ONLY functions that actually exist in tools/crm_lookup.py:
  - get_customer(customer_id)
  - get_order(order_id)
  - get_customer_orders(customer_id)
  - get_customer_refund_requests(customer_id)
  - get_refund_history(customer_id)
"""

import logging
from datetime import datetime

from tools.crm_lookup import (
    get_customer,
    get_order,
    get_customer_orders,
    get_customer_refund_requests,
    get_refund_history,
)
from graph.state import AgentState

logger = logging.getLogger(__name__)


def _format_customer(customer: dict) -> str:
    """Format a customer record for LLM consumption."""
    if not customer:
        return "No customer record found."
    lines = [
        f"Name: {customer.get('name', 'Unknown')}",
        f"Email: {customer.get('email', 'Unknown')}",
        f"Tier: {customer.get('tier', 'Unknown')}",
        f"Customer Since: {customer.get('created_at', 'Unknown')}",
    ]
    return "\n".join(lines)


def _format_order(order: dict) -> str:
    """Format an order record for LLM consumption."""
    if not order:
        return "No order record found."
    lines = [
        f"Order ID: {order.get('order_id', 'Unknown')}",
        f"Order Date: {order.get('order_date', 'Unknown')}",
        f"Product Category: {order.get('product_category', 'Unknown')}",
        f"Product Name: {order.get('product_name', 'N/A')}",
        f"Purchase Amount: ${order.get('purchase_amount', 0):.2f}",
        f"Shipping Status: {order.get('shipping_status', 'Unknown')}",
        f"Return Window: {order.get('return_window_days', 'N/A')} days",
        f"Item Condition: {order.get('item_condition', 'N/A')}",
        f"Original Packaging: {order.get('original_packaging', 'N/A')}",
    ]
    return "\n".join(lines)


def _format_refund_requests(requests: list) -> str:
    """Format refund requests for a customer."""
    if not requests:
        return "No previous refund requests found for this customer."
    lines = [f"Customer's Refund Requests ({len(requests)} total):"]
    for req in requests:
        lines.append(
            f"  - Request ID: {req.get('request_id', 'N/A')}, "
            f"Order ID: {req.get('order_id', 'N/A')}, "
            f"Status: {req.get('status', 'N/A')}, "
            f"Amount: ${req.get('requested_amount', 0):.2f}, "
            f"Reason: {req.get('reason', 'N/A')}, "
            f"Date: {req.get('created_at', 'N/A')}"
        )
    return "\n".join(lines)


def _format_refund_history(history: dict) -> str:
    """Format customer's overall refund history."""
    if not history:
        return "No refund history available."
    lines = [
        f"Total Refunds (past 12 months): {history.get('refund_count', 0)}",
        f"Last Refund Date: {history.get('last_refund_date', 'Never')}",
        f"Fraud Flag: {history.get('fraud_flag', False)}",
    ]
    if history.get("fraud_flag"):
        lines.append("WARNING: Customer has a fraud flag — review carefully")
    if history.get("refund_count", 0) >= 3:
        lines.append(
            f"WARNING: Customer has {history['refund_count']} refunds "
            f"in past 12 months — velocity check triggered"
        )
    return "\n".join(lines)


def _calculate_days_since_order(order: dict) -> str:
    """Calculate and format days since order for LLM."""
    if not order or not order.get("order_date"):
        return "Cannot calculate — no order date"
    try:
        order_date = datetime.strptime(str(order["order_date"])[:10], "%Y-%m-%d")
        days = (datetime.utcnow() - order_date).days
        return f"{days} days ago"
    except (ValueError, TypeError):
        return "Cannot calculate — invalid date format"


def crm_lookup_node(state: AgentState) -> dict:
    """
    Fetch CRM data and format as LLM-readable context.

    Consumes: customer_id, order_id
    Produces: crm_data, crm_context, crm_lookup_reasoning, customer_id, reasoning_log
    """
    node_start = datetime.utcnow().isoformat()
    customer_id = state.get("customer_id")
    order_id = state.get("order_id")

    logger.info(f"CRM lookup: customer_id={customer_id}, order_id={order_id}")

    errors = []

    # ── Fetch customer ──
    customer = None
    if customer_id:
        try:
            customer = get_customer(customer_id)
        except Exception as e:
            error_msg = f"Failed to fetch customer {customer_id}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    # ── Fetch order ──
    order = None
    if order_id:
        try:
            order = get_order(order_id)
        except Exception as e:
            error_msg = f"Failed to fetch order {order_id}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    # ── If we have order but no customer, try to get customer_id from order ──
    if order and not customer and not customer_id:
        cid_from_order = order.get("customer_id")
        if cid_from_order:
            try:
                customer = get_customer(cid_from_order)
                customer_id = cid_from_order
            except Exception as e:
                errors.append(f"Failed to fetch customer from order: {e}")

    # ── Fetch ALL refund requests for this customer ──
    refund_requests = []
    if customer_id:
        try:
            refund_requests = get_customer_refund_requests(customer_id)
        except Exception as e:
            errors.append(f"Failed to fetch refund requests: {e}")

    # ── Fetch refund history (counts + fraud flag) ──
    refund_history = None
    if customer_id:
        try:
            refund_history = get_refund_history(customer_id)
        except Exception as e:
            errors.append(f"Failed to fetch refund history: {e}")

    # ── If we still have no customer_id and no order_id, try to find
    #    orders by scanning — but this should be rare ──
    if not order and not customer:
        logger.warning("No customer_id or order_id available — CRM context will be empty")

    # ═══ FORMAT AS LLM-READABLE CONTEXT ═══
    context_parts = []

    context_parts.append("### CUSTOMER PROFILE")
    context_parts.append(_format_customer(customer))
    context_parts.append("")

    context_parts.append("### ORDER DETAILS")
    context_parts.append(_format_order(order))
    if order:
        context_parts.append(f"Days Since Order: {_calculate_days_since_order(order)}")
    context_parts.append("")

    context_parts.append("### CUSTOMER REFUND REQUESTS")
    context_parts.append(_format_refund_requests(refund_requests))
    context_parts.append("")

    context_parts.append("### CUSTOMER REFUND HISTORY")
    context_parts.append(_format_refund_history(refund_history))
    context_parts.append("")

    crm_context = "\n".join(context_parts)

    # Raw data dict for action node (needs order/customer dicts for tool calls)
    crm_data = {
        "customer": customer,
        "order": order,
        "refund_requests": refund_requests,
        "refund_history": refund_history,
    }

    # ── Reasoning summary ──
    found_items = []
    if customer:
        found_items.append(f"customer {customer.get('name')}")
    if order:
        found_items.append(f"order {order_id}")
    if refund_requests:
        found_items.append(f"{len(refund_requests)} refund request(s)")
    if refund_history:
        found_items.append("refund history")

    not_found = []
    if not customer:
        not_found.append("customer")
    if not order:
        not_found.append("order")

    reasoning = f"Found: {', '.join(found_items) if found_items else 'nothing'}"
    if not_found:
        reasoning += f". Not found: {', '.join(not_found)}"

    logger.info(f"CRM context formatted: {len(crm_context)} characters")

    return {
        "crm_data": crm_data,
        "crm_context": crm_context,
        "crm_lookup_reasoning": reasoning,
        "customer_id": customer_id,
        "reasoning_log": [{
            "node": "crm_lookup",
            "timestamp": node_start,
            "input_summary": f"customer_id={customer_id}, order_id={order_id}",
            "output_summary": reasoning,
            "thinking": f"Retrieved and formatted CRM data. Context length: {len(crm_context)} chars"
        }],
        "errors": errors,
    }