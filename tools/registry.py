

from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, asdict
import traceback


# ─── Import all tools ───────────────────────────────────────

from policy_search import policy_search          # ← Instance, not function
from crm_lookup import (
    get_customer,
    get_order,
    get_refund_request,
    get_refund_history,
    get_complete_case
)
from eligibility_checker import check_eligibility
from refund_calculator import calculate_refund
from crm_update import process_decision, auto_flag_fraud_if_exceeded
from escalation import (
    create_escalation,
    build_escalation_context,
    get_open_escalations,
    get_escalation_stats
)


# ─── Tool Definition ────────────────────────────────────────

@dataclass
class ToolDef:
    """Definition of a callable tool."""
    name: str
    description: str
    func: Callable
    parameters: Dict[str, str]  # param_name -> type
    returns: str
    category: str  # 'retrieval', 'lookup', 'logic', 'action'


# ─── Tool Registry ──────────────────────────────────────────

class ToolRegistry:
    """
    Central registry for all agent tools.
    
    Usage:
        registry = ToolRegistry()
        result = registry.call("get_complete_case", request_id="REF-7000")
        schemas = registry.get_llm_schemas()  # For OpenAI/Groq function calling
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDef] = {}
        self._register_all()
    
    def _register(self, tool: ToolDef):
        """Register a single tool."""
        self._tools[tool.name] = tool
    
    def _register_all(self):
        """Register all available tools."""
        
        # ── Policy Retrieval ────────────────────────────────
                
        self._register(ToolDef(
            name="search_policy",
            description="Search the refund policy document using RAG. Returns relevant policy sections.",
            func=policy_search.search,              # ← Use instance method
            parameters={"question": "str"},         # ← Param is 'question' not 'query'
            returns="List of policy chunks with relevance scores",
            category="retrieval"
        ))
        
        # ── CRM Lookups ─────────────────────────────────────
        self._register(ToolDef(
            name="get_customer",
            description="Retrieve customer details by ID (e.g., 'CUST-1000')",
            func=get_customer,
            parameters={"customer_id": "str"},
            returns="Customer dict or None",
            category="lookup"
        ))
        
        self._register(ToolDef(
            name="get_order",
            description="Retrieve order details by ID (e.g., 'ORD-5000')",
            func=get_order,
            parameters={"order_id": "str"},
            returns="Order dict or None",
            category="lookup"
        ))
        
        self._register(ToolDef(
            name="get_refund_request",
            description="Retrieve refund request details by ID (e.g., 'REF-7000')",
            func=get_refund_request,
            parameters={"request_id": "str"},
            returns="RefundRequest dict or None",
            category="lookup"
        ))
        
        self._register(ToolDef(
            name="get_refund_history",
            description="Retrieve refund history for a customer",
            func=get_refund_history,
            parameters={"customer_id": "str"},
            returns="RefundHistory dict or None",
            category="lookup"
        ))
        
        self._register(ToolDef(
            name="get_complete_case",
            description="Build complete case with all CRM data for a refund request. Use this as the primary lookup.",
            func=get_complete_case,
            parameters={"request_id": "str"},
            returns="CompleteCase dict with customer, order, refund_request, refund_history",
            category="lookup"
        ))
        
        # ── Business Logic ──────────────────────────────────
        self._register(ToolDef(
            name="check_eligibility",
            description="Determine if a refund is eligible based on policy rules. Returns approve/reject/escalate with reasoning.",
            func=check_eligibility,
            parameters={
                "customer": "dict",
                "order": "dict",
                "refund_request": "dict",
                "refund_history": "dict"
            },
            returns="EligibilityResult dict with decision, reason, confidence, step-by-step details",
            category="logic"
        ))
        
        self._register(ToolDef(
            name="calculate_refund",
            description="Calculate refund amount, restocking fees, and refund type",
            func=calculate_refund,
            parameters={
                "order": "dict",
                "refund_request": "dict"
            },
            returns="RefundCalculation dict with amount, fees, type",
            category="logic"
        ))
        
        # ── CRM Updates ─────────────────────────────────────
        self._register(ToolDef(
            name="process_decision",
            description="Write the final decision to the database. Updates refund_requests and refund_history tables.",
            func=process_decision,
            parameters={
                "request_id": "str",
                "customer_id": "str",
                "decision": "str"
            },
            returns="Dict with update results",
            category="action"
        ))
        
        self._register(ToolDef(
            name="auto_flag_fraud_if_exceeded",
            description="Automatically flag a customer for fraud if they exceed refund limits",
            func=auto_flag_fraud_if_exceeded,
            parameters={
                "customer_id": "str",
                "max_refunds": "int"
            },
            returns="bool",
            category="action"
        ))
        
        # ── Escalation ──────────────────────────────────────
        self._register(ToolDef(
            name="create_escalation",
            description="Create an escalation record for human review when agent cannot decide",
            func=create_escalation,
            parameters={
                "request_id": "str",
                "customer_id": "str",
                "order_id": "str",
                "escalation_reason": "str",
                "agent_notes": "str",
                "context": "dict"
            },
            returns="Dict with escalation details",
            category="action"
        ))
        
        self._register(ToolDef(
            name="build_escalation_context",
            description="Build comprehensive context package for human agent review",
            func=build_escalation_context,
            parameters={
                "customer": "dict",
                "order": "dict",
                "refund_request": "dict",
                "refund_history": "dict",
                "eligibility_result": "dict",
                "policy_chunks": "list"
            },
            returns="Dict with full escalation context",
            category="action"
        ))
        
        self._register(ToolDef(
            name="get_open_escalations",
            description="Get all open escalations in the queue",
            func=get_open_escalations,
            parameters={"priority": "str (optional)"},
            returns="List of escalation records",
            category="lookup"
        ))
        
        self._register(ToolDef(
            name="get_escalation_stats",
            description="Get escalation queue statistics",
            func=get_escalation_stats,
            parameters={},
            returns="Dict with counts by priority and status",
            category="lookup"
        ))
    
    # ── Public API ──────────────────────────────────────────
    
    def call(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call a tool by name with keyword arguments.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool
        
        Returns:
            Dict with 'success', 'result' or 'error', 'tool_name'
        """
        if tool_name not in self._tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found. Available: {list(self._tools.keys())}",
                "tool_name": tool_name
            }
        
        tool = self._tools[tool_name]
        
        try:
            result = tool.func(**kwargs)
            return {
                "success": True,
                "result": result,
                "tool_name": tool_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tool_name": tool_name
            }
    
    def get_tool(self, tool_name: str) -> Optional[ToolDef]:
        """Get a tool definition by name."""
        return self._tools.get(tool_name)
    
    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """List all tool names, optionally filtered by category."""
        if category:
            return [name for name, t in self._tools.items() if t.category == category]
        return list(self._tools.keys())
    
    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get full metadata for a tool."""
        tool = self._tools.get(tool_name)
        if not tool:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "returns": tool.returns,
            "category": tool.category
        }
    
    def get_all_tool_info(self) -> List[Dict[str, Any]]:
        """Get metadata for all registered tools."""
        return [self.get_tool_info(name) for name in self._tools]
    
    def get_llm_schemas(self) -> List[Dict[str, Any]]:
        """
        Generate OpenAI/Groq-compatible function calling schemas.
        
        Returns:
            List of function definitions for LLM tool calling.
        """
        schemas = []
        
        for name, tool in self._tools.items():
            properties = {}
            required = []
            
            for param, ptype in tool.parameters.items():
                # Map Python types to JSON Schema types
                type_map = {
                    "str": "string",
                    "int": "integer",
                    "float": "number",
                    "bool": "boolean",
                    "dict": "object",
                    "list": "array"
                }
                
                # Handle optional params (those with descriptions in parens)
                clean_type = ptype.split(" ")[0] if " " in ptype else ptype
                json_type = type_map.get(clean_type, "string")
                
                properties[param] = {
                    "type": json_type,
                    "description": tool.parameters.get(param, "")
                }
                
                # Assume all params are required unless noted optional
                if "optional" not in ptype.lower():
                    required.append(param)
            
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        
        return schemas
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get tools grouped by category."""
        categories = {}
        for name, tool in self._tools.items():
            if tool.category not in categories:
                categories[tool.category] = []
            categories[tool.category].append(name)
        return categories


