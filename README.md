```markdown
# 🤖 AI Customer Support Agent

An LLM-powered refund processing agent that uses **LangGraph**, **RAG (Pinecone)**, and **Groq LLM** to automatically approve, reject, or escalate e-commerce refund requests.

---

## 🎯 What It Does

- Customer describes their refund issue in natural language
- Agent fetches CRM data (customer, order, refund history)
- Agent retrieves relevant policy from Pinecone vector DB
- **LLM evaluates everything and decides:** APPROVE / REJECT / ESCALATE
- Admin dashboard shows full reasoning logs and escalation queue

---

## 🏗️ Architecture

```
Streamlit UI → FastAPI → LangGraph Workflow
                              ├── Intake (LLM analyzes input)
                              ├── CRM Lookup (SQLite)
                              ├── Policy Retrieval (Pinecone RAG)
                              ├── LLM Decision (Groq)
                              ├── Action (execute + update DB)
                              └── Logging
```

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/AI-CustomerCareAgent.git
cd AI-CustomerCareAgent
pip install -r requirements.txt
```

### 2. Set API Keys
Create `.env`:
```env
GROQ_API_KEY=your_groq_key
PINECONE_API_KEY=your_pinecone_key
```

### 3. Ingest Policy
```bash
python data/ingest_policy.py
```

### 4. Run
```bash
# Terminal 1
uvicorn api.main:app --reload

# Terminal 2
streamlit run frontend/app.py
```

Open `http://localhost:8501`

---

## 🎮 Demo Scenarios

| Scenario | Message | Expected |
|----------|---------|----------|
| ✅ Approval | *"I want to return order ORD-5003, size didn't fit"* | APPROVE |
| ❌ Rejection | *"I want another refund for order ORD-5010"* | REJECT |
| ⚠️ Escalation | *"Order ORD-5025 worth ₹72,000 is defective"* | ESCALATE |
| ⚠️ Escalation | *"Order ORD-5027 arrived damaged"* | ESCALATE |

---

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| LLM | Groq — Llama 3.3 70B |
| Agent | LangGraph |
| RAG | Pinecone + SentenceTransformers |
| Backend | FastAPI |
| Frontend | Streamlit |
| Database | SQLite |
| Observability | MLflow |

---

## 📁 Key Files

```
tools/          → CRM lookup, policy search, refund calculator, escalation
graph/nodes/    → LangGraph nodes (intake, CRM, policy, LLM decision, action)
api/main.py     → FastAPI server
frontend/app.py → Streamlit UI
data/crm.db     → Seeded database (15 customers, 50 orders)
data/policy.md  → Refund policy v2.0
```
