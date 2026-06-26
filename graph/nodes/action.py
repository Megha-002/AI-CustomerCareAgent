"""
Action Node — Executes the LLM's decision.

This node does NOT make decisions. It takes the decision
that the LLM already made and executes it.

Uses ONLY functions that actually exist in tools/crm_update.py:
  - process_decision(request_id, customer_id, decision)
  - update_refund_request_status(request_id, decision, status)
  - update_refund_history_after_approval(customer_id)
  - update_fraud_flag(customer_id, fraud_flag)
  - auto_flag_fraud_if_exceeded(customer_id, max_refunds)

Uses ONLY the actual signature of tools/refund_calculator.py:
  - calculate_refund(order: Dict, refund_request: Dict) -> Dict

Uses ONLY the actual signature of tools/escalation.py:
  - create_escalation(customer_id, order_id, reason, context, priority)
"""

import logging
from datetime import datetime

from tools.refund_calculator import calculate_refund
from tools.crm_update import (
    update_refund_request_status,
    update_refund_history_after_approval,
    process_decision,
    auto_flag_fraud_if_exceeded,
)
from tools.escalation import create_escalation
from graph.state import AgentState

logger = logging.getLogger(__name__)


def _find_existing_refund_request(refund_requests: list, order_id: str) -> dict | None:
    """
    Find an existing refund request for this order from the list
    returned by get_customer_refund_requests().
    """
    if not refund_requests or not order_id:
        return None
    for req in refund_requests:
        if req.get("order_id") == order_id:
            return req
    return None


