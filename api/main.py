"""
FastAPI Backend for AI Customer Support Agent

Endpoints:
  POST /chat  — Conversational refund processing
  GET  /health — Health check
  GET  /metrics — Prometheus metrics
"""

import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.workflow import process_refund_request_sync
from graph.state import AgentState

logger = logging.getLogger("api")

# ─── App Setup ─────────────────────────────────────────────

app = FastAPI(
    title="AI Customer Support Agent",
    description="Refund processing agent with LLM-powered decision making",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    decision: Optional[str] = None
    confidence: Optional[float] = None
    reasoning_log: List[Dict[str, Any]] = []
    errors: List[str] = []
    requires_action: bool = False
    action_type: Optional[str] = None
    # NEW: Include reasoning details in response for frontend
    decision_reason: Optional[str] = None
    policy_cited: Optional[str] = None
    customer_id: Optional[str] = None


# ─── Session Store (in-memory, replace with Redis for production) ──

sessions: Dict[str, Dict[str, Any]] = {}


def get_or_create_session(session_id: Optional[str]) -> str:
    """Get existing session or create new one."""
    if session_id and session_id in sessions:
        return session_id
    
    new_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    sessions[new_id] = {
        "created_at": datetime.now().isoformat(),
        "messages": [],
        "customer_id": None,
        "order_id": None,
        "awaiting": None,
        # NEW: Store reasoning for admin dashboard
        "last_reasoning": [],
        "last_decision_reason": "",
        "last_policy_cited": "",
    }
    return new_id


# ─── Helper: Determine if we need more info ────────────────

def needs_more_info(state: Dict[str, Any]) -> Optional[str]:
    """Check if the workflow needs more info. Returns prompt or None."""
    crm_data = state.get("crm_data") or {}
    
    if not crm_data.get("customer") and not crm_data.get("order"):
        if not state.get("order_id") and not state.get("customer_id"):
            return "I'd be happy to help with your refund! Could you provide your order number (like ORD-5005) or customer ID so I can look up your details?"
        elif not state.get("order_id"):
            return "I found your account, but I'll need your order number to process the refund. Could you share that?"
        elif not state.get("customer_id"):
            return "I found that order, but I'm having trouble linking it to your account. Could you provide your customer ID?"
    
    if crm_data.get("customer") and not crm_data.get("order"):
        return f"Hi {crm_data['customer'].get('name', 'there')}! I found your account. Which order would you like to return? Please share the order ID."
    
    if not crm_data.get("customer") and not crm_data.get("order"):
        return "I couldn't find your details with the information provided. Could you share your order number? It usually looks like ORD-5000."
    
    return None


# ─── Endpoints ─────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Handles the conversation loop:
    1. User sends message
    2. If we need more info, ask for it
    3. Otherwise, run the full workflow and return decision
    """
    
    session_id = get_or_create_session(request.session_id)
    session = sessions[session_id]
    
    session["messages"].append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    })
    
    if request.customer_id:
        session["customer_id"] = request.customer_id
    if request.order_id:
        session["order_id"] = request.order_id
    
    # ── Extract IDs from message using intake LLM ──
    try:
        from graph.nodes.intake import intake_node
        
        intake_state = {
            "user_input": request.message,
            "customer_id": session.get("customer_id"),
            "order_id": session.get("order_id"),
            "reasoning_log": [],
            "errors": [],
        }
        
        intake_result = intake_node(intake_state)
        
        if intake_result.get("customer_id"):
            session["customer_id"] = intake_result["customer_id"]
        if intake_result.get("order_id"):
            session["order_id"] = intake_result["order_id"]
        
        intent = intake_result.get("intent", "general")
        entities = intake_result.get("entities") or {}
        
    except Exception as e:
        logger.warning(f"Intake failed: {e}")
        intent = "general"
        entities = {}
    
    # ── If not a refund request, handle conversationally ──
    if intent not in ("refund_request", "general"):
        session["messages"].append({
            "role": "assistant",
            "content": "I'm here to help with refund requests. Would you like to start a return?",
            "timestamp": datetime.now().isoformat()
        })
        return ChatResponse(
            session_id=session_id,
            response="I'm here to help with refund requests. Would you like to start a return?",
            requires_action=False,
        )
    
    # ── Check if we have enough info ──
    if not session.get("order_id") and not session.get("customer_id"):
        if entities.get("order_id"):
            session["order_id"] = entities["order_id"]
        if entities.get("customer_id"):
            session["customer_id"] = entities["customer_id"]
    
    if not session.get("order_id") and not session.get("customer_id"):
        prompt = "I'd love to help process your refund! Could you share your order number? It usually starts with 'ORD-' (like ORD-5005)."
        session["awaiting"] = "order_id"
        session["messages"].append({
            "role": "assistant",
            "content": prompt,
            "timestamp": datetime.now().isoformat()
        })
        return ChatResponse(
            session_id=session_id,
            response=prompt,
            requires_action=True,
            action_type="ask_order_id",
        )
    
    # ═══════════════════════════════════════════════════════════
    # RUN THE FULL WORKFLOW
    # ═══════════════════════════════════════════════════════════
    start_time = time.time()
    
    try:
        result = process_refund_request_sync(
            user_input=request.message,
            customer_id=session.get("customer_id"),
            order_id=session.get("order_id"),
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        # ── Log to MLflow ──
        try:
            from observability.mlflow_tracker import log_workflow_run
            run_id = log_workflow_run(
                user_input=request.message,
                result=result,
                processing_time_ms=processing_time,
                session_id=session_id,
            )
            if run_id:
                session["last_mlflow_run_id"] = run_id
                logger.info(f"MLflow run logged: {run_id}")
        except Exception as e:
            logger.warning(f"MLflow logging failed (non-critical): {e}")
        
        # ── Check if we need more info after CRM lookup ──
        more_info = needs_more_info(result)
        if more_info:
            session["awaiting"] = "order_id"
            session["messages"].append({
                "role": "assistant",
                "content": more_info,
                "timestamp": datetime.now().isoformat()
            })
            return ChatResponse(
                session_id=session_id,
                response=more_info,
                requires_action=True,
                action_type="ask_order_id",
            )
        
        # ═══════════════════════════════════════════════════════════
        # SUCCESS PATH — Extract and store reasoning + customer ID
        # ═══════════════════════════════════════════════════════════
        
        # Extract reasoning from workflow result
        decision_reason = result.get("decision_reason", "")
        policy_cited = (result.get("policy_context") or "")[:1000]
        reasoning_log = result.get("reasoning_log", [])
        
        # Store in session for admin dashboard
        session["last_reasoning"] = reasoning_log
        session["last_decision_reason"] = decision_reason
        session["last_policy_cited"] = policy_cited
        
        # Extract customer_id from CRM data (if not already set)
        crm_data = result.get("crm_data") or {}
        customer = crm_data.get("customer") or {}
        if customer.get("customer_id"):
            session["customer_id"] = customer["customer_id"]
        
        # Also update order_id from result in case it was derived
        if result.get("order_id"):
            session["order_id"] = result["order_id"]
        
        # ── Build response ──
        decision = result.get("decision", "UNKNOWN")
        response_text = result.get("response", "")
        confidence = result.get("confidence")
        errors = result.get("errors", [])
        
        session["awaiting"] = None
        session["messages"].append({
            "role": "assistant",
            "content": response_text,
            "decision": decision,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
        
        return ChatResponse(
            session_id=session_id,
            response=response_text,
            decision=decision,
            confidence=confidence,
            reasoning_log=reasoning_log,
            errors=errors,
            requires_action=False,
            # NEW: Include reasoning details in response
            decision_reason=decision_reason,
            policy_cited=policy_cited,
            customer_id=session.get("customer_id"),
        )
        
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        session["messages"].append({
            "role": "assistant",
            "content": f"I encountered an error: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })
        return ChatResponse(
            session_id=session_id,
            response="I'm sorry, I ran into a technical issue. A specialist will review your case. Could you try again with your order number?",
            errors=[str(e)],
            requires_action=True,
            action_type="ask_order_id",
        )


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session history for debugging/admin panel."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (placeholder)."""
    return {"status": "ok", "message": "Metrics endpoint ready for Prometheus scraping"}


# ─── Run ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)