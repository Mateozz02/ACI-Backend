from typing import Literal
from uuid import uuid4
import re

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.schemas.schemas import ParsedOrder, IntentResponse, OrchestratorDecision
from src.agents.state import OrderState, Intent
from src.agents.llm import get_structured_llm
from src.agents.prompts import INTENT_PROMPT, ORDER_PARSE_PROMPT, ORDER_PARSE_WITH_CONTEXT_PROMPT, ORCHESTRATOR_PROMPT
from src.services.embeddings import search_product_by_name, search_similar_products
from src.services.receipt import ReceiptService
from src.utils import logger
from src.config import get_settings

from sqlalchemy import select
from src.models.models import Order, OrderItem, OrderStatus, Product, Store
from src.database import async_session_maker
import random

settings = get_settings()

# ---------------------------------------------------------------------------
# Human response templates — randomly selected for variety
# ---------------------------------------------------------------------------

_HUMAN_TEMPLATES = {
    "order_confirm": [
        "Perfecto, tu pedido:\n\n{items}\n\n*Total: ${total}*\n\n¿Confirmás?",
        "Dale, te anoto:\n\n{items}\n\nTotal: ${total}. ¿Le damos para adelante?",
        "Así queda tu pedido:\n\n{items}\n\n*Total: ${total}*\n\n¿Está bien?",
        "Listo, esto sería:\n\n{items}\n\nTotal: ${total}. ¿Confirmamos?",
    ],
    "order_added": [
        "Ahí te lo agregué. Tu pedido ahora:\n\n{items}\n\n*Total: ${total}*\n\n¿Algo más?",
        "Listo, actualizado:\n\n{items}\n\nTotal: ${total}. ¿Seguimos?",
        "Dale, quedó así:\n\n{items}\n\n*Total: ${total}*\n\n¿Confirmás o falta algo?",
    ],
    "order_confirmed": [
        "¡Listo! Pedido confirmado. Te aviso cuando esté listo.",
        "Perfecto, ya está confirmado. Te mando mensaje cuando lo tengas que retirar.",
        "Dale, confirmado. Cualquier cosa me avisás.",
    ],
    "product_not_found": [
        "No encontré {product}. ¿Querés que te muestre lo que hay disponible?",
        "No tenemos {product} por ahora. ¿Te muestro el catálogo?",
        "Eso no lo tenemos, pero capaz te interesa otra cosa. ¿Te paso la lista?",
    ],
    "product_unavailable": [
        "No tenemos {product} en este momento. ¿Querés ver opciones similares?",
        "{product} no está disponible ahora. ¿Te muestro alternativas?",
        "Ese producto no está por ahora. ¿Vemos qué hay?",
    ],
    "greeting": [
        "¡Hola! ¿Qué te gustaría pedir hoy?",
        "¡Buenas! ¿En qué te puedo ayudar?",
        "¡Hola! Contame qué necesitás y te preparo el pedido.",
    ],
    "help": [
        "¿En qué te ayudo? Podés pedirme productos, consultar el catálogo o preguntar por tu pedido.",
        "Contame qué necesitás: puedo tomarte un pedido, mostrarte el catálogo o decirte cómo va tu pedido.",
        "¡Dale! Pedime lo que quieras, consultame el catálogo o preguntame por el estado de tu pedido.",
    ],
    "fallback": [
        "No estoy seguro de qué necesitás. ¿Me lo podrías decir de otra forma?",
        "Disculpá, no entendí bien. ¿Podrías ser más claro?",
        "No estoy seguro de entenderte. ¿Me ayudás con más detalles?",
    ],
}


def _human_response(template_key: str, **kwargs) -> str:
    """Pick a random human-like template and format it."""
    templates = _HUMAN_TEMPLATES.get(template_key)
    if not templates:
        return kwargs.get("fallback", "")
    return random.choice(templates).format(**kwargs)


