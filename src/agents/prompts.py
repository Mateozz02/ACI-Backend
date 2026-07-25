from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts import HumanMessagePromptTemplate, SystemMessagePromptTemplate

SYSTEM_PROMPT = """Eres un asistente de pedidos por WhatsApp para una tienda.

Tu trabajo es:
1. Saludar amablemente a los clientes
2. Entender los pedidos que quieren hacer
3. Confirmar los pedidos
4. Dar información sobre productos
5. Ayudar con el estado de pedidos
6. Explicar cómo pagar

Responde de forma breve, amigable y en español.

Si el cliente quiere ordenar, extrae los productos y cantidades del mensaje.
Si no puedes entender algo, pide clarificación.

Usa el contexto de la tienda que se te proporciona para saber el nombre, productos, precios y políticas.
"""

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template(
        "Clasifica la intención del siguiente mensaje:\n\nMensaje: {message}\n\n"
        "Intenciones posibles: greeting, order, order_status, cancel, help, catalog, payment,send_receipt"
    ),
])

ORDER_PARSE_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        SYSTEM_PROMPT + "\n\n"
        "El cliente quiere hacer un pedido. Extrae los productos y cantidades."
        'Responde SOLO con JSON en este formato exacto:\n'
        "{{\"items\": [{{\"producto\": \"nombre del producto\", \"cantidad\": numero, \"unidad\": \"kg/unidad/paquete\"}}]}}"
    ),
    HumanMessagePromptTemplate.from_template("Mensaje del cliente: {message}"),
])

RESPONSE_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    HumanMessagePromptTemplate.from_template(
        "Mensaje del cliente: {message}\n\nIntención: {intent}\n\n"
        "Politicas de la tienda:\n{store_context}\n\n"
        "Genera una respuesta apropiada."
    ),
])
RECEIPT_VERIFY_PROMPT = """Analiza esta imagen de un comprobante de pago o transferencia bancaria.

Extrae la siguiente información. Si algún campo no está visible, usa null.

IMPORTANTE: Para números, no uses separadores de miles ni comas decimales.
Usa punto (.) como separador decimal. Ejemplo: 75975.00 (correcto), NO uses 75.975,00

Responde ÚNICAMENTE con un objeto JSON en este formato exacto:
{
  "amount": <número>,
  "date": "<YYYY-MM-DD>",
  "reference": "<número de referencia>",
  "confidence": <número entre 0 y 1>
}"""
