"""
Intake Node — LLM analyzes user input.

The LLM classifies intent and extracts entities.
NO decisions about approval/rejection are made here.
NO references to state fields that don't exist.
"""

import json
import logging
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import AgentState

logger = logging.getLogger(__name__)

INTAKE_SYSTEM_PROMPT = """You are the first stage of a customer support refund processing system. Your ONLY job is to analyze the customer's message and extract structured information.

DO NOT make any refund decisions. DO NOT check policy. DO NOT approve or reject anything.

CLASSIFY THE INTENT:
- "refund_request": Customer wants to request a refund for an order
- "refund_status": Customer is asking about an existing refund's status
- "general": Customer is asking a general question, not specifically about refunds

EXTRACT ENTITIES (if present):
- order_id: Any order identifier (e.g., "ORD-001", "order 123", etc.)
- customer_id: Any customer identifier (e.g., "CUST-001", "customer 456")
- product: What product they mention
- reason: Why they want a refund (e.g., "defective", "wrong item", "changed mind")
- amount_requested: Any specific refund amount mentioned

RESPOND WITH VALID JSON (no markdown, no code fences):

{
  "intent": "refund_request" | "refund_status" | "general",
  "entities": {
    "order_id": null | "extracted value",
    "customer_id": null | "extracted value",
    "product": null | "extracted value",
    "reason": null | "extracted value",
    "amount_requested": null | "extracted value"
  },
  "reasoning": "Brief explanation of why you classified this way"
}

If a field isn't found, use null. Don't guess or infer values that aren't clearly stated."""


def _parse_intake_response(raw: str) -> dict:
    """Parse intake LLM response. Returns safe defaults on failure."""
    try:
        parsed = json.loads(raw.strip())
        if "intent" in parsed and parsed["intent"] in ("refund_request", "refund_status", "general"):
            return {
                "intent": parsed["intent"],
                "entities": parsed.get("entities", {}),
                "reasoning": parsed.get("reasoning", "")
            }
    except (json.JSONDecodeError, TypeError):
        pass

    # Try fenced JSON
    try:
        if "```" in raw:
            json_str = raw.split("```")[1].split("```")[0].strip()
            if json_str.startswith("json"):
                json_str = json_str[4:].strip()
            parsed = json.loads(json_str)
            if "intent" in parsed:
                return {
                    "intent": parsed["intent"],
                    "entities": parsed.get("entities", {}),
                    "reasoning": parsed.get("reasoning", "")
                }
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: treat as general query
    logger.warning(f"Could not parse intake response, defaulting to 'general'. Raw: {raw[:200]}")
    return {
        "intent": "general",
        "entities": {},
        "reasoning": "Failed to parse LLM response, defaulting to general intent"
    }


def intake_node(state: AgentState) -> dict:
    """
    Analyze user input using LLM.

    Consumes: user_input
    Produces: intent, entities, intake_reasoning, customer_id, order_id, reasoning_log
    """
    node_start = datetime.utcnow().isoformat()
    user_input = state.get("user_input", "")

    if not user_input.strip():
        logger.warning("Empty user input received")
        return {
            "intent": "general",
            "entities": {},
            "intake_reasoning": "Empty input received",
            "reasoning_log": [{
                "node": "intake",
                "timestamp": node_start,
                "input_summary": "empty input",
                "output_summary": "general intent (empty)",
                "thinking": "No input to analyze"
            }]
        }

    logger.info(f"Intake analyzing: {user_input[:100]}...")

    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_tokens=512,
        )

        response = llm.invoke([
            SystemMessage(content=INTAKE_SYSTEM_PROMPT),
            HumanMessage(content=user_input)
        ])

        parsed = _parse_intake_response(response.content)
        intent = parsed["intent"]
        entities = parsed["entities"]
        reasoning = parsed["reasoning"]

        # Build return dict — only fields that exist in AgentState
        result = {
            "intent": intent,
            "entities": entities,
            "intake_reasoning": reasoning,
            "reasoning_log": [{
                "node": "intake",
                "timestamp": node_start,
                "input_summary": user_input[:200],
                "output_summary": f"intent={intent}, entities={json.dumps(entities, default=str)}",
                "thinking": reasoning
            }]
        }

        # Promote extracted IDs to top-level state fields
        if entities.get("customer_id"):
            result["customer_id"] = entities["customer_id"]
        if entities.get("order_id"):
            result["order_id"] = entities["order_id"]

        logger.info(f"Intake result: intent={intent}, entities={entities}")
        return result

    except Exception as e:
        logger.error(f"Intake LLM call failed: {e}")
        return {
            "intent": "general",
            "entities": {},
            "intake_reasoning": f"LLM call failed: {e}",
            "reasoning_log": [{
                "node": "intake",
                "timestamp": node_start,
                "input_summary": user_input[:200],
                "output_summary": "general intent (error fallback)",
                "thinking": str(e)
            }],
            "errors": [f"Intake failed: {e}"]
        }