def _keyword_intent(msg: str) -> Intent | None:
    """Detect intent from keyword patterns. Returns None if not matched."""
    m = msg.lower().strip()

    # ORDER_STATUS — looking up an existing order
    if any(kw in m for kw in ["estado", "status", "cómo va", "como va", "dónde está",
                                "donde esta", "mi pedido", "pedido mío", "cuándo llega",
                                "cuando llega", "demora", "tracking", "seguimiento"]):
        return Intent.ORDER_STATUS

    # CATALOG — only standalone questions, not "tenes X"
    if m in ["catálogo", "catalogo", "productos", "lista de precios"]:
        return Intent.CATALOG
    if m.startswith(("qué tenés", "que tenes", "qué tienen", "que tienen",
                      "qué hay", "que hay", "mostrame", "enseñame",
                      "mostrame los", "enseñame los")):
        return Intent.CATALOG

    # PAYMENT
    if any(kw in m for kw in ["cómo pago", "como pago", "pagar", "pago",
                                "transferencia", "CBU", "alias", "mercado pago",
                                "formas de pago", "método de pago", "metodo de pago",
                                "cuánto sale", "cuanto sale", "precio", "cuánto está",
                                "cuanto esta", "cuánto cuesta", "cuanto cuesta"]):
        return Intent.PAYMENT

    # CANCEL
    if any(kw in m for kw in ["cancelar", "cancelá", "cancela", "anular", "anulá",
                                "anula", "no quiero", "descartar", "borrar pedido"]):
        return Intent.CANCEL
    if m in ["no", "nop", "nel", "nope"]:
        return Intent.CANCEL

    # HELP
    if m in ["ayuda", "help", "ayudame", "no entiendo", "no entendi"]:
        return Intent.HELP

    # GREETING (short standalone messages)
    if m in ["hola", "buenos días", "buenos dias", "buen día", "buen dia",
             "buenas tardes", "buenas noches", "qué tal", "que tal",
             "buenas", "hey", "ola", "holis", "hola!", "holaa"]:
        return Intent.GREETING

    # Simple product name alone (1-2 words) → ORDER
    word_count = len(m.split())
    if word_count <= 2:
        return Intent.ORDER

    # Message with quantity+unit pattern → ORDER (e.g. "2kg de carne molida")
    if re.search(r'\d+\s*(?:kg|kilo|gramo|docena|paquete|unidad|litro|g\b|ml\b|l\b)', m):
        return Intent.ORDER

    # SEND_RECEIPT — when a receipt image is attached (handled by verify_receipt node)
    # No keyword here — the node checks for image_bytes directly

    return None


def detect_intent(state: OrderState) -> OrderState:
    """Detect customer intent — keyword first, LLM fallback."""

    # Phase 1A: try keyword-based detection (free, instant)
    intent = _keyword_intent(state["message"])
    if intent is not None:
        return {**state, "intent": intent}

    # Fallback: structured LLM for complex/ambiguous messages
    llm = get_structured_llm(IntentResponse, temperature=0)
    messages = INTENT_PROMPT.format_messages(message=state["message"])
    result = llm.invoke(messages)

    intent_str = result.intent.strip().lower()
    # Map Spanish intent names that Gemini sometimes returns
    SPANISH_INTENT_MAP = {
        "saludo": "greeting", "saludar": "greeting", "hola": "greeting", "saludar_al_cliente": "greeting",
        "pedido": "order", "orden": "order", "ordenar": "order",
        "realizar_pedido": "order", "hacer_pedido": "order", "solicitar_pedido": "order",
        "solicitud_de_pedido": "order", "nuevo_pedido": "order", "pedir": "order",
        "confirmar": "order", "confirmacion": "order", "confirmación": "order",
        "si": "order", "sí": "order", "dale": "order", "ok": "order",
        "estado": "order_status", "estado_pedido": "order_status", "status": "order_status",
        "consultar_estado": "order_status", "consulta_de_estado": "order_status",
        "cancelar": "cancel", "cancelacion": "cancel", "cancelar_pedido": "cancel",
        "ayuda": "help",
        "catalogo": "catalog", "catálogo": "catalog", "ver_catalogo": "catalog",
        "solicitar_catalogo": "catalog", "ver_productos": "catalog", "consulta_productos": "catalog",
        "pago": "payment", "pagar": "payment", "pagos": "payment",
        "informacion_de_pago": "payment", "metodos_de_pago": "payment",
        "comprobante": "send_receipt", "recibo": "send_receipt", "factura": "send_receipt",
        "enviar_comprobante": "send_receipt",
    }
    intent_str = SPANISH_INTENT_MAP.get(intent_str, intent_str)

    # Partial match fallback for unknown Spanish phrases
    valid_intents = {member.value for member in Intent}
    if intent_str not in valid_intents:
        for keyword, mapped in [
            ("pedido", "order"), ("orden", "order"),
            ("cancel", "cancel"),
            ("estado", "order_status"), ("status", "order_status"),
            ("catalogo", "catalog"), ("catálogo", "catalog"), ("producto", "catalog"),
            ("pago", "payment"), ("pagar", "payment"),
            ("comprobante", "send_receipt"), ("recibo", "send_receipt"), ("factura", "send_receipt"),
            ("saludo", "greeting"), ("hola", "greeting"),
            ("ayuda", "help"),
        ]:
            if keyword in intent_str:
                intent_str = mapped
                break

    try:
        intent = Intent(intent_str)
    except ValueError:
        intent = Intent.UNKNOWN

    return {**state, "intent": intent}


