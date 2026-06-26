import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --------------------------------------------------
# Project Import
# --------------------------------------------------

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from data.models import (
    Customer,
    Order,
    RefundRequest,
    RefundHistory,
)

# --------------------------------------------------
# Database
# --------------------------------------------------

DB_PATH = "data/crm.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
)

SessionLocal = sessionmaker(bind=engine)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

TODAY = datetime.now()


def days_ago(days: int, minutes: int = 0):
    return TODAY - timedelta(days=days, minutes=minutes)


def clear_database(session):

    session.query(RefundRequest).delete()

    session.query(Order).delete()

    session.query(RefundHistory).delete()

    session.query(Customer).delete()

    session.commit()


# --------------------------------------------------
# Seed Customers
# --------------------------------------------------

def seed_customers(session):

    customers = []

    tiers = (
        ["Bronze"] * 5 +
        ["Silver"] * 5 +
        ["Gold"] * 5
    )

    for i in range(15):

        customer = Customer(

            customer_id=f"CUST-{1000+i}",

            name=f"Customer {i+1}",

            email=f"customer{i+1}@example.com",

            tier=tiers[i]

        )

        customers.append(customer)

    session.add_all(customers)

    session.commit()

    return customers


# --------------------------------------------------
# Seed Orders
# --------------------------------------------------

def seed_orders(session, customers):

    orders = []

    categories = [
        "physical",
        "digital",
        "perishable",
        "electronics",
        "apparel"
    ]

    # -------------------------------
    # 12 APPROVAL ORDERS
    # -------------------------------

    approval_cases = [

        ("physical",15,"delivered",1500),

        ("digital",10,"delivered",900),

        ("perishable",5,"delivered",450),

        ("electronics",20,"delivered",8500),

        ("apparel",18,"delivered",2200),

        ("physical",12,"delivered",1700),

        ("electronics",25,"delivered",12000),

        ("physical",28,"delivered",3500),

        ("digital",6,"delivered",700),

        ("perishable",3,"delivered",550),

        ("physical",14,"delivered",2100),

        ("apparel",8,"delivered",1800),

    ]

    # -------------------------------
    # 12 REJECTION ORDERS
    # -------------------------------

    rejection_cases = [

        ("physical",45,"delivered",2500),

        ("digital",20,"delivered",800),

        ("perishable",15,"delivered",600),

        ("physical",50,"shipped",1900),

        ("electronics",70,"delivered",15000),

        ("apparel",40,"pending",1800),

        ("physical",55,"delivered",1200),

        ("digital",30,"delivered",650),

        ("perishable",18,"delivered",430),

        ("electronics",90,"pending",24000),

        ("physical",65,"delivered",2800),

        ("apparel",48,"shipped",3500),

    ]

    # -------------------------------
    # 10 ESCALATION ORDERS
    # -------------------------------

    escalation_cases = [

        ("physical",30,"delivered",2500),

        ("electronics",22,"delivered",72000),

        ("physical",18,"delivered",3500),

        ("physical",16,"delivered",2800),

        ("electronics",12,"delivered",5400),

        ("physical",25,"delivered",1500),

        ("physical",44,"delivered",2100),

        ("electronics",19,"delivered",9500),

        ("physical",29,"delivered",2600),

        ("apparel",27,"delivered",1800),

    ]

    # -------------------------------
    # 16 NORMAL ORDERS
    # -------------------------------

    normal_cases = [

        ("physical",11,"delivered",1200),

        ("digital",7,"delivered",900),

        ("electronics",31,"shipped",25000),

        ("perishable",4,"delivered",500),

        ("apparel",17,"delivered",1600),

        ("physical",23,"pending",2700),

        ("electronics",9,"delivered",18000),

        ("physical",35,"delivered",2200),

        ("digital",5,"delivered",750),

        ("apparel",13,"shipped",2100),

        ("physical",26,"delivered",1300),

        ("electronics",41,"delivered",39000),

        ("perishable",2,"delivered",350),

        ("physical",32,"pending",4800),

        ("digital",8,"delivered",980),

        ("apparel",21,"delivered",1700),

    ]

    all_cases = (
        approval_cases +
        rejection_cases +
        escalation_cases +
        normal_cases
    )

    for index, case in enumerate(all_cases):

        category, days, shipping, amount = case

        customer = customers[index % len(customers)]

        order = Order(

            order_id=f"ORD-{5000+index}",

            customer_id=customer.customer_id,

            order_date=days_ago(days),

            product_category=category,

            purchase_amount=amount,

            shipping_status=shipping,

            return_window_days=30,

        )

        orders.append(order)

    session.add_all(orders)

    session.commit()

    return orders
