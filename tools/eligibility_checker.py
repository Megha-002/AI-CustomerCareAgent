# tools/eligibility_checker.py
"""
Eligibility Checker - Determines refund eligibility based on CRM data + policy rules.

Implements the Decision Priority order from policy.md v2.0:
  1. Verify Customer
  2. Verify Order
  3. Verify Refund Request
  4. Check Product Category
  5. Apply Gold Tier Benefits
  6. Check Refund Window
  7. Check Shipping Status
  8. Evaluate Product Condition
  9. Perform Fraud Checks
  10. Check Manual Review Flag
  11. Make Final Decision
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, asdict


# ─── Constants from Policy ──────────────────────────────────

# Standard refund windows (days after delivery)
REFUND_WINDOWS = {
    "physical": 30,
    "digital": 14,
    "perishable": 7
}

# Gold tier gets +15 days
GOLD_EXTENSION = 15

# Non-refundable categories (refunds NEVER allowed)
NON_REFUNDABLE_CATEGORIES = [
    "gift_cards",
    "gift cards",
    "final_sale",
    "final sale",
    "personalized",
    "personalized_products",
    "intimate_apparel",
    "intimate apparel"
]

# High value threshold in ₹
HIGH_VALUE_THRESHOLD = 50000.0

# Boundary time window (minutes before/after deadline)
BOUNDARY_MINUTES = 5

# Max refunds before fraud suspicion
MAX_REFUND_COUNT = 3

# Required shipping status for eligibility
ELIGIBLE_SHIPPING_STATUS = "delivered"


# ─── Data Classes ───────────────────────────────────────────

@dataclass
class EligibilityResult:
    """Structured result from eligibility check."""
    eligible: bool
    decision: str                    # "approve", "reject", "escalate"
    reason: str                      # Human-readable explanation
    confidence: float                # 0.0 to 1.0
    escalation_reason: Optional[str] = None  # Set if decision is escalate
    details: Optional[Dict[str, Any]] = None  # Supporting details


# ─── Helper Functions ───────────────────────────────────────

def _parse_datetime(date_str: str) -> datetime:
    """Parse datetime string from SQLite format."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.strptime(date_str, "%Y-%m-%d")


def _is_non_refundable(category: str) -> bool:
    """Check if product category is non-refundable."""
    normalized = category.lower().replace(" ", "_")
    return normalized in NON_REFUNDABLE_CATEGORIES


def _calculate_refund_window(product_category: str, customer_tier: str) -> int:
    """
    Calculate the effective refund window in days.
    Applies Gold tier extension if applicable.
    """
    base_window = REFUND_WINDOWS.get(product_category.lower(), 30)
    
    if customer_tier.lower() == "gold":
        return base_window + GOLD_EXTENSION
    
    return base_window


def _calculate_deadline(order_date_str: str, window_days: int) -> datetime:
    """Calculate the refund deadline from order date + window."""
    order_date = _parse_datetime(order_date_str)
    if not order_date:
        return None
    return order_date + timedelta(days=window_days)


def _is_boundary_case(request_date_str: str, deadline: datetime) -> bool:
    """
    Check if request falls within boundary window (±5 minutes of deadline).
    """
    if not deadline:
        return False
    
    request_date = _parse_datetime(request_date_str)
    if not request_date:
        return False
    
    diff = abs((request_date - deadline).total_seconds() / 60)
    return diff <= BOUNDARY_MINUTES


# ─── Step-by-Step Checks (following Decision Priority) ──────

def _check_1_verify_customer(customer: Dict[str, Any]) -> Tuple[bool, str]:
    """Step 1: Verify customer exists."""
    if not customer:
        return False, "Customer record not found"
    if not customer.get("customer_id"):
        return False, "Customer ID is missing"
    return True, "Customer verified"


def _check_2_verify_order(order: Dict[str, Any]) -> Tuple[bool, str]:
    """Step 2: Verify order exists."""
    if not order:
        return False, "Order record not found"
    if not order.get("order_id"):
        return False, "Order ID is missing"
    return True, "Order verified"


def _check_3_verify_request(refund_request: Dict[str, Any]) -> Tuple[bool, str]:
    """Step 3: Verify refund request exists."""
    if not refund_request:
        return False, "Refund request not found"
    if not refund_request.get("request_id"):
        return False, "Request ID is missing"
    return True, "Refund request verified"


def _check_4_product_category(category: str) -> Tuple[bool, str, Optional[str]]:
    """
    Step 4: Check if product category is refundable.
    Returns: (passed, reason, escalation_reason)
    """
    if not category:
        return False, "Product category is missing", None
    
    if _is_non_refundable(category):
        return False, f"Category '{category}' is non-refundable", None
    
    if category.lower() not in REFUND_WINDOWS:
        # Unknown category - escalate for human review
        return False, f"Unknown product category: {category}", "unknown_category"
    
    return True, f"Category '{category}' is refundable", None


