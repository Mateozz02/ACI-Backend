import secrets
import time
import hashlib

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

from sqlalchemy import select

import httpx

from src.config import get_settings
from src.database import async_session_maker
from src.models.models import Store
from src.services.agent import process_message
from src.services.openwa import OpenWAService
from src.utils import logger

router = APIRouter(prefix="/webhook", tags=["webhook"])
settings = get_settings()

# Deduplication: track recently processed messages to prevent double-processing
# OpenWA sometimes delivers the same webhook event twice.
_seen_messages: dict[str, float] = {}
_DEDUP_TTL = 30  # seconds


def _is_duplicate(phone: str, text: str, timestamp: int) -> bool:
    """Check if a message was already processed recently."""
    key = hashlib.sha256(f"{phone}:{text}:{timestamp}".encode()).hexdigest()
    now = time.time()
    # Clean expired entries
    for k in list(_seen_messages):
        if now - _seen_messages[k] > _DEDUP_TTL:
            del _seen_messages[k]
    if key in _seen_messages:
        return True
    _seen_messages[key] = now
    return False


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
    if not secrets.compare_digest(x_api_key or "", settings.openwa_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = body.get("event", "")
    logger.info(f"[WEBHOOK] raw event={event} keys={list(body.keys())}")

    if event == "message":
        # OpenWA 0.10.x uses "payload", older versions used "data"
        msg_data = body.get("payload") or body.get("data", {})
        session_name = body.get("session", msg_data.get("session", ""))
        return await handle_message(session_name, msg_data)
    elif event == "session_status":
        return {"status": "ok"}
    else:
        return {"status": "ignored", "event": event}


async def _resolve_store_id(session_name: str) -> tuple[UUID | None, Store | None]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Store).where(
                Store.is_active,
                Store.openwa_session_name == session_name,
            ).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None, None
        return row.id, row


async def handle_message(session_name: str, data: dict):
    # Normalize field names: OpenWA 0.10.x uses different keys
    if "chatId" not in data and "from" in data:
        data["chatId"] = data["from"]
    if "text" not in data and "body" in data:
        data["text"] = data["body"]
    if "hasMedia" not in data:
        data["hasMedia"] = data.get("type") in ("image", "video", "document", "audio") or data.get("hasMedia", False)
    if "fromMe" not in data:
        data["fromMe"] = data.get("fromMe", False)

    message = OpenWAMessage(
        session=session_name or data.get("session", ""),
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

    # Skip duplicate webhook deliveries
    if _is_duplicate(phone, message.text or "", message.timestamp):
        logger.info(f"[WEBHOOK] Duplicate message from {phone}, skipping")
        return {"status": "duplicate"}

    logger.info(f"[WEBHOOK] Message from {phone}: {message.text}")

    store_id, store = await _resolve_store_id(message.session)
    if store_id is None:
        logger.warning("[WEBHOOK] No active store found for session, skipping")
        return {"status": "no_store"}

    text = message.text or ""
    image_bytes = None

    if message.hasMedia and message.mediaUrl:
        logger.info(f"[WEBHOOK] Media detected from {phone}, downloading...")
        async with httpx.AsyncClient() as client:
            resp = await client.get(message.mediaUrl)
            image_bytes = resp.content

    if text or image_bytes:
        text = text or "RECEIPT"
        result = await process_message(
            phone=phone,
            message=text,
            store_id=store_id,
            image_bytes=image_bytes,
        )

        if result.get("response"):
            try:
                if store and store.openwa_session_name and store.chatbot_enabled:
                    wa = OpenWAService(store.openwa_session_name)
                    await wa.send_text(phone, result["response"])
                    logger.info(f"[WEBHOOK] Sent reply to {phone}")
                else:
                    logger.warning(f"[WEBHOOK] Store has no WhatsApp session configured, skipping reply")
            except Exception as e:
                logger.error(f"[WEBHOOK] Failed to send reply: {e}")

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
