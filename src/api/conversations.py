from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.api.deps import get_current_user
from src.services.messages import get_conversations, get_conversation
from src.services.openwa import OpenWAService
from src.models.models import Store

router = APIRouter(prefix="/api/stores/{store_id}/conversations", tags=["conversations"])


async def _get_owned_store(store_id: UUID, user_id: str, db: AsyncSession) -> Store:
    store = await db.get(Store, store_id)
    if not store or str(store.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("")
async def list_conversations(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """List all customer conversations for a store."""
    await _get_owned_store(store_id, user_id, db)
    return await get_conversations(db, store_id)


@router.get("/{phone:path}")
async def read_conversation(
    store_id: UUID,
    phone: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Get full message thread with a customer."""
    await _get_owned_store(store_id, user_id, db)
    return await get_conversation(db, store_id, phone)


class SendMessageRequest(BaseModel):
    content: str
    image_url: str | None = None


@router.post("/{phone:path}/send")
async def send_to_customer(
    store_id: UUID,
    phone: str,
    data: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    """Send a message from the store to the customer via WhatsApp."""
    store = await _get_owned_store(store_id, user_id, db)

    if not store.openwa_session_name:
        raise HTTPException(status_code=400, detail="Store has no WhatsApp session")

    wa = OpenWAService(store.openwa_session_id)

    if data.image_url:
        await wa.send_image(phone, data.image_url, caption=data.content or None)
    elif data.content:
        await wa.send_text(phone, data.content)

    # Save as store message
    from src.services.messages import save_message
    await save_message(db, store_id, phone, role="store", content=data.content, image_url=data.image_url)
    await db.commit()

    return {"status": "sent"}
