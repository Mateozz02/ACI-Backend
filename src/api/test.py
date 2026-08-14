from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.services.agent import process_message
from src.api.deps import get_current_user

router = APIRouter(prefix="/api/test", tags=["test"])


class TestChatRequest(BaseModel):
    message: str
    store_id: UUID
    phone: str | None = None


@router.post("/chat")
async def test_chat(
    data: TestChatRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await process_message(
        phone=data.phone or f"test-{user_id[:8]}",
        message=data.message,
        store_id=data.store_id,
    )
    return {
        "intent": result.get("intent"),
        "response": result.get("response"),
        "parsed_items": result.get("parsed_items"),
        "total": result.get("total"),
    }


@router.post("/receipt")
async def test_receipt(
    file: UploadFile = File(...),
    store_id: UUID = Form(...),
    user_id: str = Depends(get_current_user),
):
    contents = await file.read()
    result = await process_message(
        phone=f"test-{user_id[:8]}",
        message="RECEIPT",
        store_id=store_id,
        image_bytes=contents,
    )
    return {
        "intent": result.get("intent"),
        "response": result.get("response"),
        "parsed_items": result.get("parsed_items"),
        "total": result.get("total"),
    }
