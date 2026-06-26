# graph/nodes/action.py
"""
Action Node - Executes the final decision.
Updates CRM, creates escalation records, and builds user response.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, add_error
from tools.crm_update import process_decision, auto_flag_fraud_if_exceeded
from tools.escalation import create_escalation, build_escalation_context


def action_node(state: AgentState) -> AgentState:
    """
    Execute the final decision.
    
    APPROVE: Update CRM, increment refund count, check fraud
    REJECT: Update CRM, no history change
    ESCALATE: Create escalation record, build context for human agent
    """
    
    final_decision = state.get("final_decision", "reject")
    request_id = state.get("request_id", "")
    customer_id = state.get("customer", {}).get("customer_id", "")
    order_id = state.get("order", {}).get("order_id", "")
    
    state = add_reasoning_log(
        state, "action", "action_started",
        f"Executing {final_decision.upper()} for {request_id}"
    )
    
    try:
        if final_decision == "approve":
            # Write decision to CRM
            result = process_decision(
                request_id=request_id,
                customer_id=customer_id,
                decision="approve"
            )
            state["crm_update_result"] = result
            
            # Check if fraud flag needed
            fraud_check = auto_flag_fraud_if_exceeded(customer_id, max_refunds=3)
            
            # Build response
            refund_amount = state.get("refund_amount", 0)
            refund_type = state.get("refund_type", "original_payment")
            
            state["response_text"] = (
                f"✅ Your refund has been approved!\n\n"
                f"Amount: ₹{refund_amount:,.2f}\n"
                f"Method: {refund_type.replace('_', ' ').title()}\n\n"
                f"The refund will be processed within 5-7 business days."
            )
            
            state = add_reasoning_log(
                state, "action", "approval_processed",
                f"CRM updated. Refund approved for ₹{refund_amount:,.2f}",
                {"crm_result": result, "fraud_flagged": fraud_check}
            )
            
        elif final_decision == "reject":
            # Write decision to CRM
            result = process_decision(
                request_id=request_id,
                customer_id=customer_id,
                decision="reject"
            )
            state["crm_update_result"] = result
            
            reason = state.get("decision_reason", "Policy violation")
            state["response_text"] = (
                f"❌ Your refund request has been declined.\n\n"
                f"Reason: {reason}\n\n"
                f"If you believe this is an error, please contact customer support."
            )
            
            state = add_reasoning_log(
                state, "action", "rejection_processed",
                f"CRM updated. Refund rejected: {reason[:100]}"
            )
            
        elif final_decision == "escalate":
            # Build escalation context
            context = build_escalation_context(
                customer=state.get("customer", {}),
                order=state.get("order", {}),
                refund_request=state.get("refund_request", {}),
                refund_history=state.get("refund_history", {}),
                eligibility_result=state.get("eligibility_result", {}),
                policy_chunks=state.get("policy_chunks", [])
            )
            
            # Create escalation record
            escalation_result = create_escalation(
                request_id=request_id,
                customer_id=customer_id,
                order_id=order_id,
                escalation_reason=state.get("eligibility_result", {}).get("escalation_reason", "unknown"),
                agent_notes=state.get("decision_reason", ""),
                context=context
            )
            state["escalation_result"] = escalation_result
            
            state["response_text"] = (
                f"⚠️ Your request requires additional review.\n\n"
                f"Reason: {state.get('decision_reason', 'Human review required')}\n\n"
                f"A support agent will review your case and respond within 24 hours.\n"
                f"Reference: {escalation_result.get('escalation_id', 'N/A')}"
            )
            
            state = add_reasoning_log(
                state, "action", "escalation_created",
                f"Escalation #{escalation_result.get('escalation_id')} created - "
                f"Priority: {escalation_result.get('priority')}",
                escalation_result
            )
        
        state["workflow_status"] = "completed"
    
    except Exception as e:
        state = add_error(state, "action", str(e))
        state = add_reasoning_log(
            state, "action", "action_error",
            f"Error executing decision: {str(e)}"
        )
    
    return state