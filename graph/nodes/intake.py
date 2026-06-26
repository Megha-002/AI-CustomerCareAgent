# graph/nodes/intake.py
"""
Intake Node - Entry point for the LangGraph workflow.
Validates the request_id, initializes state, and prepares for processing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, add_error
from tools.crm_lookup import get_refund_request


def intake_node(state: AgentState) -> AgentState:
    """
    Validate the incoming refund request and prepare for processing.
    
    Performs:
    1. Validate request_id format
    2. Quick check that the request exists
    3. Build policy search query
    4. Log the intake
    """
    
    request_id = state.get("request_id", "")
    
    # Log: Intake started
    state = add_reasoning_log(
        state, "intake", "intake_started",
        f"Processing refund request: {request_id}",
        {"request_id": request_id, "user_input": state.get("user_input", "")}
    )
    
    # Validate request_id format
    if not request_id or not request_id.startswith("REF-"):
        state = add_error(state, "intake", f"Invalid request ID format: {request_id}")
        state = add_reasoning_log(
            state, "intake", "validation_failed",
            f"Invalid request ID: {request_id}"
        )
        return state
    
    # Quick existence check
    refund_req = get_refund_request(request_id)
    if not refund_req:
        state = add_error(state, "intake", f"Request {request_id} not found in CRM")
        state = add_reasoning_log(
            state, "intake", "request_not_found",
            f"Request {request_id} does not exist in CRM"
        )
        return state
    
    # Build policy search query from refund reason
    refund_reason = refund_req.get("refund_reason", "")
    product_condition = refund_req.get("product_condition", "")
    
    policy_query = f"Refund policy for {refund_reason}. Product condition: {product_condition}."
    
    # Add customer comments if available
    comments = refund_req.get("customer_comments", "")
    if comments:
        policy_query += f" Customer comments: {comments}"
    
    state["policy_query"] = policy_query
    
    # Log: Intake complete
    state = add_reasoning_log(
        state, "intake", "intake_complete",
        f"Request validated. Policy query: {policy_query[:100]}...",
        {"refund_reason": refund_reason, "policy_query": policy_query}
    )
    
    return state