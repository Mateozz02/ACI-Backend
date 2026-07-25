from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Store


class StoreService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, phone: str, user_id,
                     address: str | None = None, description: str | None = None,
                     greeting_message: str | None = None,
                     payment_instructions: str | None = None,
                     cancellation_policy: str | None = None) -> Store:
        store = Store(
            name=name,
            phone=phone,
            user_id=user_id,
            address=address,
            description=description,
            greeting_message=greeting_message,
            payment_instructions=payment_instructions,
            cancellation_policy=cancellation_policy,
        )
        self.db.add(store)
        await self.db.commit()
        await self.db.refresh(store)
        return store

    async def get_by_id(self, store_id: UUID, user_id: UUID | None = None) -> Store | None:
        query = select(Store).where(Store.id == store_id)
        if user_id is not None:
            query = query.where(Store.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str, user_id: UUID | None = None) -> Store | None:
        query = select(Store).where(Store.slug == slug)
        if user_id is not None:
            query = query.where(Store.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(self, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[Store]:
        query = select(Store)
        if user_id is not None:
            query = query.where(Store.user_id == user_id)
        result = await self.db.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(self, store_id: UUID, user_id: UUID | None = None, **kwargs) -> Store | None:
        store = await self.get_by_id(store_id, user_id=user_id)
        if not store:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(store, key, value)
        await self.db.commit()
        await self.db.refresh(store)
        return store
