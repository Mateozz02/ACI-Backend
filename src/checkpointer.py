from langgraph.checkpoint.redis import AsyncRedisSaver

from src.config import get_settings

settings = get_settings()


async def build_checkpointer() -> AsyncRedisSaver:
    """Build and set up (create indices) an async Redis-backed LangGraph checkpointer.

    The caller owns the returned saver's lifecycle and must call
    `await saver.__aexit__(None, None, None)` (or use it as an async context
    manager) on shutdown to release the underlying Redis connection.
    """
    saver = AsyncRedisSaver(
        redis_url=settings.redis_url,
        ttl={"default_ttl": settings.pending_order_ttl_minutes, "refresh_on_read": True},
    )
    await saver.__aenter__()
    return saver
