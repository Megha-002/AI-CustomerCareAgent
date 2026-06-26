"""
Agent State Definition

TypedDict that flows through the LangGraph workflow.
Contains ALL data — no business logic lives here.
"""

from typing import TypedDict, Optional, Annotated, Any
from datetime import datetime
import operator


class ReasoningLog(TypedDict):
    """Single entry in the reasoning chain."""
    node: str
    timestamp: str
    input_summary: str
    output_summary: str
    thinking: str


class AgentState(TypedDict):
    """
    Master state that flows through every node.

    DESIGN PRINCIPLE: This state carries DATA ONLY.
    No decisions are made by Python code. The LLM evaluates
    the data in this state and makes all business decisions.
    """

    # ─── INPUT ─────────────────────────────────────────────
    user_input: str
    customer_id: Optional[str]
    order_id: Optional[str]

    # ─── INTAKE OUTPUT ────────────────────────────────────
    intent: Optional[str]
    entities: Optional[dict]
    intake_reasoning: Optional[str]

    # ─── CRM LOOKUP OUTPUT ────────────────────────────────
    crm_data: Optional[dict]
    crm_context: Optional[str]
    crm_lookup_reasoning: Optional[str]

    # ─── POLICY RETRIEVAL OUTPUT ──────────────────────────
    policy_query: Optional[str]
    policy_chunks: Optional[list]
    policy_context: Optional[str]
    policy_retrieval_reasoning: Optional[str]

    # ─── LLM DECISION OUTPUT (THE CORE) ───────────────────
    llm_decision_raw: Optional[str]
    decision: Optional[str]
    confidence: Optional[float]
    decision_reason: Optional[str]
    customer_response: Optional[str]
    decision_reasoning: Optional[str]

    # ─── ACTION OUTPUT ────────────────────────────────────
    action_taken: Optional[str]
    refund_amount: Optional[float]
    refund_id: Optional[str]
    escalation_id: Optional[str]

    # ─── FINAL OUTPUT ─────────────────────────────────────
    response: Optional[str]

    # ─── METADATA & LOGGING ───────────────────────────────
    reasoning_log: Annotated[list[ReasoningLog], operator.add]
    errors: Annotated[list[str], operator.add]
    started_at: Optional[str]
    completed_at: Optional[str]