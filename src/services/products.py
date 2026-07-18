from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Product, Store


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, store_id: UUID, unit: str, price: float,
                     description: str | None = None, category: str | None = None,
                     is_available: bool = True) -> Product:
        result = await self.db.execute(select(Store).where(Store.id == store_id))
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

    async def get_by_id(self, product_id: UUID) -> Product | None:
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        return result.scalar_one_or_none()

    async def list_by_store(self, store_id: UUID, skip: int = 0, limit: int = 100) -> list[Product]:
        result = await self.db.execute(
            select(Product)
            .where(Product.store_id == store_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, product_id: UUID, **kwargs) -> Product | None:
        product = await self.get_by_id(product_id)
        if not product:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        return product
