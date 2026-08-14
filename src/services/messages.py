from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Message


async def save_message(
    db: AsyncSession,
    store_id: UUID,
    customer_phone: str,
    role: str,
    content: str | None = None,
    image_url: str | None = None,
    intent: str | None = None,
    order_id: UUID | None = None,
) -> Message:
    """Persist a chat message."""
    msg = Message(
        id=uuid4(),
        store_id=store_id,
        customer_phone=customer_phone,
        role=role,
        content=content,
        image_url=image_url,
        intent=intent,
        order_id=order_id,
    )
    db.add(msg)
    await db.flush()
    return msg


async def get_conversations(db: AsyncSession, store_id: UUID) -> list[dict]:
    """List all conversations for a store, grouped by phone with last message."""
    subq = (
        select(
            Message.customer_phone,
            func.max(Message.created_at).label("last_msg_at"),
            func.count(Message.id).label("msg_count"),
        )
        .where(Message.store_id == store_id)
        .group_by(Message.customer_phone)
        .subquery()
    )

    result = await db.execute(
        select(
            Message.customer_phone,
            Message.content,
            Message.role,
            Message.created_at,
            subq.c.msg_count,
        )
        .join(subq, (Message.customer_phone == subq.c.customer_phone)
              & (Message.created_at == subq.c.last_msg_at))
        .where(Message.store_id == store_id)
        .order_by(desc(subq.c.last_msg_at))
    )
    return [
        {
            "phone": row.customer_phone,
            "last_message": row.content,
            "last_role": row.role,
            "last_at": row.created_at.isoformat(),
            "message_count": row.msg_count,
        }
        for row in result.fetchall()
    ]


async def get_conversation(db: AsyncSession, store_id: UUID, phone: str) -> list[dict]:
    """Get the full message thread for a customer."""
    result = await db.execute(
        select(Message)
        .where(Message.store_id == store_id, Message.customer_phone == phone)
        .order_by(Message.created_at)
    )
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "image_url": m.image_url,
            "intent": m.intent,
            "order_id": str(m.order_id) if m.order_id else None,
            "created_at": m.created_at.isoformat(),
        }
        for m in result.scalars()
    ]
