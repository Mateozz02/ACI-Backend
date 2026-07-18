from datetime import datetime
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


from src.schemas.schemas import ParsedOrder
from src.agents.state import OrderState, Intent
from src.agents.llm import get_llm
from src.agents.prompts import INTENT_PROMPT, ORDER_PARSE_PROMPT, RESPONSE_PROMPT
from src.services.embeddings import get_store_context, search_similar_products

from sqlalchemy import select
from src.models.models import Order, OrderStatus, Product
from src.database import async_session_maker



def detect_intent(state: OrderState) -> OrderState:
    """Detect customer intent using LLM"""
    llm = get_llm(temperature=0)
    messages = INTENT_PROMPT.format_messages(message=state["message"])
    response = llm.invoke(messages)
    intent_str = response.content.strip().lower()

    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.UNKNOWN

    return {**state, "intent": intent}


async def parse_order(state: OrderState) -> OrderState:
    """Parse order items from message"""
    if state["intent"] != Intent.ORDER:
        return {**state, "parsed_items": None, "total": None}

    llm = get_llm(temperature=0)

    try:
        messages = ORDER_PARSE_PROMPT.format_messages(message=state["message"])
        response = llm.invoke(messages)
        content = _clean_json(response.content)
        parsed = ParsedOrder.model_validate_json(content)
        items = [item.model_dump() for item in parsed.items]

        has_ambiguous = any(item.get("ambiguous") for item in items)

        total = 0
        for item in items:
            producto = item.get("producto", "")
            store_id_str = str(state["store_id"]) if state.get("store_id") else None
            if store_id_str:
                results = await search_similar_products(producto,store_id_str,limit=1)
                if results:
                    item["price"] = results[0]["price"]
                    total += item.get("cantidad",0) * results[0]["price"]

        return {
            **state,
            "parsed_items": items,
            "total": total,
            "has_ambiguous": has_ambiguous,
        }
    except Exception as e:
        print(f"[parse_order] Error: {e}")
        return {**state, "parsed_items": None, "total": None, "has_ambiguous": None}


def _clean_json(text: str) -> str:
    """Strip markdown fences from LLM output to extract raw JSON."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1]
    if "```" in text:
        text = text.split("```", 1)[0]
    return text.strip()



async def generate_response(state: OrderState) -> OrderState:
    """Generate AI response based on intent"""
    llm = get_llm(temperature=0.8)

    history = state.get("conversation_history", [])
    history_messages = []
    for msg in history[-5:]:
        history_messages.append(HumanMessage(content=msg.get("user", "")))

    store_context = ""
    store_id = state.get("store_id")
    if store_id:
        store_context = await get_store_context(str(store_id))

    messages = RESPONSE_PROMPT.format_messages(
        message=state["message"],
        intent=state["intent"].value,
        history=history_messages,
        store_context = store_context
    )

    response = llm.invoke(messages)
    history = state.get("conversation_history", [])
    history.append({"user":state["message"],"assistant": response.content})
    return {**state, "response": response.content,"conversation_history":history[-10:]}


def route_intent(state: OrderState) -> Literal[
    "parse_order", "generate_response", "check_order_status",
    "cancel_order", "payment_info", "show_catalog",
]:
    if state["intent"] == Intent.ORDER:
        return "parse_order"
    elif state["intent"] == Intent.ORDER_STATUS:
        return "check_order_status"
    elif state["intent"] == Intent.CANCEL:
        return "cancel_order"
    elif state["intent"] == Intent.PAYMENT:
        return "payment_info"
    elif state["intent"] == Intent.CATALOG:
        return "show_catalog"
    return "generate_response"

async def check_order_status(state:OrderState) -> OrderState:
    phone = state["phone"]
    store_id = state.get("store_id")
    if not store_id:
        return {**state, "response": "No tengo tienda asignada para consultar tu pedido."}

    async with async_session_maker() as session:
        result = await session.execute(
            select(Order)
            .where(Order.customer_phone == phone,Order.store_id == store_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        order = result.scalar_one_or_none()
    if not order:
        return {**state, "response": "No encontré ningun pedido con tu numero."}

    return {**state, "response": f"Tu pedido #{order.id} esta *{order.status.value.upper()}*."} 


async def cancel_order(state: OrderState) -> OrderState:
    phone = state["phone"]
    store_id = state.get("store_id")
    if not store_id:
        return {**state, "response": "No tengo tienda asignada."}

    async with async_session_maker() as session:
        result = await session.execute(
            select(Order)
            .where(Order.customer_phone == phone, Order.store_id == store_id,
                   Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.COMPLETED]))
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        order = result.scalar_one_or_none()
        if not order:
            return {**state, "response": "No tenes pedidos activos para cancelar."}
        order.status = OrderStatus.CANCELLED
        await session.commit()
    return {**state, "response": f"Pedido #{order.id} cancelado."}


async def payment_info(state: OrderState) -> OrderState:
    store_id = state.get("store_id")
    if not store_id:
        return {**state, "response": "No tengo tienda asignada."}
    ctx = await get_store_context(str(store_id))
    if not ctx:
        return {**state, "response": "No hay instrucciones de pago configuradas para esta tienda."}
    return {**state, "response": f"Para pagar:\n\n{ctx}"}


async def show_catalog(state: OrderState) -> OrderState:
    store_id = state.get("store_id")
    if not store_id:
        return {**state, "response": "No tengo tienda asignada."}
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product).where(Product.store_id == store_id, Product.is_available == True)
        )
        products = result.scalars().all()
    if not products:
        return {**state, "response": "No hay productos disponibles en este momento."}
    lines = [f"- {p.name}: ${p.price}/{p.unit}" for p in products]
    return {**state, "response": "Catalogo disponible:\n\n" + "\n".join(lines)}


def build_order_graph():
    """Build the LangGraph for order processing"""
    graph = StateGraph(OrderState)

    graph.add_node("detect_intent", detect_intent)
    graph.add_node("parse_order", parse_order)
    graph.add_node("generate_response", generate_response)
    graph.add_node("check_order_status", check_order_status)
    graph.add_node("cancel_order", cancel_order)
    graph.add_node("payment_info", payment_info)
    graph.add_node("show_catalog", show_catalog)

    graph.set_entry_point("detect_intent")

    graph.add_conditional_edges(
        "detect_intent",
        route_intent,
        {
            "parse_order": "parse_order",
            "generate_response": "generate_response",
            "check_order_status": "check_order_status",
            "cancel_order": "cancel_order",
            "payment_info": "payment_info",
            "show_catalog": "show_catalog",
        },
    )

    graph.add_edge("parse_order", "generate_response")
    graph.add_edge("check_order_status", "generate_response")
    graph.add_edge("cancel_order", "generate_response")
    graph.add_edge("payment_info", "generate_response")
    graph.add_edge("show_catalog", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile(checkpointer=MemorySaver())


order_agent = build_order_graph()
