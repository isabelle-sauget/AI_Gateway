import os
import redis


DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def create_redis_client() -> redis.Redis:
    """Create a Redis client using REDIS_URL or the local development default."""
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", DEFAULT_REDIS_URL),
        decode_responses=True,
    )


def check_redis_connection() -> bool:
    """Return whether the configured Redis server responds to a ping."""
    client = create_redis_client()
    try:
        return bool(client.ping())
    finally:
        client.close()