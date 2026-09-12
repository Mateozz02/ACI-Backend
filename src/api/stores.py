from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.models import User, Store
from src.schemas.schemas import StoreCreate, StoreUpdate, StoreResponse
from src.services.stores import StoreService
from src.api.deps import get_current_user

router = APIRouter(tags=["stores"])

TIER_LIMITS = {
    "free": 1,
    "pro": 3,
    "enterprise": None,
}

CHATBOT_TIERS = {"pro", "enterprise"}

async def _check_store_limit(db: AsyncSession, user_id: UUID) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    limit = TIER_LIMITS.get(user.tier)
    if limit is None:
        return

    count = await db.execute(
        select(func.count()).select_from(Store).where(Store.user_id == user_id)
    )
    current = count.scalar()

    if current >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Tu plan {user.tier} solo permite {limit} tienda(s). Actualizá tu plan para crear más.",
        )


@router.post("/", response_model=StoreResponse)
async def create_store(
    store: StoreCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    await _check_store_limit(db, UUID(user_id))
    svc = StoreService(db)
    data = store.model_dump(exclude={"slug"})
    data["user_id"] = user_id
    return await svc.create(**data)


@router.get("/by-slug/{slug}", response_model=StoreResponse)
async def get_store_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = StoreService(db)
    store = await svc.get_by_slug(slug, user_id=UUID(user_id))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = StoreService(db)
    store = await svc.get_by_id(store_id, user_id=UUID(user_id))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/", response_model=list[StoreResponse])
async def list_stores(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    svc = StoreService(db)
    return await svc.list_all(user_id=UUID(user_id), skip=skip, limit=limit)


@router.patch("/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: UUID,
    store_update: StoreUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if store_update.chatbot_enabled is True:
        user = await db.get(User, UUID(user_id))
        if not user or user.tier not in CHATBOT_TIERS:
            raise HTTPException(
                status_code=403,
                detail="Necesitás plan pro o superior para activar el chatbot automático.",
            )

    svc = StoreService(db)
    store = await svc.update(store_id, user_id=UUID(user_id), **store_update.model_dump(exclude_unset=True))
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store
