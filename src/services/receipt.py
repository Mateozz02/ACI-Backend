import base64
import json
import os
from datetime import datetime
from uuid import UUID

import aiofiles

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.models import Order, OrderStatus, Store
from src.agents.llm import get_vision_llm
from src.agents.prompts import RECEIPT_VERIFY_PROMPT
from src.utils import clean_llm_json, logger


class ReceiptService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_image(self, store_id: UUID, order: Order, image_bytes: bytes) -> str:
        result = await self.db.execute(select(Store).where(Store.id == store_id))
        store = result.scalar_one_or_none()
        slug = store.slug if store else "unknown"
        folder = f"data/receipts/{slug}"
        os.makedirs(folder, exist_ok=True)
        path = f"{folder}/{order.id}.jpg"
        async with aiofiles.open(path, "wb") as f:
            await f.write(image_bytes)
        return path

    async def analyze(self, image_bytes: bytes) -> dict:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        vision_llm = get_vision_llm(temperature=0.2)
        from langchain_core.messages import HumanMessage
        msg = HumanMessage(content=[
            {"type": "text", "text": RECEIPT_VERIFY_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ])
        response = vision_llm.invoke([msg])
        content = response.content
        if isinstance(content, list):
            content = content[0]
        if isinstance(content, dict):
            content = content.get("text", "")
        content = clean_llm_json(content)
        logger.info(f"[verify_receipt] Gemini raw: {content}")
        return json.loads(content)

    async def verify(self, order: Order, extracted: dict) -> str:
        amount = extracted.get("amount")
        ref = extracted.get("reference")
        date = extracted.get("date")
        confidence = extracted.get("confidence", 0)

        if amount is not None and confidence >= 0.2 and abs(amount - float(order.total_amount or 0)) < 0.01:
            order.status = OrderStatus.VERIFIED
            order.payment_reference = str(ref) if ref else None
            if date:
                order.payment_date = datetime.fromisoformat(date)
            await self.db.commit()
            return f"Pago verificado! Tu pedido #{order.id} por ${amount:.2f} está en proceso."

        order.status = OrderStatus.PAYMENT_RECEIVED
        await self.db.commit()
        return "Recibí tu comprobante. Lo voy a revisar y te confirmo."
