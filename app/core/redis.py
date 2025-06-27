import redis.asyncio as redis
from app.core.config import settings

# Create Redis client
redis_client = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)


async def get_redis():
    return redis_client
