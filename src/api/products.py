from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.schemas import ProductCreate, ProductUpdate, ProductResponse
from src.services.products import ProductService
from src.api.deps import get_current_user

router = APIRouter(tags=["products"])


@router.post("/", response_model=ProductResponse)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = ProductService(db)
    try:
        return await svc.create(user_id=UUID(user_id), **product.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = ProductService(db)
    product = await svc.get_by_id(product_id, user_id=UUID(user_id))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/store/{store_id}", response_model=list[ProductResponse])
async def list_products_by_store(
    store_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = ProductService(db)
    return await svc.list_by_store(store_id, user_id=UUID(user_id), skip=skip, limit=limit)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product_update: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = ProductService(db)
    product = await svc.update(product_id, user_id=UUID(user_id), **product_update.model_dump(exclude_unset=True))
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
