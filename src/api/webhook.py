from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from src.config import get_settings
from src.database import async_session_maker
from src.models.models import Store
from src.services.agent import process_message
from src.services.openwa import openwa_service

router = APIRouter(prefix="/webhook", tags=["webhook"])
settings = get_settings()


class OpenWAMessage(BaseModel):
    session: str
    chatId: str
    text: Optional[str] = None
    hasMedia: bool = False
    mediaUrl: Optional[str] = None
    fromMe: bool = False
    timestamp: int
    author: Optional[str] = None


class WebhookEvent(BaseModel):
    event: str
    session: str
    data: dict


def format_phone(phone: str) -> str:
    """Convert phone to WhatsApp format: 573001234567"""
    phone = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    if phone.endswith("@s.whatsapp.net"):
        phone = phone.replace("@s.whatsapp.net", "")
    return phone


@router.post("/openwa")
async def receive_openwa_webhook(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    if settings.openwa_api_key != "orderflow-api-key-change-in-production":
        if x_api_key != settings.openwa_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = body.get("event", "")

    if event == "message":
        return await handle_message(body.get("data", {}))
    elif event == "session_status":
        return {"status": "ok"}
    else:
        return {"status": "ignored", "event": event}


async def _resolve_store_id() -> UUID | None:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Store.id).where(Store.is_active == True).limit(1)
        )
        row = result.scalar_one_or_none()
        return row


async def handle_message(data: dict):
    message = OpenWAMessage(
        session=data.get("session", ""),
        chatId=data.get("chatId", ""),
        text=data.get("text", ""),
        hasMedia=data.get("hasMedia", False),
        mediaUrl=data.get("mediaUrl"),
        fromMe=data.get("fromMe", False),
        timestamp=data.get("timestamp", 0),
        author=data.get("author"),
    )

    if message.fromMe:
        return {"status": "ignored", "reason": "bot message"}

    phone = format_phone(message.chatId)

    print(f"[WEBHOOK] Message from {phone}: {message.text}")

    store_id = await _resolve_store_id()
    if store_id is None:
        print("[WEBHOOK] No active store found, skipping")
        return {"status": "no_store"}

    if message.text:
        result = await process_message(
            phone=phone,
            message=message.text,
            store_id=store_id,
        )

        if result.get("response"):
            await openwa_service.send_text(phone, result["response"])
            print(f"[WEBHOOK] Sent reply to {phone}")

        return {
            "status": "processed",
            "phone": phone,
            "store_id": str(store_id),
            "intent": result.get("intent"),
            "response": result.get("response"),
            "parsed_items": result.get("parsed_items"),
        }

    return {
        "status": "received_no_text",
        "phone": phone,
        "store_id": str(store_id),
        "hasMedia": message.hasMedia,
    }
