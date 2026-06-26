"""
Streamlit Frontend — AI Customer Support Agent

Two tabs:
  1. Customer Chat — Conversational refund processing
  2. Admin Dashboard — Reasoning logs, escalation queue, stats
"""

import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Config ────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Customer Support",
    page_icon="🤖",
    layout="wide"
)

API_URL = "http://localhost:8000"


# ─── Session State ─────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_decision" not in st.session_state:
    st.session_state.last_decision = None
# NEW: Store full reasoning from last response
if "last_reasoning" not in st.session_state:
    st.session_state.last_reasoning = []
if "last_decision_reason" not in st.session_state:
    st.session_state.last_decision_reason = ""
if "last_policy_cited" not in st.session_state:
    st.session_state.last_policy_cited = ""


# ─── Sidebar ───────────────────────────────────────────────

st.sidebar.title("🤖 AI Support Agent")
st.sidebar.markdown("---")

tab = st.sidebar.radio(
    "Navigation",
    ["💬 Customer Chat", "📊 Admin Dashboard"]
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Session: {st.session_state.session_id or 'New'}")

if st.sidebar.button("🔄 New Session"):
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.last_decision = None
    st.session_state.last_reasoning = []
    st.session_state.last_decision_reason = ""
    st.session_state.last_policy_cited = ""
    st.rerun()


# ═══════════════════════════════════════════════════════════
# TAB 1: CUSTOMER CHAT
# ═══════════════════════════════════════════════════════════

if tab == "💬 Customer Chat":
    
    st.title("💬 Refund Support Chat")
    st.caption("Describe your refund issue — the AI agent will help you.")
    
    # Quick demo buttons
    with st.expander("⚡ Quick Demo Scenarios", expanded=False):
        cols = st.columns(4)
        demos = [
            ("✅ Standard Approval", "I want to return order ORD-5005, I found a better alternative"),
            ("❌ Fraud Rejection", "I want another refund for order ORD-5000"),
            ("⚠️ High Value Escalate", "My electronics order ORD-5025 worth 72000 is defective"),
            ("⚠️ Damaged Product", "Order ORD-5027 arrived damaged, I need a refund"),
        ]
        for i, (label, msg) in enumerate(demos):
            with cols[i]:
                if st.button(label, key=f"demo_{i}"):
                    st.session_state.messages.append({"role": "user", "content": msg})
                    # Send to API
                    with st.spinner("Processing..."):
                        resp = requests.post(f"{API_URL}/chat", json={
                            "message": msg,
                            "session_id": st.session_state.session_id,
                        })
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.session_id = data["session_id"]
                            st.session_state.last_decision = data.get("decision")
                            # NEW: Store reasoning from response
                            st.session_state.last_reasoning = data.get("reasoning_log", [])
                            st.session_state.last_decision_reason = data.get("decision_reason", "")
                            st.session_state.last_policy_cited = data.get("policy_cited", "")
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": data["response"],
                                "decision": data.get("decision"),
                                "confidence": data.get("confidence"),
                            })
                    st.rerun()
    
    # Chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["content"])
        else:
            with st.chat_message("assistant"):
                decision = msg.get("decision")
                if decision == "APPROVE":
                    st.success(msg["content"])
                elif decision == "REJECT":
                    st.error(msg["content"])
                elif decision == "ESCALATE":
                    st.warning(msg["content"])
                else:
                    st.info(msg["content"])
                
                if msg.get("confidence"):
                    st.caption(f"Confidence: {msg['confidence']:.0%}")
    
    # Chat input
    if prompt := st.chat_input("Describe your refund issue..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.spinner("Agent is thinking..."):
            resp = requests.post(f"{API_URL}/chat", json={
                "message": prompt,
                "session_id": st.session_state.session_id,
            })
            
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.session_id = data["session_id"]
                st.session_state.last_decision = data.get("decision")
                # NEW: Store reasoning from response
                st.session_state.last_reasoning = data.get("reasoning_log", [])
                st.session_state.last_decision_reason = data.get("decision_reason", "")
                st.session_state.last_policy_cited = data.get("policy_cited", "")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data["response"],
                    "decision": data.get("decision"),
                    "confidence": data.get("confidence"),
                })
            else:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Sorry, I'm having trouble connecting. Please try again.",
                })
        
        st.rerun()


# ═══════════════════════════════════════════════════════════
# TAB 2: ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════

