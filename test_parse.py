import asyncio
from src.agents.order_agent import parse_order
from src.agents.state import OrderState, Intent

state: OrderState = {
    "phone": "573001234567",
    "store_id": None,
    "message": "Quiero 2kg de carne molida y 1 paquete de salchichas",
    "intent": Intent.ORDER,
    "order_id": None,
    "parsed_items": None,
    "total": None,
    "has_ambiguous": None,
    "response": None,
    "conversation_history": [],
    "timestamp": None,  # o puede ir datetime.now()
}

result = asyncio.run(parse_order(state))
print("Items:", result.get("parsed_items"))
print("Total:", result.get("total"))
print("Ambiguous:", result.get("has_ambiguous"))