# AI Customer Support Refund Policy

**Version:** 2.0  
**Last Updated:** June 2026

---

# Purpose

This document is the official refund policy used by the AI Customer Support Agent.

The AI assistant retrieves information from this document using Retrieval-Augmented Generation (RAG) and combines it with CRM data to determine whether a refund request should be:

- Approved
- Rejected
- Escalated to a Human Support Agent

The policy document is the source of truth for business rules.

---

# Decision Outcomes

Every refund request must result in exactly one outcome.

| Decision | Description |
|-----------|-------------|
| APPROVE | Refund can be processed automatically. |
| REJECT | Refund violates company policy. |
| ESCALATE | Human review is required before a decision is made. |

---

# Standard Refund Windows

| Product Category | Refund Window |
|------------------|---------------|
| Physical Products | 30 Days |
| Digital Products | 14 Days |
| Perishable Goods | 7 Days |

The refund window begins once the product has been delivered.

---

# Gold Customer Benefits

Gold tier customers receive an additional **15-day refund window**.

Examples:

Physical Product

30 → 45 Days

Digital Product

14 → 29 Days

Perishable Product

7 → 22 Days

No other customer tiers receive this benefit.

---

# Product Eligibility

A product is eligible for refund only if:

- It is within the refund window.
- The item belongs to a refundable category.
- The order has been delivered.
- The customer has not exceeded fraud thresholds.

---

# Product Condition Rules

The AI should evaluate the following fields from the refund request.

| Database Field | Expected Value |
|----------------|----------------|
| product_condition | unopened or opened (acceptable if policy allows) |
| package_opened | False preferred |
| receipt_available | True preferred |
| damage_reported | False for normal refunds |
| wrong_item_received | False for normal refunds |

---

# Non-Refundable Categories

Refunds are never allowed for:

- Gift Cards
- Final Sale Products
- Personalized Products
- Intimate Apparel

These rules override all customer tiers.

---

# Shipping Rules

Refunds are only considered after delivery.

Shipping Status

Eligible:

- delivered

Not Eligible:

- pending
- shipped

If the customer disputes delivery information, the request must be escalated.

---

# Fraud Prevention

Refunds may be rejected when:

- Fraud flag is active.
- Customer exceeds 3 refunds within the review period.
- Suspicious refund behaviour is detected.

The AI should never override fraud rules.

---

# Automatic Approval Rules

The AI may approve a refund only if ALL conditions are satisfied.

- Order exists.
- Customer exists.
- Refund request exists.
- Product is refundable.
- Order delivered.
- Refund request within allowed time.
- Product condition acceptable.
- Receipt available.
- Fraud checks passed.
- Manual review not required.

---

# Automatic Rejection Rules

The AI should reject a refund request if ANY condition is true.

- Refund window expired.
- Product category not refundable.
- Shipping status is pending.
- Fraud flag is active.
- Refund limit exceeded.
- Product violates policy.

---

# Human Escalation Policy

The AI must never make uncertain decisions.

Whenever the following situations occur, the request must be transferred to a Human Support Agent.

---

## Boundary Time Requests

If a refund request is submitted within **5 minutes before or after** the refund deadline, the request should not be automatically approved or rejected.

Reason:

Possible timezone differences, payment delays, or network latency.

Decision:

ESCALATE

---

## High Value Orders

Orders with a purchase amount greater than ₹50,000 require manager approval.

Decision:

ESCALATE

---

## Lost Shipment

If

shipping_status = delivered

AND

delivery_issue = lost

Decision:

ESCALATE

---

## Damaged Products

If

damage_reported = True

Decision:

ESCALATE

Image verification may be required.

---

## Wrong Item Delivered

If

wrong_item_received = True

Decision:

ESCALATE

Warehouse verification is required.

---

## Missing Receipt

If

receipt_available = False

Decision:

ESCALATE

The AI should not reject immediately.

---

## Goodwill Requests

Examples

"I am a loyal customer."

"This is my first refund."

"I missed the deadline by only a few minutes."

These require human judgement.

Decision:

ESCALATE

---

## Customer Disputes

If the customer

- disputes the policy
- requests a supervisor
- references previous exceptions
- threatens legal action

Decision:

ESCALATE

---

## Conflicting Information

Examples

CRM:

shipping_status = delivered

Customer:

"I never received it."

OR

Customer claims wrong product.

Decision:

ESCALATE

---

## Manual Review Flag

If

manual_review_required = True

Decision:

ESCALATE

This database field always overrides automatic approval or rejection.

---

# Decision Priority

The AI should evaluate information in the following order.

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

---

# CRM Fields Used

The AI agent should use the following CRM fields during evaluation.

Customer

- customer_id
- tier

Order

- order_id
- purchase_amount
- order_date
- shipping_status
- product_category

Refund Request

- request_date
- refund_reason
- product_condition
- package_opened
- receipt_available
- damage_reported
- wrong_item_received
- delivery_issue
- customer_comments
- manual_review_required

Refund History

- refund_count
- last_refund_date
- fraud_flag

---

# AI Behaviour

The AI assistant should:

- Never invent customer information.
- Always retrieve policy information before making a decision.
- Explain why a refund was approved or rejected.
- Escalate whenever policy requires human judgement.
- Never override fraud rules.
- Never override the manual_review_required flag.
- Always provide a professional explanation.

---

# Summary

The refund decision is determined using:

1. CRM Database
2. Refund Request Information
3. Refund History
4. Refund Policy
5. Customer Tier

The AI must return exactly one decision.

- APPROVE
- REJECT
- ESCALATE