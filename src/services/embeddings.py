import asyncio

from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from src.database import async_session_maker


_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def generate_embedding(text: str) -> list[float]:
    model = get_model()
    return model.encode(text).tolist()


async def async_generate_embedding(text: str) -> list[float]:
    return await asyncio.to_thread(generate_embedding, text)

async def search_product_by_name(query: str, store_id: str) -> list[dict]:
    """Fast product search using ILIKE (case-insensitive substring match).

    No embeddings, no CPU — suitable for structured LLM output where names
    are already canonical (e.g. Gemini structured output returns 'carne molida').
    Falls back to embedding search for creative/vague queries.
    """
    sql = text("""
        SELECT id, name, unit, price, is_available
        FROM products
        WHERE store_id = :store_id
          AND is_available = true
          AND (name ILIKE '%' || :query || '%'
               OR :query ILIKE '%' || name || '%')
        LIMIT 1
    """)
    async with async_session_maker() as session:
        result = await session.execute(sql, {
            "store_id": store_id,
            "query": query,
        })
        rows = result.fetchall()
        return [{
            "id": str(row.id),
            "name": row.name,
            "unit": row.unit,
            "price": row.price,
            "is_available": row.is_available,
            "distance": 0.0,
        } for row in rows]


async def search_similar_products(
        query: str,
        store_id: str,
        limit: int = 5
) -> list[dict]:
    embedding = await async_generate_embedding(query)
    embedding_str = f"[{','.join(str(v) for v in embedding)}]"

    sql = text("""
        SELECT id,name,unit,price,description,is_available,
               embedding <=> :embedding AS distance
        FROM products
        WHERE store_id = :store_id
        ORDER by distance
        LIMIT :limit
               """)
    async with async_session_maker () as session:
        result = await session.execute(sql,{
            "embedding": embedding_str,
            "store_id": store_id,
            "limit" : limit,
        })
        return [{
            "id": str(row.id),
            "name": row.name,
            "unit" : row.unit,
            "price": row.price,
            "is_available": row.is_available,
            "distance": float(row.distance),
        } for row in result.fetchall()]

async def get_store_context(store_id:str) -> str:
    sql = text("""
        SELECT greeting_message, payment_instructions, cancellation_policy
        FROM stores WHERE id = :store_id
        """)
    async with async_session_maker() as session:
        result = await session.execute(sql,{"store_id": store_id})
        row = result.fetchone()
    if not row:
        return ""
    parts = [p for p in row if p]
    return "\n".join(parts)


async def get_store_policies(store_id: str) -> str:
    """Return payment and cancellation policies only (no greeting)."""
    sql = text("""
        SELECT payment_instructions, cancellation_policy
        FROM stores WHERE id = :store_id
        """)
    async with async_session_maker() as session:
        result = await session.execute(sql, {"store_id": store_id})
        row = result.fetchone()
    if not row:
        return ""
    parts = [p for p in row if p]
    return "\n".join(parts)


async def get_available_products_summary(store_id: str) -> str:
    """Return a formatted list of available products for the store."""
    sql = text("""
        SELECT name, price, unit
        FROM products
        WHERE store_id = :store_id AND is_available = true
        ORDER BY name
        """)
    async with async_session_maker() as session:
        result = await session.execute(sql, {"store_id": store_id})
        rows = result.fetchall()
    if not rows:
        return "No hay productos disponibles en este momento."
    lines = [f"- {row.name}: ${row.price:.0f}/{row.unit}" for row in rows]
    return "\n".join(lines)

