from fastapi import APIRouter, HTTPException,UploadFile,File, Depends
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.schemas import OrderCreate, OrderUpdate, OrderResponse, OrderDetailResponse
from src.services.orders import OrderService


router = APIRouter(tags=["orders"])


@router.post("/", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    svc = OrderService(db)
    return await svc.create(**order.model_dump())


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = OrderService(db)
    order = await svc.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/store/{store_id}", response_model=list[OrderDetailResponse])
async def list_orders_by_store(
    store_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    svc = OrderService(db)
    return await svc.list_by_store(store_id, skip=skip, limit=limit)


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: UUID,
    order_update: OrderUpdate,
    db: AsyncSession = Depends(get_db),
):
    svc = OrderService(db)
    order = await svc.update(order_id, **order_update.model_dump(exclude_unset=True))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/phone/{phone}", response_model=list[OrderDetailResponse])
async def get_orders_by_phone(
    phone: str,
    store_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    svc = OrderService(db)
    return await svc.list_by_phone(phone, store_id=store_id, skip=skip, limit=limit)

@router.post("/{order_id}/receipt")
async def upload_receipt(
    order_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    svc = OrderService(db)
    contents = await file.read()
    order = await svc.upload_receipt(order_id, contents)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "ok", "order_id": str(order_id), "new_status": order.status.value}