elif tab == "📊 Admin Dashboard":
    
    st.title("📊 Admin Dashboard")
    st.caption("Real-time agent reasoning logs and escalation queue.")
    
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    
    total_msgs = len(st.session_state.messages)
    user_msgs = sum(1 for m in st.session_state.messages if m["role"] == "user")
    agent_msgs = sum(1 for m in st.session_state.messages if m["role"] == "assistant")
    last_decision = st.session_state.last_decision or "N/A"
    
    col1.metric("Total Messages", total_msgs)
    col2.metric("User Messages", user_msgs)
    col3.metric("Agent Responses", agent_msgs)
    col4.metric("Last Decision", last_decision)
    
    st.markdown("---")
    
    # Escalation Queue
    st.subheader("🚨 Escalation Queue")
    
    try:
        from tools.escalation import get_open_escalations
        
        escalations = get_open_escalations()
        if escalations:
            df = pd.DataFrame(escalations)
            st.dataframe(
                df[["escalation_id", "request_id", "customer_id", "escalation_reason", "priority", "created_at"]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No open escalations.")
    except Exception as e:
        st.warning(f"Could not load escalation queue: {e}")
    
    st.markdown("---")
    
    # Reasoning Logs
    st.subheader("🧠 Reasoning Logs")
    
    has_reasoning = bool(st.session_state.last_reasoning) or bool(st.session_state.last_decision_reason)
    
    if has_reasoning:
        if st.session_state.last_decision_reason:
            st.markdown("### 📝 Decision Reason")
            st.info(st.session_state.last_decision_reason)
        
        if st.session_state.last_reasoning:
            st.markdown("### 🔍 Step-by-Step Trace")
            for i, step in enumerate(st.session_state.last_reasoning, 1):
                node_name = step.get("node", "unknown")
                output_summary = step.get("output_summary", "")
                thinking = step.get("thinking", "")
                timestamp = step.get("timestamp", "")
                
                with st.expander(f"Step {i}: [{node_name}] {output_summary[:60]}...", expanded=(i <= 2)):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown("**Action:**")
                        st.write(output_summary)
                    with col2:
                        st.markdown("**Timestamp:**")
                        st.caption(timestamp)
                    
                    if thinking:
                        st.markdown("**Thinking:**")
                        st.text(thinking)
        
        if st.session_state.last_policy_cited:
            st.markdown("### 📋 Policy Referenced")
            with st.expander("Click to view policy text", expanded=False):
                st.text(st.session_state.last_policy_cited)
        
        with st.expander("📄 Raw JSON", expanded=False):
            st.json({
                "decision": st.session_state.last_decision,
                "decision_reason": st.session_state.last_decision_reason,
                "reasoning_steps": len(st.session_state.last_reasoning),
                "policy_cited_length": len(st.session_state.last_policy_cited),
            })
    
    else:
        st.info("📝 No reasoning data yet. Run a refund request from the Chat tab first, then check here.")
    
    st.markdown("---")
    
    # Agent Stats from MLflow
    st.subheader("📈 Agent Statistics (MLflow)")
    
    try:
        import importlib
        mlflow_tracker = importlib.import_module("observability.mlflow_tracker")
        get_run_stats = mlflow_tracker.get_run_stats
        get_recent_runs = mlflow_tracker.get_recent_runs
        
        stats = get_run_stats()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Runs", stats.get("total_runs", 0))
        col2.metric("Approvals", stats.get("approvals", 0))
        col3.metric("Rejections", stats.get("rejections", 0))
        col4.metric("Escalations", stats.get("escalations", 0))
        col5.metric("Avg Confidence", f"{stats.get('avg_confidence', 0):.0%}")
        
        if stats.get("total_runs", 0) > 0:
            st.markdown("#### Recent Workflow Runs")
            recent = get_recent_runs(5)
            if recent:
                df_runs = pd.DataFrame(recent)
                display_cols = {
                    "start_time": "Time",
                    "params.decision": "Decision",
                    "metrics.confidence": "Confidence",
                    "metrics.processing_time_ms": "Time (ms)",
                    "params.session_id": "Session",
                }
                available_cols = {k: v for k, v in display_cols.items() if k in df_runs.columns}
                if available_cols:
                    df_display = df_runs[list(available_cols.keys())].rename(columns=available_cols)
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df_runs.head(), use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.info(f"📊 MLflow stats will appear after processing requests. ({e})")
    
    st.markdown("---")
    
    # Session Details
    st.subheader("🔗 Session Details")
    
    if st.session_state.session_id:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Session ID:**")
            st.code(st.session_state.session_id)
            
            st.markdown("**Customer ID:**")
            customer_id = None
            try:
                resp = requests.get(f"{API_URL}/sessions/{st.session_state.session_id}")
                if resp.status_code == 200:
                    session_data = resp.json()
                    customer_id = session_data.get("customer_id")
            except:
                pass
            
            if customer_id:
                st.code(customer_id)
            else:
                st.caption("Not available yet")
        
        with col2:
            st.markdown("**Message Count:**")
            st.code(len(st.session_state.messages))
            
            st.markdown("**Last Activity:**")
            if st.session_state.messages:
                last_ts = st.session_state.messages[-1].get("timestamp", "Unknown")
                st.code(last_ts)
            else:
                st.caption("No messages yet")
    else:
        st.info("No active session. Start a chat first.")
    
    st.markdown("---")
    
    # API Health
    st.subheader("🔧 System Status")
    
    col1, col2 = st.columns(2)
    
    with col1:
        try:
            resp = requests.get(f"{API_URL}/health", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"✅ API Online\n\nTimestamp: {data.get('timestamp', 'N/A')}")
            else:
                st.error("❌ API returned error")
        except requests.exceptions.ConnectionError:
            st.error("❌ API Offline — Cannot connect\n\nStart with:\n```bash\nuvicorn api.main:app --reload\n```")
        except Exception as e:
            st.error(f"❌ API Error: {e}")
    
    with col2:
        try:
            import importlib
            mlflow_check = importlib.import_module("observability.mlflow_tracker")
            if mlflow_check._ensure_mlflow():
                st.success("✅ MLflow Connected")
            else:
                st.warning("⚠️ MLflow not configured")
        except:
            st.warning("⚠️ MLflow not available")