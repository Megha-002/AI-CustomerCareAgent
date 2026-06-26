"""
LangGraph Workflow Definition

Defines the state machine for refund processing.
Linear flow — no conditional routing needed because
the LLM makes all decisions in llm_decision_node.
"""

import logging

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    intake_node,
    crm_lookup_node,
    policy_retrieval_node,
    llm_decision_node,
    action_node,
    logging_node,
)

logger = logging.getLogger(__name__)


def build_workflow() -> StateGraph:
    """
    Build the refund processing workflow.

    Flow:
        intake -> crm_lookup -> policy_retrieval -> llm_decision -> action -> logging -> END

    All business decisions are made in llm_decision_node by the LLM.
    All other nodes only fetch, format, and execute.
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("crm_lookup", crm_lookup_node)
    workflow.add_node("policy_retrieval", policy_retrieval_node)
    workflow.add_node("llm_decision", llm_decision_node)
    workflow.add_node("action", action_node)
    workflow.add_node("logging", logging_node)

    # Linear flow
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "crm_lookup")
    workflow.add_edge("crm_lookup", "policy_retrieval")
    workflow.add_edge("policy_retrieval", "llm_decision")
    workflow.add_edge("llm_decision", "action")
    workflow.add_edge("action", "logging")
    workflow.add_edge("logging", END)

    logger.info(
        "Workflow built: intake -> crm_lookup -> policy_retrieval -> "
        "llm_decision -> action -> logging -> END"
    )

    return workflow


def compile_workflow():
    """Compile the workflow into a runnable graph."""
    workflow = build_workflow()
    return workflow.compile()


# Singleton compiled workflow
_app = None


def get_workflow():
    """Get or create the compiled workflow singleton."""
    global _app
    if _app is None:
        _app = compile_workflow()
        logger.info("Workflow compiled successfully")
    return _app


async def process_refund_request(
    user_input: str,
    customer_id: str = None,
    order_id: str = None,
) -> dict:
    """
    High-level async function to process a refund request.

    Args:
        user_input: The customer's message
        customer_id: Optional pre-identified customer
        order_id: Optional pre-identified order

    Returns:
        dict with: response, decision, confidence, reasoning_log, errors
    """
    from datetime import datetime

    workflow = get_workflow()

    initial_state = {
        "user_input": user_input,
        "customer_id": customer_id,
        "order_id": order_id,
        "started_at": datetime.utcnow().isoformat(),
        "reasoning_log": [],
        "errors": [],
    }

    try:
        final_state = await workflow.ainvoke(initial_state)
        final_state["completed_at"] = datetime.utcnow().isoformat()
        return final_state
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        return {
            **initial_state,
            "response": (
                "I'm sorry, an error occurred while processing your request. "
                "A specialist has been notified."
            ),
            "decision": "ESCALATE",
            "confidence": 0.0,
            "errors": [f"Workflow failed: {e}"],
            "completed_at": datetime.utcnow().isoformat(),
        }


def process_refund_request_sync(
    user_input: str,
    customer_id: str = None,
    order_id: str = None,
) -> dict:
    """Synchronous version for testing."""
    from datetime import datetime

    workflow = get_workflow()

    initial_state = {
        "user_input": user_input,
        "customer_id": customer_id,
        "order_id": order_id,
        "started_at": datetime.utcnow().isoformat(),
        "reasoning_log": [],
        "errors": [],
    }

    try:
        final_state = workflow.invoke(initial_state)
        final_state["completed_at"] = datetime.utcnow().isoformat()
        return final_state
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        return {
            **initial_state,
            "response": (
                "I'm sorry, an error occurred while processing your request. "
                "A specialist has been notified."
            ),
            "decision": "ESCALATE",
            "confidence": 0.0,
            "errors": [f"Workflow failed: {e}"],
            "completed_at": datetime.utcnow().isoformat(),
        }