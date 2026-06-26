# tools/refund_calculator.py
"""
Refund Calculator - Determines refund amount and type based on CRM data.

Handles:
  - Full vs partial refunds
  - Refund method (original payment, store credit, etc.)
  - Restocking fees for opened items
  - High-value order partial holds
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


# ─── Constants ──────────────────────────────────────────────

# Restocking fee percentage for opened items
RESTOCKING_FEE_PERCENT = 15.0  # 15%

# Refund types
REFUND_TYPE_ORIGINAL = "original_payment"
REFUND_TYPE_STORE_CREDIT = "store_credit"
REFUND_TYPE_PARTIAL = "partial_refund"

# Product categories exempt from restocking fees
NO_RESTOCKING_CATEGORIES = ["digital", "perishable"]

# Digital products always refund to original payment
DIGITAL_REFUND_TYPE = REFUND_TYPE_ORIGINAL


# ─── Data Classes ───────────────────────────────────────────

@dataclass
class RefundCalculation:
    """Structured refund calculation result."""
    refund_amount: float
    original_amount: float
    refund_type: str
    restocking_fee: float
    is_full_refund: bool
    breakdown: Dict[str, Any]
    notes: Optional[str] = None


# ─── Calculator Functions ───────────────────────────────────

def _calculate_restocking_fee(
    purchase_amount: float,
    product_category: str,
    package_opened: bool,
    product_condition: str
) -> float:
    """
    Determine if restocking fee applies.
    
    Rules:
    - Digital and perishable goods: no restocking fee
    - Unopened items: no restocking fee
    - Opened physical items: 15% restocking fee
    """
    category_lower = product_category.lower() if product_category else ""
    
    # Exempt categories
    if category_lower in NO_RESTOCKING_CATEGORIES:
        return 0.0
    
    # Unopened items exempt
    if not package_opened and product_condition in ("unopened", "like_new"):
        return 0.0
    
    # Opened physical items get restocking fee
    if package_opened or product_condition == "opened":
        return round(purchase_amount * RESTOCKING_FEE_PERCENT / 100, 2)
    
    return 0.0


def _determine_refund_type(
    product_category: str,
    purchase_amount: float,
    restocking_fee: float
) -> str:
    """
    Determine how the refund should be issued.
    
    Rules:
    - Digital products: original payment
    - Full refund (no fees): original payment
    - Partial refund (with fees): partial_refund
    """
    category_lower = product_category.lower() if product_category else ""
    
    # Digital always to original payment
    if category_lower == "digital":
        return REFUND_TYPE_ORIGINAL
    
    # If restocking fee applied, it's a partial refund
    if restocking_fee > 0:
        return REFUND_TYPE_PARTIAL
    
    return REFUND_TYPE_ORIGINAL


def calculate_refund(
    order: Dict[str, Any],
    refund_request: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate the refund amount and type.
    
    Args:
        order: Order dict from crm_lookup
        refund_request: RefundRequest dict from crm_lookup
    
    Returns:
        RefundCalculation as dictionary
    """
    purchase_amount = order.get("purchase_amount", 0.0)
    product_category = order.get("product_category", "")
    package_opened = refund_request.get("package_opened", False)
    product_condition = refund_request.get("product_condition", "")
    
    # Calculate restocking fee
    restocking_fee = _calculate_restocking_fee(
        purchase_amount, product_category, package_opened, product_condition
    )
    
    # Calculate final refund amount
    refund_amount = round(purchase_amount - restocking_fee, 2)
    
    # Determine refund type
    refund_type = _determine_refund_type(product_category, purchase_amount, restocking_fee)
    
    # Build breakdown
    breakdown = {
        "purchase_amount": purchase_amount,
        "restocking_fee_percent": RESTOCKING_FEE_PERCENT if restocking_fee > 0 else 0,
        "restocking_fee_amount": restocking_fee,
        "package_opened": package_opened,
        "product_condition": product_condition,
        "product_category": product_category
    }
    
    # Generate notes
    notes = None
    if restocking_fee > 0:
        notes = (
            f"Restocking fee of {RESTOCKING_FEE_PERCENT}% (₹{restocking_fee:,.2f}) "
            f"applied due to opened product condition."
        )
    elif product_category.lower() == "digital":
        notes = "Digital product - refund to original payment method."
    
    return asdict(RefundCalculation(
        refund_amount=refund_amount,
        original_amount=purchase_amount,
        refund_type=refund_type,
        restocking_fee=restocking_fee,
        is_full_refund=(restocking_fee == 0),
        breakdown=breakdown,
        notes=notes
    ))


# ─── Tool Metadata ──────────────────────────────────────────

TOOL_METADATA = {
    "calculate_refund": {
        "description": "Calculate refund amount, fees, and payment method",
        "parameters": {
            "order": "Order dict",
            "refund_request": "RefundRequest dict"
        },
        "returns": "RefundCalculation dict with amount, type, fees, breakdown"
    }
}


# ─── Self-Test ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from crm_lookup import get_complete_case
    
    print("=" * 60)
    print("Refund Calculator - Self Test")
    print("=" * 60)
    
    # Test different scenarios
    test_cases = [
        ("REF-7000", "Standard physical unopened"),
        ("REF-7001", "Check if opened"),
        ("REF-7002", "Check if digital"),
    ]
    
    for request_id, description in test_cases:
        print(f"\n{'─' * 60}")
        print(f"Case: {request_id} - {description}")
        print(f"{'─' * 60}")
        
        case = get_complete_case(request_id)
        if not case:
            print(f"  ❌ Could not retrieve case")
            continue
        
        result = calculate_refund(
            order=case["order"],
            refund_request=case["refund_request"]
        )
        
        print(f"  Original Amount: ₹{result['original_amount']:,.2f}")
        print(f"  Restocking Fee:  ₹{result['restocking_fee']:,.2f}")
        print(f"  Refund Amount:   ₹{result['refund_amount']:,.2f}")
        print(f"  Refund Type:     {result['refund_type']}")
        print(f"  Full Refund:     {result['is_full_refund']}")
        if result['notes']:
            print(f"  Notes:           {result['notes']}")
    
    # Test edge cases
    print(f"\n{'─' * 60}")
    print("Edge Case: Opened physical product")
    print(f"{'─' * 60}")
    
    test_order = {
        "purchase_amount": 2000.00,
        "product_category": "physical"
    }
    test_request = {
        "package_opened": True,
        "product_condition": "opened"
    }
    result = calculate_refund(test_order, test_request)
    print(f"  Amount: ₹{result['original_amount']:,.2f}")
    print(f"  Fee:    ₹{result['restocking_fee']:,.2f} (15%)")
    print(f"  Refund: ₹{result['refund_amount']:,.2f}")
    
    print(f"\n{'=' * 60}")
    print("Self-test complete")