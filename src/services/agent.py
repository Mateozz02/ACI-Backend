from datetime import datetime
from uuid import UUID

from src.agents.order_agent import order_agent
from src.agents.state import OrderState


async def process_message(
    phone: str,
    message: str,
    store_id: UUID | None = None,
    conversation_history: list[dict] | None = None,
    image_bytes: bytes | None = None,
) -> dict:
    """Process a WhatsApp message through the order agent"""

    initial_state: OrderState = {
        "phone": phone,
        "store_id": store_id,
        "message": message,
        "timestamp": datetime.now(),
        "image_bytes": image_bytes,
    }
    thread_id = f"{store_id or 'default'}:{phone}"
    config = {"configurable": {'thread_id': thread_id}}
    final_state = await order_agent.ainvoke(initial_state,config=config)

    return {
        "intent": final_state["intent"].value,
        "response": final_state["response"],
        "parsed_items": final_state.get("parsed_items"),
        "total": final_state.get("total"),
    }
