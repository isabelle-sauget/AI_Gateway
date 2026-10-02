"""Document-processing and health endpoints."""

from fastapi import APIRouter, Depends, HTTPException
import redis
from presidio_analyzer import AnalyzerEngine

from app.schemas.document import DocumentRequest, DocumentResponse, HealthResponse
from app.api.dependencies import get_analyzer, get_redis_client
from app.services.gemini_client import generate_summary
from app.services.privacy_service import anonymize_and_store, restore_text


router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(redis_client: redis.Redis = Depends(get_redis_client)) -> HealthResponse:
    """Report whether the API process and Redis are available."""
    try:
        redis_status = "up" if redis_client.ping() else "down"
    except redis.ConnectionError:
        redis_status = "down"

    return HealthResponse(
        status="ok" if redis_status == "up" else "degraded",
        redis=redis_status,
    )


@router.post("/process-document", response_model=DocumentResponse)
def process_document_route(
    request: DocumentRequest,
    analyzer: AnalyzerEngine = Depends(get_analyzer),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> DocumentResponse:
    """Scrub PII, call the LLM with safe text, and restore the response."""
    try:
        scrubbed_text, session_id = anonymize_and_store(request.text, analyzer, redis_client)
        llm_response = generate_summary(scrubbed_text)
        final_restored_text = restore_text(llm_response, session_id, redis_client)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Document processing failed.") from exc

    return DocumentResponse(
        session_id=session_id,
        scrubbed_text=scrubbed_text,
        llm_response=llm_response,
        final_restored_text=final_restored_text,
    )