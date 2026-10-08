# AI Gateway

## Overview

AI Gateway is a privacy-first document-processing API for organizations that need to use generative AI with Romanian-language business and legal documents while reducing the amount of personal and sensitive information sent to an external model provider.

The application creates a controlled boundary between internal documents and Gemini:

1. It accepts either Romanian text or an uploaded PDF, DOCX, or TXT document.
2. It extracts text from the document. Digital PDF text is extracted natively, while scanned or image-based PDF pages can be processed with OCR.
3. A locally running Presidio analyzer, powered by spaCy and Romanian-specific recognizers, identifies personal data and business identifiers.
4. Detected values are replaced with typed placeholders such as `<PERSON_0>`, `<ROMANIAN_CNP_0>`, or `<ROMANIAN_IBAN_0>`.
5. The original values are stored temporarily in Redis under a per-request session.
6. Only the scrubbed text is sent to the configured Gemini model for professional summarization.
7. Placeholders in Gemini's response are replaced with the original values, and the temporary Redis mapping is deleted.

The goal is to make AI-assisted document summarization more suitable for privacy-sensitive workflows without requiring the external model to receive the original values. This is a GDPR-oriented technical control, not a legal certification or a substitute for an organization's legal, security, data-retention, and vendor-risk assessments.

## Business purpose

Organizations commonly need to summarize contracts, identity documents, company records, and other operational documents. Those documents may contain names, contact details, identity numbers, bank information, addresses, and company identifiers. Sending the documents directly to a third-party AI service can create unnecessary privacy and compliance exposure.

AI Gateway addresses that exposure by:

- keeping detection and masking local to the gateway;
- supporting Romanian-specific identity, financial, company, and administrative identifiers;
- sending a minimized representation to Gemini rather than the original document text;
- preserving document usability by restoring values in the final response;
- providing a test endpoint for validating OCR and anonymization without consuming LLM quota; and
- exposing a health endpoint suitable for local checks and deployment probes.

## Current scope and important limitations

- The current AI operation is a professional document summary.
- The analyzer is configured for Romanian (`ro`) and uses the `ro_core_news_sm` spaCy model.
- Redis mappings expire after 600 seconds and are also deleted after response restoration.
- The API returns both the scrubbed text and the restored result. Callers should treat the scrubbed text and returned session identifier as sensitive operational data.
- PII detection is pattern- and NLP-based; it is not a guarantee that every sensitive value will be detected. Production deployments should validate detection quality against representative, legally approved test data.
- OCR depends on a locally installed Tesseract executable and the `ron` and `eng` language data. These are system prerequisites, not Python packages managed by `requirements.txt`.
- The application does not implement authentication, authorization, rate limiting, audit logging, tenant isolation, or persistent document storage. These controls should be added at the deployment or gateway layer before exposing the service beyond a trusted network.

## Technology stack

### Application and API

- **Python**: application runtime.
- **FastAPI**: HTTP API framework, dependency injection, validation, and generated OpenAPI documentation.
- **Uvicorn**: ASGI server used to run the application.
- **Pydantic and pydantic-settings**: request/response models and environment-based configuration.

### Privacy and language processing

- **Microsoft Presidio Analyzer**: entity analysis framework.
- **spaCy** with **`ro_core_news_sm`**: Romanian NLP engine.
- **Custom Presidio recognizers**: regular-expression and checksum-based detection for Romanian identifiers.
- **Redis**: short-lived storage for placeholder-to-original-value mappings.

### Document processing and AI

- **PyMuPDF (`pymupdf`)**: native PDF text extraction and page rendering.
- **python-docx**: paragraph and table extraction from DOCX files.
- **Pillow**: in-memory image handling for OCR.
- **pytesseract**: Tesseract OCR integration.
- **Google GenAI SDK (`google-genai`)**: Gemini API client.

Pinned Python dependencies are listed in [`requirements.txt`](./requirements.txt).

## Privacy pipeline

The central processing sequence is:

