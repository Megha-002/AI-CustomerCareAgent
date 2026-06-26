# graph/nodes/eligibility.py
"""
Eligibility Node - Evaluates refund eligibility using CRM data and policy.
Calls the eligibility checker and stores results in state.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, add_error
from tools.eligibility_checker import check_eligibility


def eligibility_node(state: AgentState) -> AgentState:
    """
    Check refund eligibility using CRM data and policy rules.
    
    Takes customer, order, refund_request, and refund_history from state,
    runs the eligibility checker, and stores the decision.
    """
    
    # Log: Eligibility check started
    state = add_reasoning_log(
        state, "eligibility", "check_started",
        "Running eligibility checks..."
    )
    
    try:
        customer = state.get("customer", {})
        order = state.get("order", {})
        refund_request = state.get("refund_request", {})
        refund_history = state.get("refund_history", {})
        
        if not all([customer, order, refund_request, refund_history]):
            state = add_error(state, "eligibility", "Missing CRM data for eligibility check")
            return state
        
        # Run eligibility check
        result = check_eligibility(
            customer=customer,
            order=order,
            refund_request=refund_request,
            refund_history=refund_history
        )
        
        # Store results
        state["eligibility_result"] = result
        state["eligibility_decision"] = result.get("decision")
        state["eligibility_confidence"] = result.get("confidence")
        state["eligibility_details"] = result.get("details", {})
        
        # Log step-by-step results
        decision = result.get("decision", "unknown").upper()
        reason = result.get("reason", "")
        confidence = result.get("confidence", 0)
        escalation = result.get("escalation_reason")
        
        state = add_reasoning_log(
            state, "eligibility", "check_complete",
            f"Decision: {decision} | Confidence: {confidence:.0%} | {reason[:100]}",
            {
                "decision": decision,
                "confidence": confidence,
                "reason": reason,
                "escalation_reason": escalation,
                "steps_passed": sum(1 for v in result.get("details", {}).values() if v.get("passed")),
                "steps_total": len(result.get("details", {}))
            }
        )
        
        # Log each individual check for admin dashboard
        for step_name, step_detail in result.get("details", {}).items():
            state = add_reasoning_log(
                state, "eligibility", f"step_{step_name}",
                f"{'✅' if step_detail.get('passed') else '❌'} {step_name}: {step_detail.get('message', '')[:100]}",
                {"passed": step_detail.get("passed")}
            )
    
    except Exception as e:
        state = add_error(state, "eligibility", str(e))
        state = add_reasoning_log(
            state, "eligibility", "check_error",
            f"Error during eligibility check: {str(e)}"
        )
    
    return state