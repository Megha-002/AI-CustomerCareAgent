"""
Policy Retrieval Node

Uses the LLM to determine WHAT to search for in the policy,
then queries Pinecone via the actual PolicySearch class instance,
and formats results as LLM-readable context.

FIXED: Uses `policy_search.search()` (the class instance method)
instead of a non-existent `search_policy()` function.
"""

import json
import logging
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# ✅ CORRECT: Import the class instance, not a standalone function
from tools.policy_search import policy_search

from graph.state import AgentState

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """You are generating a search query to find relevant refund policy rules.

Given the customer's refund request and the order details, generate a SHORT search query (5-15 words) that would find the most relevant policy sections.

Focus on:
- The product category (physical, digital, perishable, etc.)
- The reason for refund (defective, changed mind, wrong item, etc.)
- The customer's tier (Bronze, Silver, Gold)
- Any time-related concerns (how many days, past window, etc.)

RESPOND WITH ONLY THE SEARCH QUERY — no JSON, no explanation, just the query text.

Examples:
- "physical product refund window return policy"
- "digital download refund eligibility"
- "Gold member extended return window"
- "perishable food item refund policy"
- "fraud flag refund velocity check"
"""


def _generate_search_query(state: AgentState) -> str:
    """Use LLM to generate an appropriate policy search query."""

    parts = []
    parts.append(f"Customer Request: {state.get('user_input', '')}")

    entities = state.get("entities") or {}
    if entities.get("product"):
        parts.append(f"Product: {entities['product']}")
    if entities.get("reason"):
        parts.append(f"Reason: {entities['reason']}")

    # Add product category from CRM data if available
    crm_data = state.get("crm_data") or {}
    order = crm_data.get("order") or {}
    if order.get("product_category"):
        parts.append(f"Product Category: {order['product_category']}")

    customer = crm_data.get("customer") or {}
    if customer.get("tier"):
        parts.append(f"Customer Tier: {customer['tier']}")

    refund_history = crm_data.get("refund_history") or {}
    if refund_history.get("fraud_flag"):
        parts.append("NOTE: Customer has fraud flag")

    context = "\n".join(parts)

    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            max_tokens=50,
        )

        response = llm.invoke([
            SystemMessage(content=QUERY_GENERATION_PROMPT),
            HumanMessage(content=context)
        ])

        query = response.content.strip().strip('"').strip("'")
        logger.info(f"LLM generated search query: {query}")
        return query

    except Exception as e:
        logger.warning(f"Failed to generate search query with LLM: {e}")
        fallback_parts = ["refund policy"]
        if order.get("product_category"):
            fallback_parts.append(order["product_category"])
        if entities.get("reason"):
            fallback_parts.append(entities["reason"])
        return " ".join(fallback_parts[:4])


def _format_policy_chunks(chunks: list) -> str:
    """Format retrieved policy chunks into readable text for the LLM."""
    if not chunks:
        return "No relevant policy sections were found. This may indicate a gap in the policy documentation."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        heading = chunk.get("section", chunk.get("heading", "Untitled Section"))
        text = chunk.get("text", "")
        score = chunk.get("score", 0)

        parts.append(f"#### Section {i}: {heading}")
        parts.append(f"(Relevance score: {score:.3f})")
        parts.append(text)
        parts.append("")

    return "\n".join(parts)


def policy_retrieval_node(state: AgentState) -> dict:
    """
    Generate search query with LLM, retrieve policy chunks, format as context.

    Consumes: user_input, entities, crm_data
    Produces: policy_query, policy_chunks, policy_context, policy_retrieval_reasoning, reasoning_log
    """
    node_start = datetime.utcnow().isoformat()

    # Step 1: LLM generates the search query
    query = _generate_search_query(state)

    # Step 2: Search Pinecone via the class instance method
    chunks = []
    try:
        # ✅ CORRECT: Call .search() on the PolicySearch instance
        results = policy_search.search(query, top_k=5)

        # The PolicySearch.search() returns list of dicts with keys:
        #   text, heading, score (based on actual implementation)
        if isinstance(results, list):
            chunks = results
        elif isinstance(results, dict) and "results" in results:
            chunks = results["results"]
        else:
            logger.warning(f"Unexpected return type from policy_search.search(): {type(results)}")
            chunks = []

        logger.info(f"Retrieved {len(chunks)} policy chunks for query: {query}")

    except Exception as e:
        logger.error(f"Policy search failed: {e}")
        return {
            "policy_query": query,
            "policy_chunks": [],
            "policy_context": "Policy search failed — could not retrieve policy rules. Escalation recommended.",
            "policy_retrieval_reasoning": f"Search failed: {e}",
            "reasoning_log": [{
                "node": "policy_retrieval",
                "timestamp": node_start,
                "input_summary": f"query={query}",
                "output_summary": "ERROR - no chunks retrieved",
                "thinking": str(e)
            }],
            "errors": [f"Policy retrieval failed: {e}"],
        }

    # Step 3: Format chunks as LLM-readable context
    policy_context = _format_policy_chunks(chunks)

    return {
        "policy_query": query,
        "policy_chunks": chunks,
        "policy_context": policy_context,
        "policy_retrieval_reasoning": f"Generated query '{query}', retrieved {len(chunks)} chunks",
        "reasoning_log": [{
            "node": "policy_retrieval",
            "timestamp": node_start,
            "input_summary": f"query={query}",
            "output_summary": f"{len(chunks)} chunks retrieved, {len(policy_context)} chars formatted",
            "thinking": "LLM generated targeted query based on product category, reason, and customer tier"
        }],
    }