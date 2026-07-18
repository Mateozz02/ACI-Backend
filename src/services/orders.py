from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.models import Order


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, store_id: UUID, customer_phone: str,
                     customer_name: str | None = None,
                     raw_message: str | None = None,
                     conversation_id: str | None = None) -> Order:
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

    async def get_by_id(self, order_id: UUID) -> Order | None:
        result = await self.db.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def list_by_store(self, store_id: UUID, skip: int = 0, limit: int = 100) -> list[Order]:
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.store_id == store_id)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_phone(self, phone: str, store_id: UUID | None = None,
                            skip: int = 0, limit: int = 50) -> list[Order]:
        query = select(Order).options(selectinload(Order.items)).where(
            Order.customer_phone == phone
        )
        if store_id:
            query = query.where(Order.store_id == store_id)
        query = query.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, order_id: UUID, **kwargs) -> Order | None:
        order = await self.get_by_id(order_id)
        if not order:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(order, key, value)
        await self.db.commit()
        await self.db.refresh(order)
        return order
