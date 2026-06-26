from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


# -------------------------
# Customer
# -------------------------
class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    tier = Column(String, nullable=False)

    orders = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    refund_history = relationship(
        "RefundHistory",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan",
    )


# -------------------------
# Orders
# -------------------------
class Order(Base):
    __tablename__ = "orders"

    order_id = Column(String, primary_key=True)

    customer_id = Column(
        String,
        ForeignKey("customers.customer_id"),
        nullable=False,
    )

    order_date = Column(DateTime, nullable=False)

    product_category = Column(String, nullable=False)

    purchase_amount = Column(Float, nullable=False)

    shipping_status = Column(String, nullable=False)

    return_window_days = Column(Integer, nullable=False)

    customer = relationship("Customer", back_populates="orders")

    refund_requests = relationship(
        "RefundRequest",
        back_populates="order",
        cascade="all, delete-orphan",
    )


# -------------------------
# Refund Requests
# -------------------------
class RefundRequest(Base):
    __tablename__ = "refund_requests"

    request_id = Column(String, primary_key=True)

    order_id = Column(
        String,
        ForeignKey("orders.order_id"),
        nullable=False,
    )

    request_date = Column(DateTime, nullable=False)

    refund_reason = Column(String, nullable=False)

    product_condition = Column(String, nullable=False)

    package_opened = Column(Boolean, default=False)

    receipt_available = Column(Boolean, default=True)

    damage_reported = Column(Boolean, default=False)

    wrong_item_received = Column(Boolean, default=False)

    delivery_issue = Column(
        String,
        default="none",
    )

    customer_comments = Column(Text)

    ai_decision = Column(
        String,
        default="pending",
    )

    manual_review_required = Column(
        Boolean,
        default=False,
    )

    status = Column(
        String,
        default="pending",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    order = relationship(
        "Order",
        back_populates="refund_requests",
    )


# -------------------------
# Refund History
# -------------------------
class RefundHistory(Base):
    __tablename__ = "refund_history"

    customer_id = Column(
        String,
        ForeignKey("customers.customer_id"),
        primary_key=True,
    )

    refund_count = Column(Integer, default=0)

    last_refund_date = Column(DateTime)

    fraud_flag = Column(Boolean, default=False)

    customer = relationship(
        "Customer",
        back_populates="refund_history",
    )


# -------------------------
# Create Database
# -------------------------
def create_database(db_path="data/crm.db"):

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
    )

    Base.metadata.create_all(engine)

    print("Database Created Successfully")
    print("Tables Created")

    print("- customers")
    print("- orders")
    print("- refund_requests")
    print("- refund_history")

    return engine


if __name__ == "__main__":
    create_database()