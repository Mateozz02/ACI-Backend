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

async def search_similar_products(
        query: str,
        store_id: str,
        limit: int = 5
) -> list[dict]:
    embedding = await async_generate_embedding(query)
    embedding_str = f"[{','.join(str(v) for v in embedding)}]"

    sql = text("""
        SELECT id,name,unit,price,description,
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