# ---------------------------------------------------------------------------
# Regex order parser — handles simple orders without LLM
# ---------------------------------------------------------------------------

# Confidence threshold: below this score, fall back to LLM
CONFIDENCE_THRESHOLD = 60

_NUMBERS = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "media": 0.5, "medio": 0.5, "mitad": 0.5,
}

# Quantity: digits (2, 1.5), fractions (1/2, 3/4), or spelled numbers
_QTY = r'(?:un[ao]?|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|medi[oa]|mitad|\d+/\d+|\d+(?:[.,]\d+)?)'
_UNITS = r'(?:kg|kilos?|gramos?|g\b|unidad(?:es)?|docena(?:s)?|paquete(?:s)?|litros?|l\b|ml\b|cc\b)'

_ITEM_RE = re.compile(
    r'^'
    r'(' + _QTY + r'\s*)'
    r'(' + _UNITS + r')?\s*'
    r'(?:de\s+)?'
    r'(.+)'
    r'$'
)

# Prefijos: indica si el mensaje modifica o reemplaza el pedido actual
_ADD_PREFIXES = re.compile(r'^(?:agreg[áa]|agregame|sum[áa]|pon[eé]|añ[aá]d[ií]|sumale|agregale|dame|traeme)\s+(?:a\s+)?', re.IGNORECASE)
_CHANGE_PREFIXES = re.compile(r'^(?:cambi[áa]|cambiame|mejor\s+dame|en\s+vez\s+de)\s+(?:a\s+)?', re.IGNORECASE)


def _parse_qty(s: str) -> float | None:
    """Parse a quantity string that may be a fraction, decimal, or spelled number."""
    s = s.strip().replace(',', '.')
    # Fraction like "1/2"
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                return None
    try:
        return float(s)
    except ValueError:
        return _NUMBERS.get(s)


def _regex_parse_order(msg: str) -> tuple[list[dict] | None, bool]:
    """Parse simple order messages via regex.

    Returns (items, is_add) where:
      - items is the list of parsed items or None
      - is_add means the new items should be MERGED into the existing order
    """
    m = msg.strip()
    is_add = False
    is_change = False

    # Detect and strip prefixes
    add_match = _ADD_PREFIXES.match(m)
    if add_match:
        is_add = True
        m = m[add_match.end():]

    change_match = _CHANGE_PREFIXES.match(m)
    if change_match:
        is_change = True
        m = m[change_match.end():]

    m = m.lower().strip()
    m = re.sub(r'\s+y\s+', ' , ', m)
    m = re.sub(r'\s*,\s*', ' , ', m)

    parts = [p.strip().rstrip('.') for p in m.split(' , ') if p.strip()]
    items: list[dict] = []

    for part in parts:
        match = _ITEM_RE.match(part)
        if not match:
            return None, False

        qty_str = match.group(1).strip()
        unit = (match.group(2) or "").strip()
        product = match.group(3).strip().rstrip('.,;')

        if not product:
            return None, False

        qty = _parse_qty(qty_str)
        if qty is None:
            return None, False

        items.append({
            "producto": product,
            "cantidad": qty,
            "unidad": unit,
            "ambiguous": False,
        })

    return (items if items else None), (is_add or is_change)


def _calculate_regex_confidence(msg: str, parsed_items: list[dict] | None) -> int:
    """Evaluate regex parsing confidence (0-100). Below CONFIDENCE_THRESHOLD, fall back to LLM."""
    if not parsed_items:
        return 0
    score = 100
    # Prefijos que sugieren ambigüedad
    for prefix in ["dame", "quiero", "necesito", "traeme", "manda", "poneme"]:
        if msg.lower().startswith(prefix):
            score -= 30
            break
    # Palabras de pregunta vs pedido
    if any(w in msg.lower() for w in ["tenes", "tenés", "hay", "tienen", "queda", "disponible", "precio", "cuanto"]):
        score -= 40
    # Mensaje muy corto
    if len(msg.split()) <= 2:
        score -= 20
    # Conectores complejos
    if any(c in msg.lower() for c in ["y también", "además", "también quiero", "me das"]):
        score -= 25
    # Producto genérico
    for item in parsed_items:
        if item["producto"].lower() in ["algo", "eso", "esto", "lo mismo"]:
            score -= 50
            break
    # Cantidad ambigua
    for item in parsed_items:
        if item["cantidad"] == 0:
            score -= 30
            break
    return max(0, score)


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Orchestrator node — decides regex vs LLM
# ---------------------------------------------------------------------------


