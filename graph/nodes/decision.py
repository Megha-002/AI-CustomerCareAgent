# graph/nodes/decision.py
"""
Decision Node - Makes the final decision based on eligibility results.
Routes to APPROVE, REJECT, or ESCALATE.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, add_error
from tools.refund_calculator import calculate_refund


def decision_node(state: AgentState) -> AgentState:
    """
    Make the final decision and calculate refund if approved.
    
    If APPROVE: Calculate refund amount
    If REJECT: Prepare rejection message
    If ESCALATE: Prepare escalation context
    """
    
    eligibility_decision = state.get("eligibility_decision", "reject")
    eligibility_result = state.get("eligibility_result", {})
    
    state = add_reasoning_log(
        state, "decision", "decision_started",
        f"Processing decision: {eligibility_decision.upper()}"
    )
    
    try:
        if eligibility_decision == "approve":
            # Calculate refund
            order = state.get("order", {})
            refund_request = state.get("refund_request", {})
            
            calculation = calculate_refund(order=order, refund_request=refund_request)
            state["refund_calculation"] = calculation
            state["refund_amount"] = calculation.get("refund_amount")
            state["refund_type"] = calculation.get("refund_type")
            state["final_decision"] = "approve"
            state["decision_reason"] = eligibility_result.get("reason", "")
            
            state = add_reasoning_log(
                state, "decision", "approve_with_refund",
                f"APPROVED - Refund: ₹{calculation.get('refund_amount', 0):,.2f} "
                f"({calculation.get('refund_type', '')})",
                {
                    "refund_amount": calculation.get("refund_amount"),
                    "refund_type": calculation.get("refund_type"),
                    "restocking_fee": calculation.get("restocking_fee", 0),
                    "is_full_refund": calculation.get("is_full_refund")
                }
            )
            
        elif eligibility_decision == "reject":
            state["final_decision"] = "reject"
            state["decision_reason"] = eligibility_result.get("reason", "")
            state["refund_amount"] = 0.0
            
            state = add_reasoning_log(
                state, "decision", "rejected",
                f"REJECTED - {eligibility_result.get('reason', '')[:150]}"
            )
            
        elif eligibility_decision == "escalate":
            state["final_decision"] = "escalate"
            state["decision_reason"] = eligibility_result.get("reason", "")
            state["refund_amount"] = 0.0
            
            escalation_reason = eligibility_result.get("escalation_reason", "unknown")
            state = add_reasoning_log(
                state, "decision", "escalated",
                f"ESCALATED - Reason: {escalation_reason}",
                {"escalation_reason": escalation_reason}
            )
    
    except Exception as e:
        state = add_error(state, "decision", str(e))
        state = add_reasoning_log(
            state, "decision", "decision_error",
            f"Error during decision: {str(e)}"
        )
    
    return state