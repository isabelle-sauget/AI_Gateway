# AI Gateway

This project is a GDPR-oriented AI gateway. It detects Romanian personal data locally, replaces it with placeholders, sends only the scrubbed text to an AI provider, and restores the original values in the final response.

The application entry point is `app/main.py`.

## Project structure

```text
app/
    main.py                 FastAPI app, lifespan, and router registration
    api/
        dependencies.py     Request-scoped access to shared application resources
        routes/
            document.py     GET /health and POST /api/v1/process-document
    core/
        config.py           Pydantic settings loaded from .env
    schemas/
        document.py         Pydantic request and response models
    services/
        gemini_client.py    Gemini connection logic
        redis_client.py     Redis connection logic
        privacy_service.py  PII detection, masking, and restoration
        recognizers.py      Romanian-specific Presidio recognizers
```

## Routes

### `GET /health`

Checks that the API process is running and reports whether Redis responds to a ping. It is useful for local checks and deployment health probes.

### `POST /api/v1/process-document`

Accepts document text, masks detected PII, sends the safe text to Gemini, then restores the original values in the returned AI response. The response also exposes the intermediate scrubbed text for learning and testing.
