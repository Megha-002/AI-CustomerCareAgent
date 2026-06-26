# graph/state.py
"""
LangGraph AgentState - Defines the state object that flows through all nodes.

The state carries:
  - User input (request_id, messages)
  - CRM data retrieved
  - Policy chunks from RAG
  - Eligibility results
  - Refund calculation
  - Final decision
  - Reasoning logs (for admin dashboard)
  - Error/retry tracking
"""

from typing import Dict, Any, List, Optional, TypedDict, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import operator


# ─── State Definition ───────────────────────────────────────

class AgentState(TypedDict):
    """
    The full state object passed between LangGraph nodes.
    
    Each node reads from and writes to this state.
    The state accumulates data as it flows through the workflow.
    """
    
    # ── Input ───────────────────────────────────────────────
    request_id: str                          # User-provided refund request ID (e.g., 'REF-7000')
    messages: List[Dict[str, Any]]           # Chat messages for the LLM
    user_input: str                          # Raw user input text
    voice_input: Optional[str]               # Transcribed voice input (if voice mode)
    
    # ── CRM Data ────────────────────────────────────────────
    customer: Optional[Dict[str, Any]]       # Customer record
    order: Optional[Dict[str, Any]]          # Order record
    refund_request: Optional[Dict[str, Any]] # Refund request record
    refund_history: Optional[Dict[str, Any]] # Refund history record
    crm_lookup_error: Optional[str]          # Error during CRM lookup
    
    # ── Policy Retrieval ────────────────────────────────────
    policy_query: Optional[str]              # Query sent to Pinecone
    policy_chunks: List[Dict[str, Any]]      # Retrieved policy sections
    policy_retrieval_error: Optional[str]    # Error during RAG
    
    # ── Eligibility ─────────────────────────────────────────
    eligibility_result: Optional[Dict[str, Any]]  # Full EligibilityResult
    eligibility_decision: Optional[str]           # 'approve', 'reject', 'escalate'
    eligibility_confidence: Optional[float]       # 0.0 to 1.0
    eligibility_details: Optional[Dict]           # Step-by-step checks
    eligibility_error: Optional[str]              # Error during eligibility check
    
    # ── Refund Calculation ──────────────────────────────────
    refund_calculation: Optional[Dict[str, Any]]  # Full RefundCalculation
    refund_amount: Optional[float]                # Final refund amount
    refund_type: Optional[str]                    # Payment method
    calculation_error: Optional[str]              # Error during calculation
    
    # ── Final Decision ──────────────────────────────────────
    final_decision: Optional[str]           # 'approve', 'reject', 'escalate'
    decision_reason: Optional[str]          # Human-readable reason
    escalation_result: Optional[Dict]       # Escalation record if escalated
    crm_update_result: Optional[Dict]       # Result of DB update
    
    # ── Reasoning Logs ──────────────────────────────────────
    reasoning_logs: Annotated[List[Dict[str, Any]], operator.add]  # Step-by-step logs
    
    # ── Error & Retry Tracking ──────────────────────────────
    errors: List[Dict[str, Any]]            # Any errors encountered
    retry_count: int                        # Number of retries attempted
    current_node: str                       # Current node being executed
    workflow_status: str                    # 'running', 'completed', 'failed'
    
    # ── Response ────────────────────────────────────────────
    response_text: Optional[str]            # Final response to user
    response_data: Optional[Dict]           # Structured response data


# ─── Helper Functions ───────────────────────────────────────

def create_initial_state(request_id: str, user_input: str = "") -> AgentState:
    """
    Create the initial state for a new workflow run.
    
    Args:
        request_id: The refund request ID to process
        user_input: Raw user input text
    
    Returns:
        Initialized AgentState
    """
    return AgentState(
        # Input
        request_id=request_id,
        messages=[],
        user_input=user_input,
        voice_input=None,
        
        # CRM Data (empty until lookup)
        customer=None,
        order=None,
        refund_request=None,
        refund_history=None,
        crm_lookup_error=None,
        
        # Policy (empty until retrieval)
        policy_query=None,
        policy_chunks=[],
        policy_retrieval_error=None,
        
        # Eligibility (empty until checked)
        eligibility_result=None,
        eligibility_decision=None,
        eligibility_confidence=None,
        eligibility_details=None,
        eligibility_error=None,
        
        # Calculation (empty until calculated)
        refund_calculation=None,
        refund_amount=None,
        refund_type=None,
        calculation_error=None,
        
        # Decision (empty until final)
        final_decision=None,
        decision_reason=None,
        escalation_result=None,
        crm_update_result=None,
        
        # Reasoning logs (accumulated via operator.add)
        reasoning_logs=[],
        
        # Error tracking
        errors=[],
        retry_count=0,
        current_node="intake",
        workflow_status="running",
        
        # Response (empty until end)
        response_text=None,
        response_data=None
    )