```text
Client
  |
  | text or PDF/DOCX/TXT upload
  v
FastAPI route
  |
  +--> document extraction (native text or OCR)
  |
  +--> local Romanian Presidio/spaCy analysis
  |       |
  |       +--> overlap resolution and false-positive filtering
  |       +--> typed placeholder replacement
  |       +--> temporary Redis mapping (10-minute TTL)
  |
  +--> Gemini receives scrubbed text only
  |
  +--> placeholders restored from Redis
  +--> Redis mapping deleted
  v
Client receives summary and processing metadata
```

Masking is performed from the end of the text toward the beginning so replacement offsets remain valid. Repeated normalized values reuse the same placeholder within a request. Overlapping recognizer results are resolved in favor of custom Romanian recognizers and higher-confidence matches.

### Recognized entity categories

The analyzer currently considers the following entity types:

- General NLP entities: `PERSON`, `LOCATION`, `ORGANIZATION`, and `EMAIL_ADDRESS`.
- Romanian personal and identity data: CNP, identity-card series, identity-card number, dates, phone numbers, nationality, street/address details.
- Romanian financial and business data: IBAN, CUI/CIF, company names, trade-register numbers, EUID, and CAEN codes.
- Romanian institutions and administrative organizations.

The exact matching behavior is implemented in [`privacy_service.py`](./app/services/privacy_service.py) and [`recognizers.py`](./app/services/recognizers.py). Recognizers include validation logic for CNP and CUI checksums where applicable.

## API reference

The application registers the document router with the `/api/v1` prefix. FastAPI also exposes interactive documentation at `/docs` and ReDoc at `/redoc` when the service is running.

All upload endpoints expect a multipart form field named `file`.

### `GET /api/v1/health`

Reports whether the API process and Redis are available.

#### Response: `200 OK`

```json
{
  "status": "ok",
  "redis": "up"
}
```

If the API process is running but Redis cannot be reached, the endpoint still responds with `200 OK` and reports a degraded dependency state:

```json
{
  "status": "degraded",
  "redis": "down"
}
```

This makes the endpoint useful for diagnostics and allows deployment tooling to distinguish process availability from Redis availability.

### `POST /api/v1/process-document`

Processes text supplied as JSON. The route detects and masks sensitive values, sends the scrubbed text to Gemini, and restores placeholders in the model response.

#### Request body

```json
{
  "text": "Textul documentului în limba română..."
}
```

`text` is required and must contain at least one character.

#### Response: `200 OK`

```json
{
  "session_id": "7c5c5f3d-7ef2-4a14-8c4c-0c5a9a2a4c77",
  "scrubbed_text": "Contractul este semnat de <PERSON_0>, CNP <ROMANIAN_CNP_0>.",
  "llm_response": "Rezumat: Contractul este semnat de <PERSON_0>, CNP <ROMANIAN_CNP_0>.",
  "final_restored_text": "Rezumat: Contractul este semnat de Ion Popescu, CNP 1800101123456."
}
```

Response fields:

- `session_id`: UUID associated with the temporary Redis mapping.
- `scrubbed_text`: text sent to Gemini after local masking.
- `llm_response`: Gemini's response while placeholders are still present.
- `final_restored_text`: response after placeholder restoration.

#### Error behavior

- `422 Unprocessable Entity`: invalid or missing JSON fields, including an empty `text`.
- `502 Bad Gateway`: Gemini communication or model-processing failure.
- `500 Internal Server Error`: an unexpected document-processing failure.

#### Example

```bash
curl -X POST "http://localhost:8000/api/v1/process-document" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Contractul este semnat de Ion Popescu.\"}"
```

### `POST /api/v1/process-file`

Processes an uploaded PDF, DOCX, or TXT file through extraction, local PII masking, Gemini summarization, and restoration.

#### Supported formats

- `.pdf`: native extraction per page, with Tesseract OCR fallback for pages containing fewer than 40 extracted characters.
- `.docx`: paragraphs and table cells are extracted from the in-memory document.
- `.txt`: decoded as UTF-8, ignoring invalid byte sequences.

