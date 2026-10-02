"""Dependencies shared by route handlers."""

from fastapi import Request
from presidio_analyzer import AnalyzerEngine
import redis

from app.core.config import settings

def get_analyzer(request: Request) -> AnalyzerEngine:
    """Read the initialized analyzer from FastAPI application state."""
    analyzer = getattr(request.app.state, "analyzer", None)
    if analyzer is None:
        raise RuntimeError("NLP Analyzer not loaded.")
    return analyzer

def get_redis_client():
    """
    Yields a Redis connection for the request, and ensures 
    it is closed after the request is finished.
    """
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        client.close()