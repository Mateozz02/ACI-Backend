import uuid
import re
from enum import Enum as PyEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    UniqueConstraint,
    Index,
    event,
)
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database import Base
from src.services.embeddings import generate_embedding


class OrderStatus(str, PyEnum):
    RECEIVED = "received"
    PARSED = "parsed"
    CONFIRMED = "confirmed"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_RECEIVED = "payment_received"
    VERIFIED = "verified"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Store(Base):
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    phone = Column(String(50), unique=True, nullable=False)
    address = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    greeting_message = Column(Text, nullable=True)
    payment_instructions = Column(Text, nullable=True)
    cancellation_policy = Column(Text, nullable=True)
    openwa_session_name = Column(String(255), nullable=True)
    openwa_session_id = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    chatbot_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    products = relationship("Product", back_populates="store", lazy="selectin")
    orders = relationship("Order", back_populates="store", lazy="selectin")
    

    __table_args__ = (
        Index("idx_stores_phone", "phone"),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)

    category = Column(String(100), nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    embedding = Column(Vector(384), nullable=True)

    store = relationship("Store", back_populates="products")

    __table_args__ = (
        Index("idx_products_store_id", "store_id"),
        Index("idx_products_category", "category"),
        UniqueConstraint("store_id", "name", name="uq_product_store_name"),
    )


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)

    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=False)

    status = Column(Enum(OrderStatus), default=OrderStatus.RECEIVED, nullable=False)

    total_amount = Column(Float, nullable=True)

    payment_reference = Column(String(255), nullable=True)
    payment_date = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)
    raw_message = Column(Text, nullable=True)

    conversation_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("OrderItem", back_populates="order", lazy="selectin")
    store = relationship("Store", back_populates="orders")

    __table_args__ = (
        Index("idx_orders_store_id", "store_id"),
        Index("idx_orders_status", "status"),
        Index("idx_orders_customer_phone", "customer_phone"),
        Index("idx_orders_created_at", "created_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)

    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    product_name = Column(String(255), nullable=False)

    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    subtotal = Column(Float, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="items")
    product = relationship("Product", lazy="selectin")

    __table_args__ = (
        Index("idx_order_items_order_id", "order_id"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)

    customer_phone = Column(String(50), nullable=False)
    session_id = Column(String(255), nullable=False)

    messages = Column(JSON, default=list)
    context = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_conversations_session", "session_id"),
        UniqueConstraint("store_id", "customer_phone", "session_id", name="uq_conv_store_phone_session"),
    )


class Message(Base):
    """Individual chat messages between customer and store."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)

    customer_phone = Column(String(50), nullable=False)
    customer_name = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'store'
    content = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    intent = Column(String(50), nullable=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    store = relationship("Store")
    order = relationship("Order", lazy="selectin")

    __table_args__ = (
        Index("idx_messages_store_phone", "store_id", "customer_phone"),
        Index("idx_messages_created_at", "created_at"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    tier = Column(String(50), default="free", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    

@event.listens_for(Store, "before_insert")
def _set_store_slug_insert(mapper, connection, target):
    if target.name:
        slug = target.name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        target.slug = slug


@event.listens_for(Store, "before_update")
def _set_store_slug_update(mapper, connection, target):
    if target.name:
        new_slug = target.name.lower()
        new_slug = re.sub(r"[^a-z0-9]+", "-", new_slug)
        new_slug = new_slug.strip("-")
        if new_slug != target.slug:
            target.slug = new_slug


@event.listens_for(Product, "before_insert")
@event.listens_for(Product, "before_update")
def _set_product_embedding(mapper, connection, target):
    if target.name:
        target.embedding = generate_embedding(target.name)
