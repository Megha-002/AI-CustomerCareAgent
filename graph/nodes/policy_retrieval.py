# graph/nodes/policy_retrieval.py
"""
Policy Retrieval Node - Searches Pinecone for relevant policy sections.
Uses RAG to find policy rules matching the refund scenario.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from graph.state import AgentState, add_reasoning_log, add_error
from tools.policy_search import policy_search


def policy_retrieval_node(state: AgentState) -> AgentState:
    """
    Retrieve relevant policy sections from Pinecone.
    
    Uses the policy_query built during intake to search the vector DB.
    Populates state with policy_chunks.
    """
    
    policy_query = state.get("policy_query", "")
    refund_reason = state.get("refund_request", {}).get("refund_reason", "")
    
    # Build a comprehensive query
    product_category = state.get("order", {}).get("product_category", "")
    customer_tier = state.get("customer", {}).get("tier", "")
    
    # Enrich query with CRM context
    enriched_query = (
        f"{policy_query} "
        f"Product category: {product_category}. "
        f"Customer tier: {customer_tier}. "
        f"Refund reason: {refund_reason}."
    )
    
    # Log: Policy retrieval started
    state = add_reasoning_log(
        state, "policy_retrieval", "retrieval_started",
        f"Searching policy for: {enriched_query[:120]}..."
    )
    
    try:
        results = policy_search.search(enriched_query, top_k=3)
        
        if not results:
            state["policy_chunks"] = []
            state = add_reasoning_log(
                state, "policy_retrieval", "no_results",
                "No matching policy sections found"
            )
        else:
            state["policy_chunks"] = results
            
            # Log retrieved sections
            sections = [r.get("section", "Unknown") for r in results]
            scores = [f"{r.get('score', 0):.2f}" for r in results]
            
            state = add_reasoning_log(
                state, "policy_retrieval", "retrieval_complete",
                f"Retrieved {len(results)} policy sections: {', '.join(sections)}",
                {
                    "sections": sections,
                    "scores": scores,
                    "top_score": results[0].get("score", 0) if results else 0
                }
            )
    
    except Exception as e:
        state = add_error(state, "policy_retrieval", str(e))
        state = add_reasoning_log(
            state, "policy_retrieval", "retrieval_error",
            f"Error retrieving policy: {str(e)}"
        )
    
    return state