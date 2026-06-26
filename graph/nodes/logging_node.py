"""
Logging Node — Final node in the workflow.

Records the complete state to logs.
Does not make any decisions or business logic.
Only reads fields that exist in AgentState.
"""

import logging
from datetime import datetime

from graph.state import AgentState

logger = logging.getLogger(__name__)


def logging_node(state: AgentState) -> dict:
    """
    Log the final state of the workflow.

    Consumes: decision, confidence, response, errors, reasoning_log
    Produces: completed_at, reasoning_log (appended)
    """
    completed_at = datetime.utcnow().isoformat()

    # ✅ All fields read here exist in AgentState
    decision = state.get("decision", "UNKNOWN")
    confidence = state.get("confidence") or 0
    response = state.get("response", "")
    errors = state.get("errors") or []
    reasoning_log = state.get("reasoning_log") or []

    # Log summary
    logger.info("=" * 60)
    logger.info("WORKFLOW COMPLETED")
    logger.info(f"  Decision: {decision}")
    logger.info(f"  Confidence: {confidence:.2f}")
    logger.info(f"  Errors: {len(errors)}")
    logger.info(f"  Reasoning steps: {len(reasoning_log)}")
    logger.info(f"  Response length: {len(response)} chars")
    logger.info("=" * 60)

    # Log each reasoning step
    for step in reasoning_log:
        logger.info(
            f"  [{step.get('node', '?')}] {step.get('output_summary', '')}"
        )

    # Log errors if any
    for error in errors:
        logger.error(f"  ERROR: {error}")

    # Log full response for audit
    if response:
        logger.debug(f"  Full response: {response[:500]}")

    return {
        "completed_at": completed_at,
        "reasoning_log": [{
            "node": "logging",
            "timestamp": completed_at,
            "input_summary": f"decision={decision}, confidence={confidence:.2f}",
            "output_summary": "Workflow logged successfully",
            "thinking": "Passive logging node — no decisions made",
        }],
    }