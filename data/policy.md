# AI Customer Support Refund Policy

**Version:** 1.0  
**Last Updated:** June 2026

---

# Refund Eligibility Policy

This document defines the official refund policy used by the AI Customer Support Agent for automated refund decisions.

The AI assistant retrieves information from this document using Retrieval-Augmented Generation (RAG). All refund decisions should follow these rules unless an escalation is required.

---

# 1. Refund Time Limits

Customers must request a refund within the allowed return window.

| Product Type | Refund Window |
|--------------|---------------|
| Physical Products | 30 days from delivery |
| Digital Products | 14 days from purchase |
| Perishable Goods | 7 days from delivery |

Requests submitted after the allowed window are normally rejected.

---

# 2. Gold Member Exception

Gold-tier customers receive an extended return period.

Additional benefit:

- Gold members receive an extra **15 days** beyond the standard refund window.

Examples:

- Physical item:
  - Standard customer: 30 days
  - Gold customer: 45 days

- Digital product:
  - Standard customer: 14 days
  - Gold customer: 29 days

- Perishable goods:
  - Standard customer: 7 days
  - Gold customer: 22 days

---

# 3. Product Condition Requirements

Refunds are approved only when products satisfy all of the following conditions:

- Item is unused
- Item is unopened
- Original packaging is available
- Original accessories are included
- Purchase receipt or order confirmation is available

Products that are damaged due to customer misuse are not eligible.

---

# 4. Shipping Requirements

Refund processing depends on delivery status.

Eligible:

- Delivered orders
- Customer has received the package

Not Eligible:

- Orders still in transit
- Orders marked as processing
- Orders not yet shipped

Lost or damaged shipments should be escalated for manual review.

---

# 5. Non-Refundable Categories

The following categories are not eligible for refunds:

- Final Sale items
- Gift Cards
- Intimate Apparel
- Personalized or Custom-made products

These exclusions apply regardless of customer tier.

---

# 6. Digital Product Policy

Digital products are refundable only if:

- Request is made within 14 days (29 days for Gold members)
- Product has not been substantially consumed
- No abuse of download policy is detected

Digital licenses that have been permanently activated are generally not refundable.

---

# 7. Perishable Goods Policy

Perishable items must satisfy all conditions:

- Refund requested within 7 days
- Product arrived damaged
- Product spoiled before expected shelf life
- Valid proof (photo or description) is provided

Expired requests are rejected unless manually approved.

---

# 8. Fraud Prevention Rules

To prevent refund abuse, automated checks are performed.

A refund request may be denied if:

- Customer has received more than **3 refunds in the last 12 months**
- Fraud flag exists on the customer account
- Multiple refund requests are submitted within a short period (velocity check)
- Suspicious purchasing behavior is detected

Fraud-related requests should be escalated for manual investigation.

---

# 9. High-Value Orders

Orders with unusually high purchase amounts may require manual approval before refunds are issued.

The AI assistant should recommend escalation instead of automatic approval whenever additional verification is needed.

---

# 10. Receipt Requirement

Customers should provide one of the following:

- Order ID
- Purchase receipt
- Email confirmation

If no purchase evidence can be located, the request should be escalated.

---

# 11. Partial Refunds

Partial refunds may be issued when:

- Only part of an order is returned
- Accessories are missing
- Product condition is partially acceptable
- Restocking fees apply

The refund amount is determined by the refund calculation service.

---

# 12. Automatic Approval Conditions

A refund can be automatically approved when ALL of the following are true:

- Order exists
- Customer exists
- Refund window is valid
- Product category is refundable
- Delivery has completed
- Product condition requirements are satisfied
- Customer is below fraud thresholds
- No manual review rule is triggered

---

# 13. Automatic Rejection Conditions

A refund should be automatically rejected when ANY of the following are true:

- Refund window expired
- Product is a Final Sale item
- Product is a Gift Card
- Product is Intimate Apparel
- Product is personalized
- Customer exceeds refund limits
- Fraud flag is active
- Required documentation is missing

---

# 14. Escalation Rules

The AI assistant should escalate a case to a human support agent when:

- Fraud detection is triggered
- Purchase cannot be verified
- Shipping status is inconsistent
- High-value purchase requires approval
- Customer disputes the policy
- Multiple policies appear to conflict
- Confidence in the automated decision is low

---

# 15. Decision Priority

When evaluating refund requests, the AI should apply rules in the following order:

1. Verify customer identity
2. Verify order exists
3. Verify shipping status
4. Determine product category
5. Apply customer tier benefits
6. Check refund time window
7. Validate product condition
8. Perform fraud checks
9. Determine refund eligibility
10. Escalate if required

---
# 16. Human Review and Escalation Policy

The AI assistant should avoid making automated decisions whenever policy interpretation, customer evidence, or business judgment is required.

A case must be escalated to a human support agent if any of the following conditions are met.

---

## 16.1 Boundary Time Cases

Refund requests submitted within **5 minutes before or after** the refund deadline should not be automatically approved or rejected.

Examples:

- Refund submitted at 11:58 PM when the window expires at midnight.
- Refund submitted at 12:01 AM immediately after the deadline.

Reason:

Small timing differences may result from payment processing delays, network latency, or timezone differences.

Decision:

Escalate to Human Agent.

---

## 16.2 High-Value Orders

Orders with a purchase amount greater than **₹50,000** (or the configured business threshold) require manual approval.

Decision:

Escalate to Human Agent.

---

## 16.3 Lost Shipment Claims

If the order status shows "Delivered" but the customer claims the package was never received, the case must be manually investigated.

Decision:

Escalate to Human Agent.

---

## 16.4 Damaged Product Claims

If the customer reports that a product arrived damaged or defective, image verification or manual inspection may be required.

Decision:

Escalate to Human Agent.

---

## 16.5 Wrong Product Delivered

If the customer claims that the received product does not match the ordered product, warehouse verification is required.

Decision:

Escalate to Human Agent.

---

## 16.6 Missing Purchase Evidence

If no receipt or order confirmation is available and the AI cannot confidently verify the purchase from CRM records, the request should be escalated.

Decision:

Escalate to Human Agent.

---

## 16.7 Goodwill Exceptions

Support managers may approve refunds outside the normal policy for exceptional customer service reasons.

Examples include:

- Long-term loyal customers.
- Premium customers requesting a one-time exception.
- Minor policy violations.

The AI must never grant goodwill refunds automatically.

Decision:

Escalate to Human Agent.

---

## 16.8 Customer Disputes

If a customer disputes the refund policy, references previous exceptions, threatens legal action, or requests a supervisor, the AI should stop automated processing.

Decision:

Escalate to Human Agent.

---

## 16.9 AI Confidence Threshold

If the AI confidence score falls below the configured threshold (default: 0.65), the request should be transferred to a human agent instead of making an uncertain decision.

Decision:

Escalate to Human Agent.

---

## 16.10 Conflicting Information

The AI should escalate whenever customer statements conflict with CRM records.

Examples include:

- Customer says the package never arrived, but CRM says "Delivered".
- Customer claims they never requested a previous refund.
- Multiple records contain inconsistent information.

Decision:

Escalate to Human Agent.

# Summary

A refund is eligible only if:

- The request is within the allowed refund period.
- The product category is refundable.
- The product meets condition requirements.
- Delivery has been completed.
- Purchase evidence exists.
- Fraud checks pass.
- No escalation rule has been triggered.

This policy serves as the authoritative knowledge source for the AI Refund Processing Agent.