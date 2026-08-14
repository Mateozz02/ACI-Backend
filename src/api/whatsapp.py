from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.models import Store
from src.services.openwa import OpenWAService
from src.api.deps import get_current_user

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


async def _get_owned_store(store_id: UUID, user_id: str, db: AsyncSession) -> Store:
    store = await db.get(Store, store_id)
    if not store or str(store.user_id) != user_id:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


def _require_session(store: Store, field: str):
    if not getattr(store, field):
        raise HTTPException(status_code=400, detail="Store has no WhatsApp session configured")


@router.post("/{store_id}/create-session")
async def create_session(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    store = await _get_owned_store(store_id, user_id, db)

    if store.openwa_session_name:
        raise HTTPException(status_code=400, detail="Store already has a WhatsApp session")

    wa = OpenWAService()
    try:
        session = await wa.create_session(name=store.slug)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenWA error: {e}")

    store.openwa_session_name = session["name"]
    store.openwa_session_id = session["id"]
    await db.commit()

    return {
        "store_id": str(store_id),
        "session_name": session["name"],
        "session_id": session["id"],
        "status": session["status"],
    }


@router.post("/{store_id}/start")
async def start_session(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    store = await _get_owned_store(store_id, user_id, db)
    _require_session(store, "openwa_session_id")

    wa = OpenWAService()
    try:
        session = await wa.start_session(store.openwa_session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenWA error: {e}")

    return {
        "store_id": str(store_id),
        "status": session["status"],
        "phone": session.get("phone"),
        "connected_at": session.get("connectedAt"),
    }


@router.get("/{store_id}/qr")
async def get_qr(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    store = await _get_owned_store(store_id, user_id, db)
    _require_session(store, "openwa_session_id")

    wa = OpenWAService()
    for attempt in range(10):
        try:
            qr = await wa.get_session_qr(store.openwa_session_id)
            if qr.get("qrCode"):
                break
        except Exception:
            # 400 may mean QR not ready yet OR session already authenticated
            if attempt == 0:
                # Check if already connected — no QR needed
                try:
                    s = await wa.get_session_status(store.openwa_session_id)
                    if s.get("status") == "ready":
                        return {
                            "store_id": str(store_id),
                            "qr_code": None,
                            "status": "ready",
                            "phone": s.get("phone"),
                        }
                except Exception:
                    pass
            if attempt == 9:
                raise HTTPException(status_code=502, detail="QR code not available after multiple retries")
        await asyncio.sleep(1.5)

    return {
        "store_id": str(store_id),
        "qr_code": qr.get("qrCode"),
        "status": qr.get("status"),
    }


@router.get("/{store_id}/status")
async def get_status(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    store = await _get_owned_store(store_id, user_id, db)
    _require_session(store, "openwa_session_id")

    wa = OpenWAService()
    try:
        session = await wa.get_session_status(store.openwa_session_id)
    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower():
            store.openwa_session_name = None
            store.openwa_session_id = None
            await db.commit()
            return {
                "store_id": str(store_id),
                "status": "deleted",
            }
        raise HTTPException(status_code=502, detail=f"OpenWA error: {e}")

    return {
        "store_id": str(store_id),
        "status": session["status"],
        "phone": session.get("phone"),
        "push_name": session.get("pushName"),
        "connected_at": session.get("connectedAt"),
        "last_active": session.get("lastActive"),
    }


@router.delete("/{store_id}/session")
async def delete_session(
    store_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    store = await _get_owned_store(store_id, user_id, db)
    _require_session(store, "openwa_session_id")

    wa = OpenWAService()
    try:
        await wa.delete_session(store.openwa_session_id)
    except Exception:
        pass

    store.openwa_session_name = None
    store.openwa_session_id = None
    await db.commit()

    return {"store_id": str(store_id), "status": "deleted"}
