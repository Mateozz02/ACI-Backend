from typing import TypedDict, Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class Intent(str, Enum):
    GREETING = "greeting"
    ORDER = "order"
    ORDER_STATUS = "order_status"
    CANCEL = "cancel"
    HELP = "help"
    CATALOG = "catalog"
    PAYMENT = "payment"
    SEND_RECEIPT = "send_receipt"
    UNKNOWN = "unknown"


class OrderState(TypedDict):
    phone: str
    store_id: Optional[UUID]
    message: str
    intent: Intent
    order_id: Optional[UUID]
    parsed_items: Optional[list[dict]]
    total: Optional[float]
    response: Optional[str]
    conversation_history: list[dict]
    timestamp: datetime
    has_ambiguous: Optional[bool]
    image_bytes: Optional[bytes]     
    image_path: Optional[str] 
