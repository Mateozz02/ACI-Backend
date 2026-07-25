from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Product, Store


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, store_id: UUID, unit: str, price: float,
                     user_id: UUID | None = None,
                     description: str | None = None, category: str | None = None,
                     is_available: bool = True) -> Product:
        query = select(Store).where(Store.id == store_id)
        if user_id is not None:
            query = query.where(Store.user_id == user_id)
        result = await self.db.execute(query)
        if not result.scalar_one_or_none():
            raise ValueError("Store not found")

        product = Product(
            name=name,
            store_id=store_id,
            unit=unit,
            price=price,
            description=description,
            category=category,
            is_available=is_available,
        )
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def get_by_id(self, product_id: UUID, user_id: UUID | None = None) -> Product | None:
        query = select(Product).where(Product.id == product_id)
        if user_id is not None:
            query = query.join(Store).where(Store.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_by_store(self, store_id: UUID, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[Product]:
        query = select(Product).where(Product.store_id == store_id)
        if user_id is not None:
            query = query.join(Store).where(Store.user_id == user_id)
        result = await self.db.execute(query.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def update(self, product_id: UUID, user_id: UUID | None = None, **kwargs) -> Product | None:
        product = await self.get_by_id(product_id, user_id=user_id)
        if not product:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        return product
