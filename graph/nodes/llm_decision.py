"""
LLM Decision Node — THE CORE OF THE SYSTEM

This is where the AI actually thinks. It receives:
  1. CRM context (formatted customer/order/refund history)
  2. Policy context (relevant policy chunks from RAG)

It evaluates both and decides:
  - APPROVE: Policy allows this refund
  - REJECT: Policy does not allow this refund
  - ESCALATE: LLM is unsure or case is complex

The LLM ALSO generates the customer-facing response message.
NO HARDCODED RULES. The LLM does all evaluation.

Only reads state fields — does NOT call any CRM tools.
All state fields referenced here exist in AgentState.
"""

import json
import logging
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import AgentState

logger = logging.getLogger(__name__)

DECISION_SYSTEM_PROMPT = """You are a senior customer support agent specializing in refund decisions. You have access to two critical pieces of information:

1. **CRM DATA** — The customer's profile, order details, and refund history
2. **POLICY CONTEXT** — The relevant refund policy rules retrieved from our knowledge base

YOUR JOB:
- Carefully read BOTH the CRM data and the policy context
- Evaluate whether the refund request is permitted under policy
- Consider ALL factors: time windows, product category, item condition, customer tier, refund history, fraud indicators
- Make a clear decision: APPROVE, REJECT, or ESCALATE

DECISION CRITERIA:
- APPROVE: The policy clearly supports granting this refund
- REJECT: The policy clearly does NOT support this refund (explain which rule applies)
- ESCALATE: You are uncertain, the case is ambiguous, policy is conflicting, or this seems like an exception that needs human judgment

CONFIDENCE:
- 0.9-1.0: Very clear cut, policy is unambiguous
- 0.7-0.89: Mostly clear but some interpretation needed
- 0.5-0.69: Ambiguous, consider ESCALATE
- Below 0.5: Definitely ESCALATE

IMPORTANT RULES:
- Never approve a refund that policy explicitly forbids
- Never reject a refund that policy explicitly allows
- When in doubt, ESCALATE — it's better to have a human review than make a wrong decision
- Gold tier members may have extended windows — check carefully
- Fraud flags are serious — if fraud_flag is True, strongly consider ESCALATE unless policy is crystal clear
- Digital products and perishables have shorter/no refund windows
- Always explain your reasoning thoroughly

RESPONSE FORMAT:
You MUST respond with valid JSON in this exact format (no markdown, no code fences, just raw JSON):

{
  "decision": "APPROVE" | "REJECT" | "ESCALATE",
  "confidence": 0.0-1.0,
  "reason": "Your detailed reasoning explaining which policy rules apply and why you made this decision",
  "customer_response": "A polite, professional message to the customer explaining the decision. Use their name. Be empathetic but clear. For APPROVE: explain refund timeline and next steps. For REJECT: NEVER mention fraud flags, refund velocity, internal risk scores, or that the customer is flagged. Instead use vague but professional language like 'your request does not meet our current refund criteria' or 'we are unable to process this refund at this time' and invite them to contact support for more details. For ESCALATE: explain that a specialist is reviewing their case and give a timeframe."
}

DO NOT include any text outside the JSON object."""


def _build_decision_prompt(state: AgentState) -> str:
    """Build the human message with CRM + Policy context for the LLM."""
    parts = []

    # User's original request
    parts.append("## CUSTOMER'S REFUND REQUEST")
    parts.append(state.get("user_input", "No input provided"))
    parts.append("")

    # CRM context (formatted by crm_lookup node)
    crm_context = state.get("crm_context", "")
    if crm_context:
        parts.append("## CRM DATA")
        parts.append(crm_context)
        parts.append("")
    else:
        parts.append("## CRM DATA")
        parts.append("WARNING: No CRM data was retrieved. This may indicate a lookup failure.")
        parts.append("")

    # Policy context (formatted by policy_retrieval node)
    policy_context = state.get("policy_context", "")
    if policy_context:
        parts.append("## APPLICABLE POLICY RULES")
        parts.append(policy_context)
        parts.append("")
    else:
        parts.append("## APPLICABLE POLICY RULES")
        parts.append("WARNING: No policy context was retrieved. ESCALATE this case.")
        parts.append("")

    # Intent and entities from intake
    intent = state.get("intent", "unknown")
    entities = state.get("entities") or {}
    parts.append("## INTAKE ANALYSIS")
    parts.append(f"Classified intent: {intent}")
    if entities:
        parts.append(f"Extracted entities: {json.dumps(entities, default=str)}")
    parts.append("")

    return "\n".join(parts)


