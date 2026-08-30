"""Crea una tienda demo con pedidos para probar el frontend.
Si la tienda ya existe, solo agrega pedidos nuevos."""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select

from src.database import async_session_maker, init_db
from src.models.models import User, Store, Product, Order, OrderItem, OrderStatus
from src.services.auth import hash_password


async def seed():
    await init_db()

    async with async_session_maker() as db:
        # Crear usuario demo
        result = await db.execute(select(User).where(User.email == "admin@orderflow.com"))
        user = result.scalar_one_or_none()
        if not user:
            user = User(email="admin@orderflow.com", password_hash=hash_password("admin123"), name="Admin")
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Usuario creado: {user.email}")
        else:
            print(f"Usuario ya existe: {user.email}")
        user_id = user.id

        # Crear tienda
        result = await db.execute(select(Store).where(Store.name == "Carniceria El Corte"))
        store = result.scalar_one_or_none()

        if store:
            store_id = store.id
            print(f"Tienda ya existe: {store_id}")
        else:
            store = Store(name="Carniceria El Corte", phone="573002222222",
                          user_id=user_id,
                          greeting_message="Bienvenido a Carniceria El Corte!",
                          payment_instructions="Transferencia CBU 1234567890 o efectivo al retirar.",
                          cancellation_policy="Cancela con 24hs de anticipacion.")
            db.add(store)
            await db.commit()
            await db.refresh(store)
            store_id = store.id
            print(f"Tienda creada: {store_id}")

        # Productos (solo si no existen)
        result = await db.execute(select(Product).where(Product.store_id == store_id))
        if not result.scalars().all():
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
            print(f"{len(productos)} productos creados")
        else:
            print("Productos ya existen")

        # Pedidos de prueba
        orders_data = [
            {"phone": "573001234567", "name": "Maria", "status": OrderStatus.CONFIRMED,
             "items": [("Carne molida", 2, 12), ("Chorizo", 3, 3)]},
            {"phone": "573007654321", "name": "Pedro", "status": OrderStatus.AWAITING_PAYMENT,
             "items": [("Pechuga de pollo", 3, 7), ("Salchichas", 1, 5)]},
            {"phone": "573003334444", "name": "Ana", "status": OrderStatus.RECEIVED,
             "items": [("Bistec de rib-eye", 2, 8)]},
            {"phone": "573009998888", "name": None, "status": OrderStatus.COMPLETED,
             "items": [("Chuletas de cerdo", 4, 10), ("Carne molida", 1, 12)]},
        ]

        for od in orders_data:
            order = Order(
                store_id=store_id, customer_phone=od["phone"],
                customer_name=od["name"], status=od["status"],
            )
            total = 0
            for name, qty, price in od["items"]:
                total += qty * price
                item = OrderItem(product_name=name, quantity=qty, unit_price=price, subtotal=qty * price)
                order.items.append(item)
            order.total_amount = total
            db.add(order)

        await db.commit()

    print(f"{len(orders_data)} pedidos agregados")
    print("\nAbrí http://localhost:3000 para ver el dashboard")


asyncio.run(seed())
