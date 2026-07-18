from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Store


class StoreService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, phone: str,
                     address: str | None = None, description: str | None = None,
                     greeting_message: str | None = None,
                     payment_instructions: str | None = None,
                     cancellation_policy: str | None = None) -> Store:
        store = Store(
            name=name,
            phone=phone,
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

    async def get_by_id(self, store_id: UUID) -> Store | None:
        result = await self.db.execute(select(Store).where(Store.id == store_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Store | None:
        result = await self.db.execute(select(Store).where(Store.slug == slug))
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[Store]:
        result = await self.db.execute(select(Store).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(self, store_id: UUID, **kwargs) -> Store | None:
        store = await self.get_by_id(store_id)
        if not store:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(store, key, value)
        await self.db.commit()
        await self.db.refresh(store)
        return store
