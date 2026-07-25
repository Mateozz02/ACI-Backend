from uuid import UUID
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.models import Order, OrderStatus, Store


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, store_id: UUID, customer_phone: str,
                     user_id: UUID | None = None,
                     customer_name: str | None = None,
                     raw_message: str | None = None,
                     conversation_id: str | None = None) -> Order:
        if user_id is not None:
            result = await self.db.execute(
                select(Store).where(Store.id == store_id, Store.user_id == user_id)
            )
            if not result.scalar_one_or_none():
                raise ValueError("Store not found")

        order = Order(
            store_id=store_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            raw_message=raw_message,
            conversation_id=conversation_id,
        )
        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def get_by_id(self, order_id: UUID, user_id: UUID | None = None) -> Order | None:
        query = select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
        if user_id is not None:
            query = query.join(Store).where(Store.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_store(self, store_id: UUID, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[Order]:
        query = (
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.store_id == store_id)
        )
        if user_id is not None:
            query = query.join(Store).where(Store.user_id == user_id)
        query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_phone(self, phone: str, user_id: UUID | None = None, store_id: UUID | None = None,
                            skip: int = 0, limit: int = 50) -> list[Order]:
        query = select(Order).options(selectinload(Order.items)).where(
            Order.customer_phone == phone
        )
        if user_id is not None:
            query = query.join(Store).where(Store.user_id == user_id)
        if store_id:
            query = query.where(Order.store_id == store_id)
        query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, order_id: UUID, user_id: UUID | None = None, **kwargs) -> Order | None:
        order = await self.get_by_id(order_id, user_id=user_id)
        if not order:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(order, key, value)
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def upload_receipt(self, order_id: UUID, file_bytes: bytes, user_id: UUID | None = None) -> Order | None:
        order = await self.get_by_id(order_id, user_id=user_id)
        if not order:
            return None

        result = await self.db.execute(select(Store).where(Store.id == order.store_id))
        store = result.scalar_one_or_none()
        slug = store.slug if store else "unknown"

        folder = f"data/receipts/{slug}"
        os.makedirs(folder, exist_ok=True)

        path = f"{folder}/{order_id}.jpg"
        with open(path, "wb") as f:
            f.write(file_bytes)

        order.status = OrderStatus.PAYMENT_RECEIVED
        await self.db.commit()
        await self.db.refresh(order)
        return order