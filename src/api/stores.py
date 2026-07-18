from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.schemas import StoreCreate, StoreUpdate, StoreResponse
from src.services.stores import StoreService

router = APIRouter(tags=["stores"])


@router.post("/", response_model=StoreResponse)
async def create_store(
    store: StoreCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = StoreService(db)
    return await svc.create(**store.model_dump())


@router.get("/by-slug/{slug}", response_model=StoreResponse)
async def get_store_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    svc = StoreService(db)
    store = await svc.get_by_slug(slug)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = StoreService(db)
    store = await svc.get_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/", response_model=list[StoreResponse])
async def list_stores(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    svc = StoreService(db)
    return await svc.list_all(skip=skip, limit=limit)


@router.patch("/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: UUID,
    store_update: StoreUpdate,
    db: AsyncSession = Depends(get_db),
):
    svc = StoreService(db)
    store = await svc.update(store_id, **store_update.model_dump(exclude_unset=True))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store
