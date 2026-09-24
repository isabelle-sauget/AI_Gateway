"""Document-processing and health endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from presidio_analyzer import AnalyzerEngine

from app.api.dependencies import get_analyzer
from app.schemas.document import DocumentRequest, DocumentResponse, HealthResponse
from app.services.gemini_client import generate_summary
from app.services.privacy_service import anonymize_and_store, restore_text
from app.services.redis_client import check_redis_connection


router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Report whether the API process and Redis are available."""
    redis_status = "up" if check_redis_connection() else "down"
    return HealthResponse(
        status="ok" if redis_status == "up" else "degraded",
        redis=redis_status,
    )


@router.post("/process-document", response_model=DocumentResponse)
async def process_document_route(
    request: DocumentRequest,
    analyzer: AnalyzerEngine = Depends(get_analyzer),
) -> DocumentResponse:
    """Scrub PII, call the LLM with safe text, and restore the response."""
    try:
        scrubbed_text, session_id = anonymize_and_store(request.text, analyzer)
        llm_response = generate_summary(scrubbed_text)
        final_restored_text = restore_text(llm_response, session_id)
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