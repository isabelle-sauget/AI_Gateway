"""Document-processing and health endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
import redis
from presidio_analyzer import AnalyzerEngine

from app.schemas.document import DocumentRequest, DocumentResponse, HealthResponse
from app.api.dependencies import get_analyzer, get_redis_client
from app.services.gemini_client import generate_summary
from app.services.document_extractor import extract_document_text
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


@router.post("/process-file", response_model=DocumentResponse)
def process_file_route(
    file: UploadFile,
    analyzer: AnalyzerEngine = Depends(get_analyzer),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> DocumentResponse:
    """
    Accepts PDF, DOCX, or TXT file uploads, extracts text (with OCR fallback),
    anonymizes PII, calls Gemini, and restores the PII.
    """
    try:
        # 1. Read binary content
        file_bytes = file.file.read()
        
        # 2. Extract text (native or OCR)
        raw_text = extract_document_text(file.filename or "unknown", file_bytes)

        # 3. Anonymize PII and cache mappings in Redis
        scrubbed_text, session_id = anonymize_and_store(raw_text, analyzer, redis_client)

        # 4. Process with Gemini
        llm_response = generate_summary(scrubbed_text)

        # 5. Restore placeholders with original values
        final_restored_text = restore_text(llm_response, session_id, redis_client)

        return DocumentResponse(
            session_id=session_id,
            scrubbed_text=scrubbed_text,
            llm_response=llm_response,
            final_restored_text=final_restored_text,
        )

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        ) from val_err
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {exc}"
        ) from exc
    finally:
        file.file.close()

@router.post("/test-ocr-pii", tags=["Testing"])
def test_ocr_pii_route(
    file: UploadFile,
    analyzer: AnalyzerEngine = Depends(get_analyzer),
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """
    Test file extraction (OCR) and PII anonymization without calling the LLM.
    Useful for validating extraction accuracy while avoiding LLM quotas.
    """
    try:
        # 1. read file
        file_bytes = file.file.read()
        
        # ocr extraction
        from app.services.document_extractor import extract_document_text
        raw_text = extract_document_text(file.filename or "unknown", file_bytes)

        # 3. anonymize pii
        from app.services.privacy_service import anonymize_and_store
        scrubbed_text, session_id = anonymize_and_store(raw_text, analyzer, redis_client)

        return {
            "status": "success",
            "message": "OCR and PII scrub executed successfully without LLM.",
            "session_id": session_id,
            "raw_character_count": len(raw_text),
            "scrubbed_text": scrubbed_text
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        file.file.close()