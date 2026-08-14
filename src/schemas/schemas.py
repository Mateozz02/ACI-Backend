from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

"Product"
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    unit: str
    price: float
    category: Optional[str] = None
    is_available: bool = True


class ProductCreate(ProductBase):
    store_id:UUID


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    is_available: Optional[bool] = None


class ProductResponse(ProductBase):
    id: UUID
    store_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

"Store"
class StoreBase(BaseModel):
    name: str
    slug: Optional[str] = None
    phone: str
    address: Optional[str] = None
    description: Optional[str] = None


class StoreCreate(StoreBase):
    user_id: Optional[UUID] = None
    greeting_message: Optional[str] = None
    payment_instructions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    openwa_session_name: Optional[str] = None


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    greeting_message: Optional[str] = None
    payment_instructions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    is_active: Optional[bool] = None
    openwa_session_name: Optional[str] = None


class StoreResponse(StoreBase):
    id: UUID
    greeting_message: Optional[str] = None
    payment_instructions: Optional[str] = None
    cancellation_policy: Optional[str] = None
    openwa_session_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

"Order"
class OrderItemBase(BaseModel):
    product_name: str
    quantity: float
    unit_price: float


class OrderItemCreate(OrderItemBase):
    product_id: Optional[UUID] = None


class OrderItemResponse(OrderItemBase):
    id: UUID
    product_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: str


class OrderCreate(OrderBase):
    store_id: UUID
    raw_message: Optional[str] = None
    conversation_id: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    payment_reference: Optional[str] = None
    payment_date: Optional[datetime] = None


class OrderResponse(OrderBase):
    id: UUID
    store_id: UUID
    status: str
    total_amount: Optional[float] = None
    payment_reference: Optional[str] = None
    payment_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderDetailResponse(OrderResponse):
    items: list[OrderItemResponse] = []

    class Config:
        from_attributes = True

class ParsedOrderItem(BaseModel):
    producto: str
    cantidad: float
    unidad: str
    ambiguous: bool = False

class ParsedOrder(BaseModel):
    items: list[ParsedOrderItem]


class IntentResponse(BaseModel):
    """Structured output for intent detection."""
    intent: str  # LLM returns a string, mapped to Intent enum by detect_intent


class OrchestratorDecision(BaseModel):
    """LLM decides how to process an order message."""
    decision: str  # "regex", "llm", or "other"

"User"
class UserCreate(BaseModel):
    email: str
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    tier: str = "free"
    created_at: datetime

    class Config:
        from_attributes = True