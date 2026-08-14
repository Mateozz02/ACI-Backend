from datetime import datetime, timedelta
from uuid import UUID
import asyncio

from src.agents.order_agent import order_agent
from src.agents.state import OrderState
from src.database import async_session_maker
from src.services.messages import save_message, get_conversation

# Limit concurrent LLM calls to avoid rate-limiting
_llm_semaphore = asyncio.Semaphore(5)


async def _load_history(store_id: UUID, phone: str) -> str:
    """Load recent conversation history as plain text."""
    try:
        async with async_session_maker() as db:
            msgs = await get_conversation(db, store_id, phone)
        if not msgs:
            return "(sin historial previo)"
        # Filter: today + yesterday if needed
        cutoff = datetime.utcnow() - timedelta(days=2)
        recent = [m for m in msgs if datetime.fromisoformat(m["created_at"]) > cutoff]
        # Last 10 messages max
        recent = recent[-10:]
        lines = []
        for m in recent:
            role = "Cliente" if m["role"] == "user" else "Bot"
            content = (m["content"] or "[imagen]")[:200]
            lines.append(f"{role}: {content}")
        return "\n".join(lines) if lines else "(sin historial previo)"
    except Exception:
        return "(sin historial previo)"


async def process_message(
    phone: str,
    message: str,
    store_id: UUID | None = None,
    conversation_history: list[dict] | None = None,
    image_bytes: bytes | None = None,
) -> dict:
    """Process a WhatsApp message through the order agent"""
    # GUARDAR: mensaje entrante del usuario
    if store_id:
        async with async_session_maker() as db:
            await save_message(
                db, store_id, phone, role="user",
                content=message if not image_bytes else "[imagen]",
            )
            await db.commit()

    # Cargar historial como texto plano
    history_text = "(sin historial previo)"
    if store_id:
        history_text = await _load_history(store_id, phone)

    initial_state: OrderState = {
        "phone": phone,
        "store_id": store_id,
        "message": message,
        "timestamp": datetime.now(),
        "image_bytes": image_bytes,
        "conversation_history": history_text,  # type: ignore
    }
    thread_id = f"{store_id or 'default'}:{phone}"
    config = {"configurable": {'thread_id': thread_id}}

    async with _llm_semaphore:
        final_state = await order_agent.ainvoke(initial_state, config=config)

    # GUARDAR: respuesta del bot
    response = final_state["response"]
    if store_id and response:
        async with async_session_maker() as db:
            await save_message(
                db, store_id, phone, role="assistant",
                content=str(response),
                intent=final_state["intent"].value,
                order_id=final_state.get("order_id"),
            )
            await db.commit()

    return {
        "intent": final_state["intent"].value,
        "response": response,
        "parsed_items": final_state.get("parsed_items"),
        "total": final_state.get("total"),
    }