def _check_5_gold_benefits(tier: str, base_window: int, effective_window: int) -> str:
    """Step 5: Document Gold tier benefits if applicable."""
    if tier.lower() == "gold":
        return f"Gold tier: {base_window} → {effective_window} days (+{GOLD_EXTENSION})"
    return f"Standard tier ({tier}): {effective_window} days"


def _check_6_refund_window(
    order_date: str,
    request_date: str,
    effective_window: int
) -> Tuple[bool, str, Optional[str]]:
    """
    Step 6: Check if request is within refund window.
    Returns: (passed, reason, escalation_reason)
    """
    order_dt = _parse_datetime(order_date)
    request_dt = _parse_datetime(request_date)
    
    if not order_dt or not request_dt:
        return False, "Could not parse dates for window calculation", "date_parse_error"
    
    deadline = order_dt + timedelta(days=effective_window)
    days_since_order = (request_dt - order_dt).days
    
    # Check boundary case
    if _is_boundary_case(request_date, deadline):
        return False, (
            f"Request within {BOUNDARY_MINUTES} minutes of deadline "
            f"(deadline: {deadline.strftime('%Y-%m-%d %H:%M')})"
        ), "boundary_time"
    
    if request_dt <= deadline:
        return True, (
            f"Within refund window: {days_since_order} days used "
            f"of {effective_window} allowed"
        ), None
    else:
        days_over = (request_dt - deadline).days
        return False, (
            f"Refund window expired: {days_since_order} days since order, "
            f"window is {effective_window} days ({days_over} days over)"
        ), None


def _check_7_shipping(shipping_status: str, delivery_issue: str) -> Tuple[bool, str, Optional[str]]:
    """
    Step 7: Check shipping status.
    Returns: (passed, reason, escalation_reason)
    """
    if shipping_status == ELIGIBLE_SHIPPING_STATUS:
        # Delivered - but check for lost shipment
        if delivery_issue and delivery_issue.lower() in ("lost", "not_received"):
            return False, "Shipment marked as lost by customer", "lost_shipment"
        return True, "Order has been delivered", None
    
    elif shipping_status in ("pending", "shipped"):
        return False, f"Order not yet delivered (status: {shipping_status})", None
    
    else:
        return False, f"Unknown shipping status: {shipping_status}", "unknown_shipping_status"


def _check_8_product_condition(
    product_condition: str,
    package_opened: bool,
    receipt_available: bool,
    damage_reported: bool,
    wrong_item_received: bool
) -> Tuple[bool, str, Optional[str]]:
    """
    Step 8: Evaluate product condition.
    Returns: (passed, reason, escalation_reason)
    """
    issues = []
    escalation = None
    
    # Damage reported → escalate
    if damage_reported:
        issues.append("damage reported")
        escalation = "damage_reported"
    
    # Wrong item → escalate
    if wrong_item_received:
        issues.append("wrong item received")
        escalation = "wrong_item_received"
    
    # Missing receipt → escalate (don't reject)
    if not receipt_available:
        issues.append("receipt not available")
        escalation = "missing_receipt"
    
    # Package opened is a warning but not a blocker
    if package_opened:
        issues.append("package opened")
    
    if escalation:
        return False, f"Product condition issues: {', '.join(issues)}", escalation
    
    if issues:
        return True, f"Condition acceptable (minor: {', '.join(issues)})", None
    
    return True, f"Product condition: {product_condition}, acceptable", None