async def orchestrate(state: OrderState) -> OrderState:
    """LLM decides: parse with regex, parse with context, or route to other handler."""
    intent = state["intent"]
    if intent != Intent.ORDER:
        return state

    # Confirm/cancel words are always handled by regex
    msg_lower = state["message"].strip().lower()
    if msg_lower in {"sí", "si", "dale", "ok", "confirmo", "confirmar", "de una", "obvio", "claro", "bueno", "bien", "perfecto", "listo", "okey"}:
        return {**state, "orchestrator_decision": "regex"}
    if msg_lower in {"no", "cancelar", "cancelo", "nop", "nel", "nope"}:
        return {**state, "orchestrator_decision": "regex"}

    # Ask LLM to decide
    try:
        llm = get_structured_llm(OrchestratorDecision, temperature=0)
        history = state.get("conversation_history", "(sin historial)")
        messages = ORCHESTRATOR_PROMPT.format_messages(
            message=state["message"],
            history=str(history)[:800],
        )
        result = llm.invoke(messages)
        return {**state, "orchestrator_decision": result.decision}
    except Exception:
        return {**state, "orchestrator_decision": "regex"}  # safe fallback


async def parse_order(state: OrderState) -> OrderState:
    """Parse order items from message and generate confirmation response"""
    if state["intent"] != Intent.ORDER:
        return {**state, "parsed_items": None, "total": None}

    msg_lower = state["message"].strip().lower()

    # Short confirmation words with a pending order in state
    CONFIRM_WORDS = {"sí", "si", "dale", "ok", "confirmo", "confirmar", "de una", "obvio", "claro", "bueno", "bien", "perfecto", "listo", "okey"}
    if msg_lower in CONFIRM_WORDS and state.get("parsed_items"):
        items_data = state["parsed_items"]
        total = state.get("total", 0)
        store_id = state.get("store_id")
        phone = state["phone"]
        raw_msg = state.get("order_message", state["message"])

        if not store_id:
            return {**state, "response": "Error: no tengo tienda asignada para este pedido."}

        async with async_session_maker() as session:
            order = Order(
                id=uuid4(),
                store_id=store_id,
                customer_phone=phone,
                status=OrderStatus.RECEIVED,
                total_amount=total,
                raw_message=raw_msg,
            )
            session.add(order)

            for it in items_data:
                order_item = OrderItem(
                    id=uuid4(),
                    order_id=order.id,
                    product_id=it.get("product_id"),
                    product_name=it.get("producto", ""),
                    quantity=it.get("cantidad", 1),
                    unit_price=it.get("price", 0),
                    subtotal=(it.get("cantidad", 1) * it.get("price", 0)),
                )
                session.add(order_item)

            await session.commit()

        short_id = str(order.id)[:8]
        response_text = _human_response("order_confirmed")
        if "{short_id}" in response_text:
            response_text = response_text.format(short_id=short_id)
        return {
            **state,
            "order_id": order.id,
            "parsed_items": None,
            "total": None,
            "response": response_text,
        }

    # Short cancellation words
    CANCEL_WORDS = {"cancelar", "cancelo", "nop", "nel", "nope"}
    if msg_lower in CANCEL_WORDS and state.get("parsed_items"):
        return {
            **state,
            "parsed_items": None,
            "total": None,
            "response": _human_response("fallback", fallback="Dale, cancelado. Si querés pedir otra cosa, avisame nomás."),
        }

    # Phase 1B: try regex or LLM based on orchestrator decision
    decision = state.get("orchestrator_decision", "regex")
    regex_result = None

    if decision == "regex":
        regex_result = _regex_parse_order(state["message"])
        if regex_result is not None:
            items, is_add = regex_result
            has_ambiguous = False
            if items is None:
                regex_result = None
            elif _calculate_regex_confidence(state["message"], items) < CONFIDENCE_THRESHOLD:
                regex_result = None

    if regex_result is not None:
        items, is_add = regex_result
        # Merge with existing parsed items if this is an "add" operation
        if is_add and state.get("parsed_items"):
            existing = state["parsed_items"]
            merged = {item["producto"]: item for item in existing}
            for new_item in items:
                key = new_item["producto"]
                if key in merged:
                    merged[key]["cantidad"] = merged[key]["cantidad"] + new_item["cantidad"]
                else:
                    merged[key] = new_item
            items = list(merged.values())
    else:
        # LLM with or without context
        use_context = decision == "llm"
        try:
            if use_context:
                history = state.get("conversation_history", "")
                messages = ORDER_PARSE_WITH_CONTEXT_PROMPT.format_messages(
                    message=state["message"], history=str(history)[:800]
                )
            else:
                messages = ORDER_PARSE_PROMPT.format_messages(message=state["message"])
            llm = get_structured_llm(ParsedOrder, temperature=0)
            parsed = llm.invoke(messages)
            items = [item.model_dump() for item in parsed.items]
            has_ambiguous = any(item.get("ambiguous") for item in items)
        except Exception as e:
            logger.error(f"[parse_order] Error: {e}")
            return {**state, "parsed_items": None, "total": None, "has_ambiguous": None}

    store_id_str = str(state["store_id"]) if state.get("store_id") else None

    total = 0
    items_with_price = []
    unavailable_items = []
    not_found_items = []
    for item in items:
        producto = item.get("producto", "")
        cantidad = item.get("cantidad")
        if cantidad is None or cantidad <= 0:
            cantidad = 1
        if store_id_str:
            results = await search_product_by_name(producto, store_id_str)
            used_embedding = False
            if not results:
                results = await search_similar_products(producto, store_id_str, limit=1)
                used_embedding = True
            if results:
                if used_embedding and results[0].get("distance", 0) > 0.5:
                    not_found_items.append(producto)
                    continue
                if not results[0]["is_available"]:
                    unavailable_items.append(results[0]["name"])
                    continue
                price = results[0]["price"]
                unit = results[0]["unit"]
                product_id = results[0]["id"]
                subtotal = cantidad * price
                item["price"] = price
                item["unit"] = unit
                item["product_id"] = product_id
                items_with_price.append({
                    "producto": results[0]["name"],
                    "product_id": product_id,
                    "cantidad": cantidad,
                    "unidad": unit,
                    "precio_unitario": price,
                    "subtotal": subtotal,
                })
                total += subtotal
            else:
                not_found_items.append(producto)

    # Human-like response generation
    style = get_settings().response_style
    is_add = state.get("orchestrator_decision") == "regex" and regex_result is not None and is_add

    if items_with_price:
        lines = []
        for it in items_with_price:
            lines.append(f"- {it['cantidad']} {it['unidad']} de {it['producto']}: ${it['subtotal']:.0f}")
        items_text = "\n".join(lines)

        if style == "human":
            template = "order_added" if is_add else "order_confirm"
            response_text = _human_response(template, items=items_text, total=f"{total:.0f}")
        else:
            response_text = "Perfecto, tu pedido:\n\n" + items_text
            response_text += f"\n\n*Total: ${total:.0f}*\n\n¿Confirmás el pedido?"

        if unavailable_items:
            response_text += f"\n\n⚠️ {_human_response('product_unavailable', product=', '.join(unavailable_items))}" if style == "human" else f"\n\n⚠️ No disponible: {', '.join(unavailable_items)}"
        if not_found_items:
            response_text += f"\n\n{_human_response('product_not_found', product=', '.join(not_found_items))}" if style == "human" else f"\n\n⚠️ No encontré: {', '.join(not_found_items)}"

    elif unavailable_items or not_found_items:
        parts = []
        for p in unavailable_items:
            parts.append(_human_response("product_unavailable", product=p) if style == "human" else f"No tenemos {p} por ahora")
        for p in not_found_items:
            parts.append(_human_response("product_not_found", product=p) if style == "human" else f"No encontré {p}")
        response_text = "\n\n".join(parts)
        if style == "human":
            response_text += "\n\n¿Te muestro el catálogo?"
        else:
            response_text += ".\n\n¿Te interesaría pedir otra cosa?"

    elif has_ambiguous:
        response_text = "No estoy seguro de algunos productos. ¿Podrías ser más específico?"
    else:
        response_text = None

    return {
        **state,
        "parsed_items": items,
        "total": total,
        "has_ambiguous": has_ambiguous,
        "order_message": state["message"],
        "response": response_text,
    }


