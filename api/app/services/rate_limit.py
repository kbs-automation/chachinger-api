import time

from redis.asyncio import Redis


async def hit(redis: Redis, key: str, limit: int, window_seconds: int) -> bool:
    """Fixed-window counter. Returns False once the limit is exceeded."""
    bucket = int(time.time() // window_seconds)
    redis_key = f"rl:{key}:{bucket}"
    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)
    return count <= limit