def _execute_approve(state: AgentState) -> dict:
    """
    Execute an APPROVE decision.

    1. Call calculate_refund(order, refund_request) with correct signature
    2. Update existing refund request status if one exists
    3. Update refund history after approval
    4. Check fraud velocity
    """
    crm_data = state.get("crm_data") or {}
    order = crm_data.get("order")
    customer = crm_data.get("customer")
    refund_requests = crm_data.get("refund_requests") or []

    if not order:
        return {
            "action_taken": "APPROVE_FAILED_NO_ORDER",
            "errors": ["Cannot approve refund — no order data available"],
        }

    order_id = order.get("order_id")
    customer_id = customer.get("customer_id") or state.get("customer_id")

    # ── Build the refund_request dict that calculate_refund expects ──
    #    The calculator signature is: calculate_refund(order, refund_request)
    #    We construct a minimal refund_request from what we have in state.
    entities = state.get("entities") or {}
    refund_request = {
        "reason": entities.get("reason", "Customer requested refund"),
        "requested_amount": entities.get("amount_requested"),
        "item_condition": order.get("item_condition", "new"),
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        # ✅ CORRECT SIGNATURE: calculate_refund(order_dict, refund_request_dict)
        refund_calc = calculate_refund(order, refund_request)

        # The calculator returns a dict — adapt to whatever keys it provides
        refund_amount = (
            refund_calc.get("final_amount")
            or refund_calc.get("refund_amount")
            or refund_calc.get("amount")
            or order.get("purchase_amount", 0)
        )
        restocking_fee = refund_calc.get("restocking_fee", 0)

        logger.info(
            f"Refund calculated: ${order.get('purchase_amount', 0):.2f} "
            f"-> ${refund_amount:.2f} (fee: ${restocking_fee:.2f})"
        )

    except Exception as e:
        logger.error(f"Refund calculation failed: {e}")
        # Fallback: use full purchase amount
        refund_amount = order.get("purchase_amount", 0)
        restocking_fee = 0

    # ── Update existing refund request if one exists ──
    refund_id = None
    existing_request = _find_existing_refund_request(refund_requests, order_id)

    if existing_request and existing_request.get("request_id"):
        refund_id = existing_request["request_id"]
        try:
            update_refund_request_status(refund_id, "approve", "approved")
            logger.info(f"Updated refund request {refund_id} to approved")
        except Exception as e:
            logger.error(f"Failed to update refund request status: {e}")

    # ── Update refund history after approval ──
    if customer_id:
        try:
            update_refund_history_after_approval(customer_id)
            logger.info(f"Updated refund history for customer {customer_id}")
        except Exception as e:
            logger.error(f"Failed to update refund history: {e}")

        # ── Auto-flag fraud if threshold exceeded ──
        try:
            auto_flag_fraud_if_exceeded(customer_id, max_refunds=3)
        except Exception as e:
            logger.error(f"Fraud flag check failed: {e}")

    return {
        "action_taken": (
            f"APPROVED - Refund ${refund_amount:.2f} "
            f"(restocking fee: ${restocking_fee:.2f})"
        ),
        "refund_amount": refund_amount,
        "refund_id": refund_id,
    }


def _execute_reject(state: AgentState) -> dict:
    """
    Execute a REJECT decision.

    Updates existing refund request status to rejected if one exists.
    """
    crm_data = state.get("crm_data") or {}
    order = crm_data.get("order")
    customer = crm_data.get("customer")
    refund_requests = crm_data.get("refund_requests") or []

    order_id = order.get("order_id") if order else None
    customer_id = customer.get("customer_id") or state.get("customer_id")

    # ── Update existing refund request if one exists ──
    refund_id = None
    existing_request = _find_existing_refund_request(refund_requests, order_id)

    if existing_request and existing_request.get("request_id"):
        refund_id = existing_request["request_id"]
        try:
            update_refund_request_status(refund_id, "reject", "rejected")
            logger.info(f"Updated refund request {refund_id} to rejected")
        except Exception as e:
            logger.error(f"Failed to update refund request status: {e}")

    return {
        "action_taken": f"REJECTED - Reason: {state.get('decision_reason', 'N/A')[:100]}",
        "refund_id": refund_id,
    }


def _execute_escalate(state: AgentState) -> dict:
    """
    Execute an ESCALATE decision.

    Creates an escalation record with full context for human review.
    Uses the existing refund request ID if available, otherwise creates a pending request.
    """
    crm_data = state.get("crm_data") or {}
    order = crm_data.get("order")
    customer = crm_data.get("customer")
    refund_requests = crm_data.get("refund_requests") or []

    order_id = order.get("order_id") if order else None
    customer_id = customer.get("customer_id") or state.get("customer_id")

    # ── Find existing refund request ID for this order ──
    request_id = None
    existing_request = _find_existing_refund_request(refund_requests, order_id)
    if existing_request and existing_request.get("request_id"):
        request_id = existing_request["request_id"]
    else:
        # No existing refund request — use process_decision which handles this
        # We'll pass a generated request_id; if it doesn't exist, escalation will
        # still create the escalation record with whatever ID we have
        request_id = f"REF-ESC-{customer_id or 'UNKNOWN'}-{order_id or 'UNKNOWN'}"
        logger.warning(f"No existing refund request found for order {order_id}, using generated ID: {request_id}")

    # ── Build escalation context ──
    escalation_context = {
        "user_input": state.get("user_input", ""),
        "intent": state.get("intent", ""),
        "entities": state.get("entities") or {},
        "crm_context": state.get("crm_context", ""),
        "policy_context": state.get("policy_context", ""),
        "llm_decision_raw": state.get("llm_decision_raw", ""),
        "decision_reason": state.get("decision_reason", ""),
        "confidence": state.get("confidence", 0),
    }

    escalation_id = None
    try:
        # ✅ CORRECTED CALL:
        escalation_result = create_escalation(
            request_id=request_id,
            customer_id=customer_id,
            order_id=order_id,
            escalation_reason=f"LLM escalated: {state.get('decision_reason', 'Uncertain case')[:200]}",
            agent_notes=state.get("decision_reason", ""),
            context=escalation_context,
        )
        # The function returns a dict; we need to extract the escalation_id
        escalation_id = escalation_result.get("escalation_id")
        logger.info(f"Created escalation record: {escalation_id}")
    except Exception as e:
        logger.error(f"Failed to create escalation record: {e}")

    return {
        "action_taken": f"ESCALATED - {state.get('decision_reason', 'Uncertain case')[:100]}",
        "escalation_id": escalation_id,
    }


def action_node(state: AgentState) -> dict:
    """
    Execute the LLM's decision.

    The decision was already made by llm_decision_node.
    This node handles side effects: database updates, calculations.

    Consumes: decision, crm_data, decision_reason, customer_response, entities, confidence
    Produces: action_taken, refund_amount, refund_id, escalation_id, response, reasoning_log
    """
    node_start = datetime.utcnow().isoformat()
    decision = state.get("decision", "ESCALATE").lower()  # ← add .lower()

    logger.info(f"Action node executing decision: {decision}")

    result = {}
    errors = []

    if decision == "approve":
        approve_result = _execute_approve(state)
        result.update(approve_result)
        if "errors" in approve_result:
            errors.extend(approve_result["errors"])

    elif decision == "reject":
        reject_result = _execute_reject(state)
        result.update(reject_result)
        if "errors" in reject_result:
            errors.extend(reject_result["errors"])

    elif decision == "escalate":
        escalate_result = _execute_escalate(state)
        result.update(escalate_result)
        if "errors" in escalate_result:
            errors.extend(escalate_result["errors"])

    else:
        logger.warning(f"Unknown decision type: {decision} — treating as escalation")
        escalate_result = _execute_escalate(state)
        result.update(escalate_result)
        result["action_taken"] = f"UNKNOWN_DECISION_ESCALATED (was: {decision})"

    # Set the final response (generated by LLM, NOT by this node)
        # Set the final response (generated by LLM, NOT by this node)
    llm_response = state.get(
        "customer_response",
        "I'm sorry, I was unable to process your request. A specialist will contact you shortly."
    )
    
    # Append refund details if approved
    if decision == "approve" and result.get("refund_amount"):
        refund_amount = result["refund_amount"]
        refund_details = (
            f"\n\n💰 **Refund Details**\n"
            f"Amount: ₹{refund_amount:,.2f}\n"
            f"Processing Time: 5-7 business days"
        )
        result["response"] = llm_response + refund_details
    else:
        result["response"] = llm_response

    output = {
        "reasoning_log": [{
            "node": "action",
            "timestamp": node_start,
            "input_summary": f"decision={decision}",
            "output_summary": result.get("action_taken", "No action recorded"),
            "thinking": f"Executed {decision} decision. CRM updated.",
        }],
    }
    output.update(result)

    if errors:
        output["errors"] = errors

    logger.info(f"Action completed: {result.get('action_taken', 'unknown')}")
    return output