# ─── Singleton Instance ─────────────────────────────────────

# Create a singleton registry for the entire application
registry = ToolRegistry()


# ─── Tool Metadata ──────────────────────────────────────────

TOOL_METADATA = {
    "ToolRegistry": {
        "description": "Central tool registry for the AI Customer Support Agent",
        "usage": "registry.call('tool_name', **kwargs)",
        "total_tools": len(registry._tools),
        "categories": registry.get_categories()
    }
}


# ─── Self-Test ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Tool Registry - Self Test")
    print("=" * 60)
    
    # List all tools
    print(f"\n📦 Registered Tools: {len(registry._tools)}")
    print(f"\nBy Category:")
    for category, tools in registry.get_categories().items():
        print(f"  {category}: {', '.join(tools)}")
    
    # Test individual tool call
    print(f"\n{'─' * 60}")
    print("Test: get_complete_case('REF-7000')")
    print(f"{'─' * 60}")
    result = registry.call("get_complete_case", request_id="REF-7000")
    if result["success"]:
        case = result["result"]
        print(f"  ✅ Customer: {case['customer']['name']} ({case['customer']['tier']})")
        print(f"  ✅ Order: {case['order']['order_id']} | {case['order']['product_category']}")
        print(f"  ✅ Request: {case['refund_request']['refund_reason']}")
    else:
        print(f"  ❌ Error: {result['error']}")
    
    # Test LLM schemas
    print(f"\n{'─' * 60}")
    print("Test: LLM Function Schemas")
    print(f"{'─' * 60}")
    schemas = registry.get_llm_schemas()
    print(f"  Generated {len(schemas)} function schemas")
    print(f"  Sample: {schemas[0]['function']['name']}")
    
    # Test tool info
    print(f"\n{'─' * 60}")
    print("Test: Tool Info")
    print(f"{'─' * 60}")
    info = registry.get_tool_info("check_eligibility")
    print(f"  Name: {info['name']}")
    print(f"  Description: {info['description'][:80]}...")
    print(f"  Parameters: {list(info['parameters'].keys())}")
    
    # Test error handling
    print(f"\n{'─' * 60}")
    print("Test: Invalid Tool")
    print(f"{'─' * 60}")
    result = registry.call("nonexistent_tool")
    print(f"  Success: {result['success']}")
    print(f"  Error: {result['error'][:60]}...")
    
    print(f"\n{'=' * 60}")
    print("Self-test complete")