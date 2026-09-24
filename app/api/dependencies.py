"""Dependencies shared by route handlers."""

from fastapi import Request
from presidio_analyzer import AnalyzerEngine


def get_analyzer(request: Request) -> AnalyzerEngine:
    """Read the initialized analyzer from FastAPI application state."""
    analyzer = getattr(request.app.state, "analyzer", None)
    if analyzer is None:
        raise RuntimeError("NLP Analyzer not loaded.")
    return analyzer