# --------------------------------------------------
# Seed Refund Requests
# --------------------------------------------------

def seed_refund_requests(session, orders):

    refund_requests = []

    # --------------------------------------------------
    # APPROVAL SCENARIOS (12)
    # --------------------------------------------------

    approval_cases = [

        ("Changed Mind", "unopened", False, True, False, False, "none",
         "Product is sealed and within return window.", False),

        ("Accidental Purchase", "unopened", False, True, False, False, "none",
         "Purchased by mistake.", False),

        ("Product Not Needed", "unopened", False, True, False, False, "none",
         "No longer needed.", False),

        ("Size Issue", "opened", True, True, False, False, "none",
         "Wrong size ordered.", False),

        ("Duplicate Order", "unopened", False, True, False, False, "none",
         "Ordered twice accidentally.", False),

        ("Better Alternative", "opened", True, True, False, False, "none",
         "Purchased another model.", False),

        ("Changed Mind", "unopened", False, True, False, False, "none",
         "Returning unopened item.", False),

        ("Gift Return", "unopened", False, True, False, False, "none",
         "Recipient doesn't need it.", False),

        ("Subscription Error", "unopened", False, True, False, False, "none",
         "Wrong digital purchase.", False),

        ("Food Preference", "sealed", False, True, False, False, "none",
         "Ordered incorrect item.", False),

        ("Order Cancellation", "unopened", False, True, False, False, "none",
         "Cancelled after delivery.", False),

        ("Exchange Instead", "opened", True, True, False, False, "none",
         "Prefers different product.", False),

    ]

    # --------------------------------------------------
    # REJECTION SCENARIOS (12)
    # --------------------------------------------------

    rejection_cases = [

        ("Expired Window", "used", True, True, False, False, "none",
         "Request submitted too late.", False),

        ("Digital Consumed", "used", True, True, False, False, "none",
         "Already downloaded.", False),

        ("Perishable Expired", "opened", True, True, False, False, "none",
         "Expired return period.", False),

        ("Order In Transit", "unopened", False, True, False, False, "none",
         "Shipment still in transit.", False),

        ("Used Product", "used", True, True, False, False, "none",
         "Product heavily used.", False),

        ("Final Sale", "opened", True, True, False, False, "none",
         "Final sale purchase.", False),

        ("Late Return", "used", True, True, False, False, "none",
         "Outside policy.", False),

        ("Gift Card", "opened", True, True, False, False, "none",
         "Gift cards are non-refundable.", False),

        ("Opened Food", "opened", True, True, False, False, "none",
         "Perishable already opened.", False),

        ("Shipping Pending", "unopened", False, True, False, False, "none",
         "Package not delivered.", False),

        ("Refund Limit", "opened", True, True, False, False, "none",
         "Exceeded yearly refund limit.", False),

        ("Fraud Account", "opened", True, True, False, False, "none",
         "Account under fraud review.", False),

    ]

    # --------------------------------------------------
    # ESCALATION SCENARIOS (10)
    # --------------------------------------------------

    escalation_cases = [

        (
            "Boundary Time",
            "unopened",
            False,
            True,
            False,
            False,
            "none",
            "I submitted the refund request at 11:59 PM but it was recorded at 12:01 AM.",
            True
        ),

        (
            "High Value Order",
            "unopened",
            False,
            True,
            False,
            False,
            "none",
            "High-value purchase requiring manager approval.",
            True
        ),

        (
            "Lost Shipment",
            "unopened",
            False,
            True,
            False,
            False,
            "lost",
            "Tracking says delivered but I never received the package.",
            True
        ),

        (
            "Damaged Product",
            "damaged",
            True,
            True,
            True,
            False,
            "none",
            "Product arrived damaged.",
            True
        ),

        (
            "Wrong Item",
            "opened",
            True,
            True,
            False,
            True,
            "none",
            "Received a different product.",
            True
        ),

        (
            "Missing Receipt",
            "unopened",
            False,
            False,
            False,
            False,
            "none",
            "I lost my receipt but I purchased it from your store.",
            True
        ),

        (
            "Goodwill Exception",
            "opened",
            True,
            True,
            False,
            False,
            "none",
            "I'm a loyal customer. Please make a one-time exception.",
            True
        ),

        (
            "Policy Dispute",
            "opened",
            True,
            True,
            False,
            False,
            "none",
            "Last time your support team approved the same request.",
            True
        ),

        (
            "Legal Complaint",
            "opened",
            True,
            True,
            False,
            False,
            "none",
            "I'll file a consumer complaint if this isn't resolved.",
            True
        ),

        (
            "Low Confidence",
            "opened",
            True,
            True,
            False,
            False,
            "none",
            "The information in my account doesn't seem correct.",
            True
        ),

    ]

    scenarios = (
        approval_cases +
        rejection_cases +
        escalation_cases
    )

    for index, scenario in enumerate(scenarios):

        (
            reason,
            condition,
            opened,
            receipt,
            damaged,
            wrong_item,
            delivery_issue,
            comments,
            manual_review
        ) = scenario

        if index < 12:
            ai_decision = "approve"
            status = "approved"

        elif index < 24:
            ai_decision = "reject"
            status = "rejected"

        else:
            ai_decision = "escalate"
            status = "pending"

        request = RefundRequest(

            request_id=f"REF-{7000+index}",

            order_id=orders[index].order_id,

            request_date=days_ago(2),

            refund_reason=reason,

            product_condition=condition,

            package_opened=opened,

            receipt_available=receipt,

            damage_reported=damaged,

            wrong_item_received=wrong_item,

            delivery_issue=delivery_issue,

            customer_comments=comments,

            ai_decision=ai_decision,

            manual_review_required=manual_review,

            status=status,

        )

        refund_requests.append(request)

    session.add_all(refund_requests)

    session.commit()

    return refund_requests


