from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts import HumanMessagePromptTemplate, SystemMessagePromptTemplate

SYSTEM_PROMPT = """Eres un asistente de pedidos para una carnicería por WhatsApp.

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

Contexto de la tienda:
- Nombre: Carnicería El Corte
- Productos: carne molida (kg), bistec de rib-eye (unidad), salchichas (paquete 500g), pechuga de pollo (kg), chuletas de cerdo (kg), chorizo (unidad)
- Precios aproximados: carne molida $12/kg, rib-eye $8/unidad, salchichas $5/paquete, pollo $7/kg, chuletas $10/kg, chorizo $3/unidad
"""

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template(
        "Clasifica la intención del siguiente mensaje:\n\nMensaje: {message}\n\n"
        "Intenciones posibles: greeting, order, order_status, cancel, help, catalog, payment"
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
