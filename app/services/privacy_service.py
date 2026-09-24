"""Local PII detection, masking, and placeholder restoration."""

import uuid
from typing import cast

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.services.redis_client import create_redis_client
from app.services.recognizers import (
    RomanianAddressDetailRecognizer,
    RomanianCNPRecognizer,
    RomanianDateRecognizer,
    RomanianIbanRecognizer,
    RomanianIDNumberRecognizer,
    RomanianIDSeriesRecognizer,
    RomanianNationalityRecognizer,
    RomanianPhoneRecognizer,
    RomanianStreetRecognizer,
)


ENTITY_TYPES = [
    "PERSON", "LOCATION", "ORGANIZATION", "ROMANIAN_CNP", "ROMANIAN_ID_SERIA",
    "ROMANIAN_ID_NUMAR", "EMAIL_ADDRESS", "ROMANIAN_PHONE", "ROMANIAN_ADDRESS_DETAIL",
    "ROMANIAN_STREET", "ROMANIAN_DATE", "NATIONALITY", "ROMANIAN_IBAN",
]
FALSE_POSITIVES = {"CNP", "C.N.P.", "POSESOR AL CNP", "NR", "NR.", "CETATEAN", "CETĂȚEAN", "IBAN"}


def initialize_analyzer() -> AnalyzerEngine:
    """Create the local Romanian Presidio analyzer and custom recognizers."""
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "ro", "model_name": "ro_core_news_sm"}],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["ro"])
    for recognizer in [
        RomanianCNPRecognizer(), RomanianIDSeriesRecognizer(), RomanianIDNumberRecognizer(),
        RomanianDateRecognizer(), RomanianPhoneRecognizer(), RomanianAddressDetailRecognizer(),
        RomanianStreetRecognizer(), RomanianNationalityRecognizer(), RomanianIbanRecognizer(),
    ]:
        analyzer.registry.add_recognizer(recognizer)
    return analyzer


def anonymize_and_store(text: str, analyzer: AnalyzerEngine) -> tuple[str, str]:
    """Replace detected PII with placeholders and store its mapping in Redis."""
    results = analyzer.analyze(text=text, language="ro", entities=ENTITY_TYPES, score_threshold=0.1)
    clean_results = []
    for result in results:
        exact_text = text[result.start:result.end].upper()
        if exact_text in FALSE_POSITIVES:
            continue
        if result.entity_type == "LOCATION" and ("STR." in exact_text or "NR." in exact_text):
            continue
        clean_results.append(result)

    session_id = str(uuid.uuid4())
    redis_client = create_redis_client()
    try:
        scrubbed_text = text
        for index, result in enumerate(sorted(clean_results, key=lambda item: item.start, reverse=True)):
            real_text = text[result.start:result.end]
            placeholder = f"<{result.entity_type}_{index}>"
            redis_client.hset(session_id, placeholder, real_text)
            scrubbed_text = scrubbed_text[:result.start] + placeholder + scrubbed_text[result.end:]
        redis_client.expire(session_id, 600)
        return scrubbed_text, session_id
    finally:
        redis_client.close()


def restore_text(scrubbed_response: str, session_id: str) -> str:
    """Restore placeholders and immediately delete their Redis mapping."""
    redis_client = create_redis_client()
    try:
        mapping = cast(dict[str, str], redis_client.hgetall(session_id))
        restored_text = scrubbed_response
        for placeholder, real_text in mapping.items():
            restored_text = restored_text.replace(placeholder, real_text)
        redis_client.delete(session_id)
        return restored_text
    finally:
        redis_client.close()