Other extensions are rejected. Empty or unreadable documents are rejected.

#### Response: `200 OK`

The response has the same `DocumentResponse` shape as `process-document`.

#### Error behavior

- `400 Bad Request`: unsupported file extension or no readable text could be extracted.
- `500 Internal Server Error`: extraction, Redis, Gemini, or other processing failure. The current file route wraps all unexpected failures in this response.

#### Example

```bash
curl -X POST "http://localhost:8000/api/v1/process-file" ^
  -F "file=@contract.pdf"
```

### `POST /api/v1/test-ocr-pii`

Extracts text and performs local PII masking without calling Gemini. This endpoint is intended for OCR quality checks, recognizer testing, and development diagnostics when LLM quota should not be consumed.

#### Response: `200 OK`

```json
{
  "status": "success",
  "message": "OCR and PII scrub executed successfully without LLM.",
  "session_id": "7c5c5f3d-7ef2-4a14-8c4c-0c5a9a2a4c77",
  "raw_character_count": 1248,
  "scrubbed_text": "..."
}
```

#### Error behavior

Unexpected extraction or anonymization failures return `500 Internal Server Error`.

#### Example

```bash
curl -X POST "http://localhost:8000/api/v1/test-ocr-pii" ^
  -F "file=@scanned-document.pdf"
```

## Configuration

Create a `.env` file in the project root. The file is intentionally excluded from Git. Do not use the example below with a real key; provide your own secret through a secure secret-management mechanism in production.

```dotenv
GEMINI_API_KEY=replace-with-your-gemini-api-key
GEMINI_MODEL=gemini-3.6-flash
REDIS_URL=redis://localhost:6379/0
APP_NAME=GDPR AI Gateway API
```

Configuration is loaded by [`config.py`](./app/core/config.py). `GEMINI_API_KEY` is required. `GEMINI_MODEL` and `REDIS_URL` have defaults, and `APP_NAME` controls the FastAPI application title.

## Local setup

### Prerequisites

- Python environment compatible with the pinned dependencies.
- Redis running at the configured `REDIS_URL`.
- Tesseract OCR installed and available on `PATH` when scanned PDFs must be processed.
- Tesseract Romanian (`ron`) and English (`eng`) language data for the configured OCR command.
- A valid Gemini API key.

### Install and run

From the repository root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The service is then available at `http://localhost:8000`. Open `http://localhost:8000/docs` for the generated Swagger UI.

The module can also be started directly:

```bash
python -m app.main
```

The application initializes the Romanian analyzer once during the FastAPI lifespan and releases its application reference during shutdown. Redis connections are created per request and closed after each request.

## Project structure

```text
app/
├── main.py                         FastAPI application, lifespan, and router registration
├── api/
│   ├── dependencies.py             Analyzer and Redis request dependencies
│   └── routes/
│       └── document.py             Health, text, file, and OCR-test endpoints
├── core/
│   └── config.py                   Environment-backed application settings
├── schemas/
│   └── document.py                 Pydantic request and response contracts
└── services/
    ├── document_extractor.py       PDF, DOCX, TXT, and OCR extraction
    ├── gemini_client.py            Gemini client and summarization instruction
    ├── privacy_service.py          Analysis, masking, Redis storage, and restoration
    └── recognizers.py              Romanian-specific Presidio recognizers
```

## Operational and security guidance

For a production deployment:

1. Store `GEMINI_API_KEY` and Redis credentials in a secret manager, not in source control or a shared `.env` file.
2. Restrict network access to the API and Redis; Redis should not be publicly reachable.
3. Add authentication and authorization before allowing untrusted callers to submit documents.
4. Add request-size limits, rate limiting, structured audit events, and monitoring for Gemini, Redis, and OCR failures.
5. Define retention and deletion policies for request payloads, API logs, Redis data, and returned responses.
6. Use TLS for client-to-gateway and gateway-to-service connections where traffic crosses a trusted boundary.
7. Treat OCR and PII-recognition results as probabilistic and conduct privacy impact and accuracy testing before relying on them for regulated workflows.
