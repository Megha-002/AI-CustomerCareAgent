# graph/nodes/logging_node.py
"""
Logging Node - Final node that logs the complete workflow summary.
Records to MLflow and prepares the final state for the API response.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, get_state_summary


def logging_node(state: AgentState) -> AgentState:
    """
    Final logging and cleanup.
    
    - Logs workflow completion
    - Prepares response_data for API
    - Records summary for observability
    """
    
    # Get state summary
    summary = get_state_summary(state)
    
    # Build structured response data
    state["response_data"] = {
        "request_id": state.get("request_id"),
        "final_decision": state.get("final_decision"),
        "decision_reason": state.get("decision_reason"),
        "refund_amount": state.get("refund_amount"),
        "refund_type": state.get("refund_type"),
        "response_text": state.get("response_text"),
        "eligibility_confidence": state.get("eligibility_confidence"),
        "escalation_id": state.get("escalation_result", {}).get("escalation_id") if state.get("escalation_result") else None,
        "reasoning_logs": state.get("reasoning_logs", []),
        "errors": state.get("errors", []),
        "workflow_status": state.get("workflow_status"),
        "summary": summary
    }
    
    # Log completion
    state = add_reasoning_log(
        state, "logging", "workflow_complete",
        f"Workflow {state.get('workflow_status', 'unknown').upper()} - "
        f"Decision: {state.get('final_decision', 'N/A').upper()}",
        summary
    )
    
    # Log to MLflow (placeholder - will be wired in observability step)
    state = add_reasoning_log(
        state, "logging", "mlflow_logged",
        "Workflow metrics logged to MLflow"
    )
    
    return state