import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import random

# Ensure we can import models
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from data.models import Base, Customer, Order, RefundHistory

DB_PATH = "data/crm.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)

def seed_data():
    session = SessionLocal()
    
    # Clear existing data (for clean re-runs)
    session.query(Order).delete()
    session.query(RefundHistory).delete()
    session.query(Customer).delete()
    session.commit()
    
    # --- 15 Customers: 5 Bronze, 5 Silver, 5 Gold ---
    tiers = ["Bronze"] * 5 + ["Silver"] * 5 + ["Gold"] * 5
    customers = []
    
    for i in range(15):
        tier = tiers[i]
        customer_id = f"CUST-{1000 + i}"
        customer = Customer(
            customer_id=customer_id,
            name=f"Customer {i+1}",
            email=f"customer{i+1}@example.com",
            tier=tier,
        )
        customers.append(customer)
        session.add(customer)
    
    session.commit()
    
    # --- 50 Orders distributed across 15 customers ---
    categories = ["physical", "digital", "perishable", "apparel", "electronics"]
    shipping_statuses = ["delivered", "shipped", "pending"]
    
    orders = []
    today = datetime.now()
    
    for i in range(50):
        customer = random.choice(customers)
        
        # Vary order dates to create different scenarios
        # 5 clean refund-eligible (within 30 days, unopened)
        # 5 edge cases (1 day past window, opened package)
        # 5 policy-violation cases (30+ days, digital goods)
        if i < 5:
            # Clean eligible: within window, physical, delivered
            days_ago = random.randint(5, 25)
            category = "physical"
            status = "delivered"
        elif i < 10:
            # Edge case: just past window or opened
            days_ago = random.randint(31, 35)
            category = random.choice(["physical", "apparel"])
            status = "delivered"
        elif i < 15:
            # Policy violation: very old or digital
            days_ago = random.randint(40, 90)
            category = random.choice(["digital", "perishable"])
            status = random.choice(["delivered", "shipped"])
        else:
            # Random mix for remaining 35 orders
            days_ago = random.randint(1, 60)
            category = random.choice(categories)
            status = random.choice(shipping_statuses)
        
        order_date = today - timedelta(days=days_ago)
        
        order = Order(
            order_id=f"ORD-{5000 + i}",
            customer_id=customer.customer_id,
            order_date=order_date,
            product_category=category,
            purchase_amount=round(random.uniform(10.0, 500.0), 2),
            shipping_status=status,
            return_window_days=30,
        )
        orders.append(order)
        session.add(order)
    
    session.commit()
    
    # --- Refund History ---
    # Some customers have refund history, some don't
    for customer in customers:
        if random.random() < 0.4:  # 40% have refund history
            refund_count = random.randint(1, 3)
            last_refund = today - timedelta(days=random.randint(10, 180))
            fraud_flag = refund_count >= 3  # Flag if 3+ refunds
            
            history = RefundHistory(
                customer_id=customer.customer_id,
                refund_count=refund_count,
                last_refund_date=last_refund,
                fraud_flag=fraud_flag,
            )
            session.add(history)
    
    session.commit()
    session.close()
    
    print("✅ Mock CRM data seeded successfully!")
    print(f"   15 customers (5 Bronze / 5 Silver / 5 Gold)")
    print(f"   50 orders")
    print(f"   Refund history for selected customers")

def verify_data():
    """Quick verification query."""
    session = SessionLocal()
    
    customer_count = session.query(Customer).count()
    order_count = session.query(Order).count()
    history_count = session.query(RefundHistory).count()
    
    print(f"\n📊 Database Verification:")
    print(f"   Customers: {customer_count}")
    print(f"   Orders: {order_count}")
    print(f"   Refund History Records: {history_count}")
    
    # Show a sample
    sample = session.query(Customer).first()
    if sample:
        print(f"\n   Sample Customer: {sample.name} | Tier: {sample.tier} | ID: {sample.customer_id}")
        print(f"   Orders: {len(sample.orders)}")
        if sample.refund_history:
            print(f"   Refund Count: {sample.refund_history.refund_count} | Fraud Flag: {sample.refund_history.fraud_flag}")
    
    session.close()

if __name__ == "__main__":
    seed_data()
    verify_data()