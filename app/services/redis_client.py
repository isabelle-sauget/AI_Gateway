"""Connection logic for short-lived Redis placeholder mappings."""

import redis

from app.core.config import settings


def create_redis_client() -> redis.Redis:
    """Create a Redis client using the configured connection URL."""
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def check_redis_connection() -> bool:
    """Return whether Redis responds to a ping."""
    client = create_redis_client()
    try:
        return bool(client.ping())
    finally:
        client.close()