async def generate_response(state: OrderState) -> OrderState:
    """Generate response based on intent. All templates — zero LLM calls."""
    if state.get("response"):
        return state

    intent = state["intent"]

    # ORDER without parsed items: fallback
    if intent == Intent.ORDER:
        return {**state, "response": _human_response("fallback", fallback="No entendí bien qué productos querés. ¿Me lo podrías decir de otra forma?")}

    # GREETING from store config
    if intent == Intent.GREETING:
        store_msg = ""
        store_id = state.get("store_id")
        if store_id:
            async with async_session_maker() as _s:
                _r = await _s.execute(select(Store).where(Store.id == store_id))
                _store = _r.scalar_one_or_none()
                if _store and _store.greeting_message:
                    store_msg = _store.greeting_message
        response_text = store_msg or _human_response("greeting")
        return {**state, "response": response_text}

    # HELP template
    if intent == Intent.HELP:
        return {**state, "response": _human_response("help")}

    # UNKNOWN / any other fallback
    return {**state, "response": _human_response("fallback")}


def route_intent(state: OrderState) -> Literal[
    "parse_order", "generate_response", "check_order_status",
    "cancel_order", "payment_info", "show_catalog", "verify_receipt",
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
    elif state["intent"] == Intent.SEND_RECEIPT:
        return "verify_receipt"
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
            select(Product).where(Product.store_id == store_id, Product.is_available)
        )
        products = result.scalars().all()
    if not products:
        return {**state, "response": "No hay productos disponibles en este momento."}
    lines = [f"- {p.name}: ${p.price}/{p.unit}" for p in products]
    return {**state, "response": "Catalogo disponible:\n\n" + "\n".join(lines)}