def _check_9_fraud(
    fraud_flag: bool,
    refund_count: int,
    refund_reason: str,
    customer_comments: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Step 9: Fraud checks.
    Returns: (passed, reason, escalation_reason)
    """
    # Active fraud flag → hard reject
    if fraud_flag:
        return False, "Fraud flag is active on customer account", None
    
    # Exceeded refund limit
    if refund_count > MAX_REFUND_COUNT:
        return False, (
            f"Customer has {refund_count} refunds (max {MAX_REFUND_COUNT} allowed)"
        ), None
    
    # Check for suspicious patterns in comments
    suspicious_keywords = ["legal", "lawsuit", "sue", "attorney", "chargeback", "fraud"]
    if customer_comments:
        lower_comments = customer_comments.lower()
        for keyword in suspicious_keywords:
            if keyword in lower_comments:
                return False, (
                    f"Suspicious language detected in customer comments"
                ), "legal_threat"
    
    return True, f"Fraud checks passed ({refund_count} prior refunds)", None


def _check_10_manual_review(manual_review_required: bool) -> Tuple[bool, str, Optional[str]]:
    """
    Step 10: Check manual review flag.
    This ALWAYS overrides automatic decisions.
    """
    if manual_review_required:
        return False, "Manual review flag is set", "manual_review_required"
    return True, "No manual review required", None


def _check_11_high_value(purchase_amount: float) -> Tuple[bool, str, Optional[str]]:
    """
    Additional check: High value orders require escalation.
    """
    if purchase_amount > HIGH_VALUE_THRESHOLD:
        return False, (
            f"Order value ₹{purchase_amount:,.2f} exceeds threshold of "
            f"₹{HIGH_VALUE_THRESHOLD:,.2f}"
        ), "high_value_order"
    return True, f"Order value ₹{purchase_amount:,.2f} within limits", None


def _check_goodwill_signals(customer_comments: str, tier: str, refund_count: int) -> Optional[str]:
    """
    Detect goodwill/loyalty signals that warrant escalation.
    """
    if not customer_comments:
        return None
    
    lower = customer_comments.lower()
    
    goodwill_phrases = [
        "loyal customer",
        "first refund",
        "first time",
        "long time customer",
        "been a customer",
        "missed the deadline",
        "just missed",
        "few minutes",
        "one time exception",
        "make an exception"
    ]
    
    for phrase in goodwill_phrases:
        if phrase in lower:
            return "goodwill_request"
    
    return None


# ─── Main Eligibility Function ───────────────────────────────

def check_eligibility(
    customer: Dict[str, Any],
    order: Dict[str, Any],
    refund_request: Dict[str, Any],
    refund_history: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Determine refund eligibility based on CRM data and policy rules.
    
    Args:
        customer: Customer dict from crm_lookup.get_customer()
        order: Order dict from crm_lookup.get_order()
        refund_request: RefundRequest dict from crm_lookup.get_refund_request()
        refund_history: RefundHistory dict from crm_lookup.get_refund_history()
    
    Returns:
        EligibilityResult as dictionary with:
            eligible: bool
            decision: "approve" | "reject" | "escalate"
            reason: str
            confidence: float
            escalation_reason: str or None
            details: dict with step-by-step results
    """
    
    steps = {}
    rejection_reasons = []
    escalation_reason = None
    
    # ── Step 1: Verify Customer ─────────────────────────────
    passed, msg = _check_1_verify_customer(customer)
    steps["1_verify_customer"] = {"passed": passed, "message": msg}
    if not passed:
        rejection_reasons.append(msg)
    
    # ── Step 2: Verify Order ────────────────────────────────
    passed, msg = _check_2_verify_order(order)
    steps["2_verify_order"] = {"passed": passed, "message": msg}
    if not passed:
        rejection_reasons.append(msg)
    
    # ── Step 3: Verify Refund Request ───────────────────────
    passed, msg = _check_3_verify_request(refund_request)
    steps["3_verify_request"] = {"passed": passed, "message": msg}
    if not passed:
        rejection_reasons.append(msg)
    
    # If any of the first 3 fail, hard stop
    if rejection_reasons:
        return asdict(EligibilityResult(
            eligible=False,
            decision="reject",
            reason=f"Verification failed: {'; '.join(rejection_reasons)}",
            confidence=1.0,
            escalation_reason=None,
            details=steps
        ))
    
    # ── Extract key fields ──────────────────────────────────
    tier = customer.get("tier", "Bronze")
    category = order.get("product_category", "")
    order_date = order.get("order_date", "")
    request_date = refund_request.get("request_date", "")
    shipping_status = order.get("shipping_status", "")
    purchase_amount = order.get("purchase_amount", 0)
    product_condition = refund_request.get("product_condition", "")
    package_opened = refund_request.get("package_opened", False)
    receipt_available = refund_request.get("receipt_available", False)
    damage_reported = refund_request.get("damage_reported", False)
    wrong_item_received = refund_request.get("wrong_item_received", False)
    delivery_issue = refund_request.get("delivery_issue", "")
    customer_comments = refund_request.get("customer_comments", "")
    manual_review_required = refund_request.get("manual_review_required", False)
    fraud_flag = refund_history.get("fraud_flag", False)
    refund_count = refund_history.get("refund_count", 0)
    
    # ── Step 4: Check Product Category ──────────────────────
    passed, msg, esc = _check_4_product_category(category)
    steps["4_product_category"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    if not passed and not esc:
        rejection_reasons.append(msg)
    
    # ── Step 5: Apply Gold Tier Benefits ────────────────────
    base_window = REFUND_WINDOWS.get(category.lower(), 30)
    effective_window = _calculate_refund_window(category, tier)
    msg = _check_5_gold_benefits(tier, base_window, effective_window)
    steps["5_gold_benefits"] = {"passed": True, "message": msg}
    
    # ── Step 6: Check Refund Window ─────────────────────────
    passed, msg, esc = _check_6_refund_window(order_date, request_date, effective_window)
    steps["6_refund_window"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    if not passed and not esc:
        rejection_reasons.append(msg)
    
    # ── Step 7: Check Shipping Status ───────────────────────
    passed, msg, esc = _check_7_shipping(shipping_status, delivery_issue)
    steps["7_shipping_status"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    if not passed and not esc:
        rejection_reasons.append(msg)
    
    # ── Step 8: Evaluate Product Condition ──────────────────
    passed, msg, esc = _check_8_product_condition(
        product_condition, package_opened, receipt_available,
        damage_reported, wrong_item_received
    )
    steps["8_product_condition"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    
    # ── Step 9: Fraud Checks ────────────────────────────────
    passed, msg, esc = _check_9_fraud(fraud_flag, refund_count, 
                                       refund_request.get("refund_reason", ""),
                                       customer_comments)
    steps["9_fraud_checks"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    if not passed and not esc:
        rejection_reasons.append(msg)
    
    # ── Step 10: Manual Review Flag ─────────────────────────
    passed, msg, esc = _check_10_manual_review(manual_review_required)
    steps["10_manual_review"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    
    # ── Step 11: High Value Check ───────────────────────────
    passed, msg, esc = _check_11_high_value(purchase_amount)
    steps["11_high_value"] = {"passed": passed, "message": msg}
    if esc:
        escalation_reason = esc
    
    # ── Additional: Goodwill Signals ────────────────────────
    goodwill = _check_goodwill_signals(customer_comments, tier, refund_count)
    if goodwill:
        steps["goodwill_check"] = {"passed": False, "message": f"Goodwill signal: {goodwill}"}
        if not escalation_reason:
            escalation_reason = goodwill
    
    # ── Final Decision ──────────────────────────────────────
    
    # ESCALATE takes priority if any escalation trigger was found
    if escalation_reason:
        return asdict(EligibilityResult(
            eligible=False,
            decision="escalate",
            reason=f"Escalation required: {escalation_reason}",
            confidence=0.7,
            escalation_reason=escalation_reason,
            details=steps
        ))
    
    # REJECT if any rejection reasons
    if rejection_reasons:
        return asdict(EligibilityResult(
            eligible=False,
            decision="reject",
            reason=f"Rejected: {'; '.join(rejection_reasons)}",
            confidence=1.0,
            escalation_reason=None,
            details=steps
        ))
    
    # APPROVE if all checks passed
    return asdict(EligibilityResult(
        eligible=True,
        decision="approve",
        reason="All eligibility checks passed. Refund can be processed automatically.",
        confidence=0.95,
        escalation_reason=None,
        details=steps
    ))


# ─── Tool Metadata ──────────────────────────────────────────

TOOL_METADATA = {
    "check_eligibility": {
        "description": "Determine refund eligibility using CRM data and policy rules",
        "parameters": {
            "customer": "Customer dict",
            "order": "Order dict",
            "refund_request": "RefundRequest dict",
            "refund_history": "RefundHistory dict"
        },
        "returns": "EligibilityResult dict with decision, reason, confidence, details"
    }
}


# ─── Self-Test ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from crm_lookup import get_complete_case
    
    print("=" * 60)
    print("Eligibility Checker - Self Test")
    print("=" * 60)
    
    test_cases = ["REF-7000", "REF-7001", "REF-7002"]
    
    for request_id in test_cases:
        print(f"\n{'─' * 60}")
        print(f"Testing: {request_id}")
        print(f"{'─' * 60}")
        
        case = get_complete_case(request_id)
        if not case:
            print(f"  ❌ Could not retrieve case for {request_id}")
            continue
        
        result = check_eligibility(
            customer=case["customer"],
            order=case["order"],
            refund_request=case["refund_request"],
            refund_history=case["refund_history"]
        )
        
        decision_emoji = {"approve": "✅", "reject": "❌", "escalate": "⚠️"}
        emoji = decision_emoji.get(result["decision"], "❓")
        
        print(f"\n  {emoji} Decision: {result['decision'].upper()}")
        print(f"  Reason: {result['reason']}")
        print(f"  Confidence: {result['confidence']:.0%}")
        if result["escalation_reason"]:
            print(f"  Escalation: {result['escalation_reason']}")
        
        print(f"\n  Step-by-step:")
        for step, detail in result["details"].items():
            status = "✅" if detail["passed"] else "❌"
            print(f"    {status} {step}: {detail['message']}")
    
    print(f"\n{'=' * 60}")
    print("Self-test complete")