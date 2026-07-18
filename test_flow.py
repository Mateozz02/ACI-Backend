"""
Test de flujo completo: simula una conversacion WhatsApp con la carniceria.

Ejecutar: cd backend && uv run python test_flow.py
"""
import asyncio
from datetime import datetime
from sqlalchemy import text

from src.database import async_session_maker, init_db
from src.services.agent import process_message


async def seed_demo_store():
    """Crea una tienda demo con productos y politicas"""
    from src.models.models import Store, Product
    from src.services.embeddings import generate_embedding

    await init_db()

    async with async_session_maker() as db:
        await db.execute(text("DELETE FROM order_items"))
        await db.execute(text("DELETE FROM orders"))
        await db.execute(text("DELETE FROM products"))
        await db.execute(text("DELETE FROM conversations"))
        await db.execute(text("DELETE FROM stores"))
        await db.commit()

        store = Store(
            name="El Corte", phone="573001111111",
            greeting_message="Bienvenido a Carniceria El Corte!",
            payment_instructions="Transferencia al CBU 1234567890 o efectivo al retirar.",
            cancellation_policy="Cancela con 24hs de anticipacion.",
        )
        db.add(store)
        await db.commit()
        await db.refresh(store)
        store_id = store.id

        productos = [
            Product(name="Carne molida", store_id=store_id, unit="kg", price=12),
            Product(name="Bistec de rib-eye", store_id=store_id, unit="unidad", price=8),
            Product(name="Salchichas", store_id=store_id, unit="paquete", price=5),
            Product(name="Pechuga de pollo", store_id=store_id, unit="kg", price=7),
            Product(name="Chuletas de cerdo", store_id=store_id, unit="kg", price=10),
            Product(name="Chorizo", store_id=store_id, unit="unidad", price=3),
        ]
        for p in productos:
            db.add(p)
        await db.commit()

    return store_id


async def run_flow():
    print("=== Test de Flujo Completo ===\n")

    print("1. Sembrando datos demo...")
    store_id = await seed_demo_store()

    phone = "573009876543"
    print(f"\n2. Simulando conversacion con {phone}...\n")

    # -- Mensaje 1: Saludo --
    print("--- Msg 1: Saludo ---")
    r = await process_message(phone, "Hola, buenos dias!", store_id=store_id)
    print(f"  Intent: {r['intent']}")
    print(f"  IA: {r['response'][:100]}\n")

    # -- Mensaje 2: Pedido --
    print("--- Msg 2: Pedido ---")
    r = await process_message(phone, "Quiero 2kg de carne molida y 1 paquete de salchichas", store_id=store_id)
    print(f"  Intent: {r['intent']}")
    print(f"  Items: {r['parsed_items']}")
    print(f"  Total: ${r['total']}")
    print(f"  IA: {r['response'][:120]}\n")

    # -- Mensaje 3: Consulta de pago --
    print("--- Msg 3: Como pago? ---")
    r = await process_message(phone, "Como puedo pagar?", store_id=store_id)
    print(f"  Intent: {r['intent']}")
    print(f"  IA: {r['response'][:150]}\n")

    # -- Mensaje 4: Memoria --
    print("--- Msg 4: Memoria ---")
    r = await process_message(phone, "Que pedi hace un rato?", store_id=store_id)
    print(f"  Intent: {r['intent']}")
    print(f"  IA: {r['response'][:200]}\n")

    # -- Mensaje 5: Catalogo --
    print("--- Msg 5: Catalogo ---")
    r = await process_message(phone, "Que productos tienen?", store_id=store_id)
    print(f"  Intent: {r['intent']}")
    print(f"  IA: {r['response'][:200]}\n")

    print("=== Flujo completo OK ===")


if __name__ == "__main__":
    asyncio.run(run_flow())
