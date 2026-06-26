from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    
    customer_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    tier = Column(String, nullable=False)  # Bronze, Silver, Gold
    
    # Relationships
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    refund_history = relationship("RefundHistory", back_populates="customer", uselist=False)


class Order(Base):
    __tablename__ = "orders"
    
    order_id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), nullable=False)
    order_date = Column(DateTime, nullable=False)
    product_category = Column(String, nullable=False)  # physical, digital, perishable, apparel, etc.
    purchase_amount = Column(Float, nullable=False)
    shipping_status = Column(String, nullable=False)  # delivered, shipped, pending
    return_window_days = Column(Integer, nullable=False, default=30)
    
    # Relationships
    customer = relationship("Customer", back_populates="orders")


class RefundHistory(Base):
    __tablename__ = "refund_history"
    
    customer_id = Column(String, ForeignKey("customers.customer_id"), primary_key=True)
    refund_count = Column(Integer, nullable=False, default=0)
    last_refund_date = Column(DateTime, nullable=True)
    fraud_flag = Column(Boolean, nullable=False, default=False)
    
    # Relationships
    customer = relationship("Customer", back_populates="refund_history")


def create_database(db_path: str = "data/crm.db"):
    """Create the SQLite database and all tables."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    print(f"✅ Database created at: {db_path}")
    print("Tables: customers, orders, refund_history")
    return engine


if __name__ == "__main__":
    create_database()