def add_reasoning_log(state: AgentState, node: str, action: str, detail: str, data: Any = None) -> AgentState:
    """
    Add a reasoning log entry for the admin dashboard.
    
    Args:
        state: Current AgentState
        node: Node name (e.g., 'crm_lookup', 'eligibility')
        action: What action was taken
        detail: Human-readable detail
        data: Optional structured data
    
    Returns:
        Updated AgentState
    """
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "node": node,
        "action": action,
        "detail": detail,
        "data": data
    }
    state["reasoning_logs"].append(log_entry)
    state["current_node"] = node
    return state


def add_error(state: AgentState, node: str, error: str, recoverable: bool = True) -> AgentState:
    """
    Record an error in the state.
    
    Args:
        state: Current AgentState
        node: Node where error occurred
        error: Error message
        recoverable: Whether the workflow can continue
    
    Returns:
        Updated AgentState
    """
    error_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "node": node,
        "error": error,
        "recoverable": recoverable
    }
    state["errors"].append(error_entry)
    
    if not recoverable:
        state["workflow_status"] = "failed"
        state["response_text"] = f"Error in {node}: {error}"
    
    return state


# ─── State Summary (for logging/debugging) ──────────────────

def get_state_summary(state: AgentState) -> Dict[str, Any]:
    """
    Get a summary of the current state for debugging.
    """
    return {
        "request_id": state.get("request_id"),
        "workflow_status": state.get("workflow_status"),
        "current_node": state.get("current_node"),
        "customer_name": state.get("customer", {}).get("name") if state.get("customer") else None,
        "product_category": state.get("order", {}).get("product_category") if state.get("order") else None,
        "purchase_amount": state.get("order", {}).get("purchase_amount") if state.get("order") else None,
        "eligibility_decision": state.get("eligibility_decision"),
        "final_decision": state.get("final_decision"),
        "refund_amount": state.get("refund_amount"),
        "total_logs": len(state.get("reasoning_logs", [])),
        "total_errors": len(state.get("errors", []))
    }


# ─── Self-Test ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("AgentState - Self Test")
    print("=" * 60)
    
    # Test state creation
    print("\n--- Test: Create Initial State ---")
    state = create_initial_state("REF-7000", "I want a refund")
    print(f"  Request ID: {state['request_id']}")
    print(f"  User Input: {state['user_input']}")
    print(f"  Status: {state['workflow_status']}")
    print(f"  Current Node: {state['current_node']}")
    
    # Test reasoning logs
    print("\n--- Test: Add Reasoning Logs ---")
    state = add_reasoning_log(state, "crm_lookup", "lookup_complete", 
                              "Retrieved complete case for REF-7000", 
                              {"customer": "Customer 1"})
    state = add_reasoning_log(state, "eligibility", "check_complete",
                              "All checks passed, decision: approve",
                              {"decision": "approve", "confidence": 0.95})
    print(f"  Total logs: {len(state['reasoning_logs'])}")
    for log in state['reasoning_logs']:
        print(f"  [{log['node']}] {log['action']}: {log['detail'][:60]}...")
    
    # Test error handling
    print("\n--- Test: Add Error ---")
    state = add_error(state, "crm_lookup", "Customer not found", recoverable=False)
    print(f"  Total errors: {len(state['errors'])}")
    print(f"  Status: {state['workflow_status']}")
    print(f"  Response: {state['response_text']}")
    
    # Test state summary
    print("\n--- Test: State Summary ---")
    summary = get_state_summary(state)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print(f"\n{'=' * 60}")
    print("Self-test complete")