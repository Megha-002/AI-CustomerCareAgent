# graph/nodes/crm_lookup.py
"""
CRM Lookup Node - Retrieves all CRM data for the refund request.
Pulls customer, order, refund_request, and refund_history in one shot.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, add_error
from tools.crm_lookup import get_complete_case


def crm_lookup_node(state: AgentState) -> AgentState:
    """
    Fetch complete CRM data for the request.
    
    Populates state with:
    - customer
    - order
    - refund_request
    - refund_history
    """
    
    request_id = state.get("request_id", "")
    
    # Log: CRM lookup started
    state = add_reasoning_log(
        state, "crm_lookup", "lookup_started",
        f"Fetching CRM data for {request_id}"
    )
    
    try:
        case = get_complete_case(request_id)
        
        if not case:
            state = add_error(state, "crm_lookup", f"Failed to build complete case for {request_id}")
            return state
        
        # Populate all CRM fields
        state["customer"] = case.get("customer")
        state["order"] = case.get("order")
        state["refund_request"] = case.get("refund_request")
        state["refund_history"] = case.get("refund_history")
        
        # Log success with key details
        customer_name = state["customer"].get("name", "Unknown")
        customer_tier = state["customer"].get("tier", "Unknown")
        product = state["order"].get("product_category", "Unknown")
        amount = state["order"].get("purchase_amount", 0)
        
        state = add_reasoning_log(
            state, "crm_lookup", "lookup_complete",
            f"CRM data retrieved: {customer_name} ({customer_tier}), "
            f"{product}, ₹{amount:,.2f}",
            {
                "customer_id": state["customer"].get("customer_id"),
                "order_id": state["order"].get("order_id"),
                "tier": customer_tier,
                "product_category": product,
                "purchase_amount": amount,
                "fraud_flag": state["refund_history"].get("fraud_flag", False),
                "refund_count": state["refund_history"].get("refund_count", 0)
            }
        )
        
    except Exception as e:
        state = add_error(state, "crm_lookup", str(e))
        state = add_reasoning_log(
            state, "crm_lookup", "lookup_error",
            f"Error fetching CRM data: {str(e)}"
        )
    
    return state