# --------------------------------------------------
# Seed Refund History
# --------------------------------------------------

def seed_refund_history(session, customers):

    histories = []

    for index, customer in enumerate(customers):

        if index < 5:

            refund_count = 0
            fraud = False

        elif index < 10:

            refund_count = 2
            fraud = False

        else:

            refund_count = 4
            fraud = True

        history = RefundHistory(

            customer_id=customer.customer_id,

            refund_count=refund_count,

            last_refund_date=days_ago(30 + index),

            fraud_flag=fraud,

        )

        histories.append(history)

    session.add_all(histories)

    session.commit()

    return histories
# --------------------------------------------------
# Verification
# --------------------------------------------------

def verify_database(session):

    print("\n" + "=" * 60)
    print("DATABASE VERIFICATION")
    print("=" * 60)

    print(f"Customers        : {session.query(Customer).count()}")
    print(f"Orders           : {session.query(Order).count()}")
    print(f"Refund Requests  : {session.query(RefundRequest).count()}")
    print(f"Refund History   : {session.query(RefundHistory).count()}")

    print("\nRefund Decisions")

    print(
        f"Approved  : {session.query(RefundRequest).filter_by(ai_decision='approve').count()}"
    )

    print(
        f"Rejected  : {session.query(RefundRequest).filter_by(ai_decision='reject').count()}"
    )

    print(
        f"Escalated : {session.query(RefundRequest).filter_by(ai_decision='escalate').count()}"
    )

    print("\nSample Refund Requests")
    print("-" * 60)

    samples = session.query(RefundRequest).limit(5).all()

    for request in samples:

        print(
            f"{request.request_id} | "
            f"{request.order_id} | "
            f"{request.refund_reason} | "
            f"{request.ai_decision.upper()} | "
            f"Manual Review: {request.manual_review_required}"
        )

    print("=" * 60)


# --------------------------------------------------
# Main Seeder
# --------------------------------------------------

def seed_data():

    session = SessionLocal()

    clear_database(session)

    customers = seed_customers(session)

    orders = seed_orders(session, customers)

    refund_requests = seed_refund_requests(session, orders)

    refund_history = seed_refund_history(session, customers)

    verify_database(session)

    print("\nSeeding Completed Successfully")

    print(f"Customers         : {len(customers)}")
    print(f"Orders            : {len(orders)}")
    print(f"Refund Requests   : {len(refund_requests)}")
    print(f"Refund History    : {len(refund_history)}")

    session.close()


# --------------------------------------------------
# Run
# --------------------------------------------------

if __name__ == "__main__":

    seed_data()