async def verify_receipt(state: OrderState) -> OrderState:
    if state["intent"] != Intent.SEND_RECEIPT:
        return {**state}

    image_bytes = state.get("image_bytes")
    if not image_bytes:
        return {**state, "response": "No recibí la imagen del comprobante. Intentá de nuevo."}

    phone = state["phone"]
    store_id = state.get("store_id")

    async with async_session_maker() as session:
        result = await session.execute(
            select(Order)
            .where(
                Order.customer_phone == phone,
                Order.store_id == store_id,
                Order.status.in_([OrderStatus.AWAITING_PAYMENT, OrderStatus.PAYMENT_RECEIVED]),
            )
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        order = result.scalar_one_or_none()

        if not order:
            return {**state, "response": "No tenés pedidos pendientes de pago."}

        svc = ReceiptService(session)
        path = await svc.save_image(store_id, order, image_bytes)

        try:
            extracted = await svc.analyze(image_bytes)
        except Exception as e:
            logger.error(f"[verify_receipt] Gemini analyze error: {e}")
            return {**state, "response": "No pude leer el comprobante. ¿Podés reenviarlo más claro?", "image_path": path}

        response_text = await svc.verify(order, extracted)
        return {**state, "response": response_text, "image_path": path}


def build_order_graph():
    """Build the LangGraph for order processing"""
    graph = StateGraph(OrderState)

    graph.add_node("detect_intent", detect_intent)
    graph.add_node("orchestrate", orchestrate)
    graph.add_node("parse_order", parse_order)
    graph.add_node("generate_response", generate_response)
    graph.add_node("check_order_status", check_order_status)
    graph.add_node("cancel_order", cancel_order)
    graph.add_node("payment_info", payment_info)
    graph.add_node("show_catalog", show_catalog)
    graph.add_node("verify_receipt", verify_receipt)

    graph.set_entry_point("detect_intent")

    graph.add_conditional_edges(
        "detect_intent",
        route_intent,
        {
            "parse_order": "orchestrate",    # ORDER → orchestrate → parse_order
            "generate_response": "generate_response",
            "check_order_status": "check_order_status",
            "cancel_order": "cancel_order",
            "payment_info": "payment_info",
            "show_catalog": "show_catalog",
            "verify_receipt": "verify_receipt",
        },
    )

    graph.add_edge("orchestrate", "parse_order")
    graph.add_edge("parse_order", "generate_response")
    graph.add_edge("check_order_status", "generate_response")
    graph.add_edge("cancel_order", "generate_response")
    graph.add_edge("payment_info", "generate_response")
    graph.add_edge("show_catalog", "generate_response")
    graph.add_edge("verify_receipt", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile(checkpointer=MemorySaver())


order_agent = build_order_graph()