def _parse_llm_response(raw_response: str) -> dict:
    """
    Parse the LLM's JSON response.
    Returns dict with decision, confidence, reason, customer_response.
    On any parse failure, returns an ESCALATE decision.
    """
    # Try direct JSON parse
    try:
        parsed = json.loads(raw_response.strip())
        if all(k in parsed for k in ["decision", "confidence", "reason", "customer_response"]):
            if parsed["decision"] not in ("APPROVE", "REJECT", "ESCALATE"):
                raise ValueError(f"Invalid decision: {parsed['decision']}")
            conf = float(parsed["confidence"])
            if not (0.0 <= conf <= 1.0):
                raise ValueError(f"Confidence out of range: {conf}")
            return parsed
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Direct JSON parse failed: {e}")

    # Try extracting JSON from markdown code fences
    try:
        if "```json" in raw_response:
            json_str = raw_response.split("```json")[1].split("```")[0].strip()
            parsed = json.loads(json_str)
            if all(k in parsed for k in ["decision", "confidence", "reason", "customer_response"]):
                if parsed["decision"] in ("APPROVE", "REJECT", "ESCALATE"):
                    return parsed
        elif "```" in raw_response:
            json_str = raw_response.split("```")[1].split("```")[0].strip()
            parsed = json.loads(json_str)
            if all(k in parsed for k in ["decision", "confidence", "reason", "customer_response"]):
                if parsed["decision"] in ("APPROVE", "REJECT", "ESCALATE"):
                    return parsed
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"Fenced JSON parse failed: {e}")

    # All parsing failed — ESCALATE
    logger.error(f"Could not parse LLM response as JSON. Raw: {raw_response[:500]}")
    return {
        "decision": "ESCALATE",
        "confidence": 0.0,
        "reason": "LLM response parsing failed. Raw response could not be parsed as valid JSON. Escalating to human review.",
        "customer_response": (
            "I'm sorry, but I'm experiencing a technical issue processing your request. "
            "A specialist has been notified and will review your case shortly. "
            "You'll receive an update within 24 hours."
        ),
    }


def llm_decision_node(state: AgentState) -> dict:
    """
    THE CORE NODE — LLM makes the refund decision.

    Consumes: user_input, crm_context, policy_context, intent, entities
    Produces: llm_decision_raw, decision, confidence, decision_reason,
              customer_response, decision_reasoning, reasoning_log
    """
    node_start = datetime.utcnow().isoformat()
    logger.info("=== LLM DECISION NODE STARTED ===")

    # Get or create LLM instance
    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return {
            "llm_decision_raw": None,
            "decision": "ESCALATE",
            "confidence": 0.0,
            "decision_reason": f"LLM initialization failed: {str(e)}",
            "customer_response": (
                "I'm sorry, but I'm unable to process your request at this moment "
                "due to a system issue. A specialist will review your case and "
                "contact you within 24 hours."
            ),
            "decision_reasoning": "Escalated due to LLM initialization failure",
            "reasoning_log": [{
                "node": "llm_decision",
                "timestamp": node_start,
                "input_summary": "LLM initialization attempted",
                "output_summary": "ESCALATE - initialization failed",
                "thinking": str(e)
            }],
            "errors": [f"LLM initialization failed: {e}"],
        }

    # Build the prompt
    human_prompt = _build_decision_prompt(state)

    logger.info("Sending decision prompt to LLM...")
    logger.debug(f"CRM context length: {len(state.get('crm_context') or '')}")
    logger.debug(f"Policy context length: {len(state.get('policy_context') or '')}")

    # Call the LLM
    try:
        response = llm.invoke([
            SystemMessage(content=DECISION_SYSTEM_PROMPT),
            HumanMessage(content=human_prompt)
        ])
        raw_response = response.content
        logger.info(f"LLM responded with {len(raw_response)} characters")
        logger.debug(f"Raw LLM response: {raw_response[:500]}")

    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        return {
            "llm_decision_raw": None,
            "decision": "ESCALATE",
            "confidence": 0.0,
            "decision_reason": f"LLM invocation failed: {str(e)}",
            "customer_response": (
                "I'm sorry, but I'm experiencing a technical issue processing your request. "
                "A specialist has been notified and will review your case shortly."
            ),
            "decision_reasoning": "Escalated due to LLM invocation failure",
            "reasoning_log": [{
                "node": "llm_decision",
                "timestamp": node_start,
                "input_summary": "LLM invocation attempted",
                "output_summary": "ESCALATE - invocation failed",
                "thinking": str(e)
            }],
            "errors": [f"LLM invocation failed: {e}"],
        }

    # Parse the response
    parsed = _parse_llm_response(raw_response)

    decision = parsed["decision"]
    confidence = parsed["confidence"]
    reason = parsed["reason"]
    customer_response = parsed["customer_response"]

    # Safety: if confidence is very low, override to ESCALATE
    if decision != "ESCALATE" and confidence < 0.5:
        logger.warning(f"Low confidence ({confidence}) for {decision} — overriding to ESCALATE")
        original_decision = decision
        decision = "ESCALATE"
        reason = (
            f"[OVERRIDDEN] Original decision was {original_decision} with confidence "
            f"{confidence:.2f} (below 0.5 threshold). {reason}"
        )
        customer_response = (
            "I've reviewed your request, but due to the complexity of your case, "
            "I'd like a specialist to take a closer look. They'll review all the "
            "details and get back to you within 24 hours with a final decision."
        )

    log_entry = {
        "node": "llm_decision",
        "timestamp": node_start,
        "input_summary": (
            f"CRM context: {len(state.get('crm_context') or '')} chars, "
            f"Policy context: {len(state.get('policy_context') or '')} chars"
        ),
        "output_summary": f"{decision} (confidence: {confidence:.2f})",
        "thinking": reason[:500],
    }

    logger.info(f"LLM Decision: {decision} with confidence {confidence:.2f}")
    logger.info(f"Reason: {reason[:200]}...")

    return {
        "llm_decision_raw": raw_response,
        "decision": decision,
        "confidence": confidence,
        "decision_reason": reason,
        "customer_response": customer_response,
        "decision_reasoning": (
            f"LLM evaluated CRM data and policy context. "
            f"Decided {decision} with {confidence:.2f} confidence."
        ),
        "reasoning_log": [log_entry],
    }