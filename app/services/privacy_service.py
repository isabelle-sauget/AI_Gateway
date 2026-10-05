"""Local PII detection, masking, and placeholder restoration."""

import re
import uuid
from typing import cast, Tuple
import redis

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

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
FALSE_POSITIVES = {
    "CNP", "C.N.P.", "POSESOR AL CNP", "NR", "NR.", "CETATEAN", "CETĂȚEAN", "IBAN",
    "SUBSEMNATUL", "SUBSEMNATA", "SUBSEMNAȚII", "VÂNZĂTOR", "VANZATOR", "VÂNZĂTORUL",
    "CUMPĂRĂTOR", "CUMPARATOR", "CUMPĂRĂTORUL", "OBIECTUL", "OBIECTUL CONTRACTULUI",
    "TITULAR", "POSESOR", "ARTICOLUL", "PREȚUL", "PRETUL", "CONFIDENȚIALITATE",
    "CONTRACT", "CONTRACTUL", "CONTRACT DE VÂNZARE-CUMPĂRARE", "MODALITATEA"}

LEGAL_PREFIX_REGEX = re.compile(
    r"^(subsemnatul|subsemnata|subsemnații|subsemnatii|domnul|doamna|dl\.?|dna\.?)\s+",
    re.IGNORECASE,
)

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

def resolve_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """
    Prevent corrupted tags by ensuring no two entity spans overlap.
    Prefers specific custom recognizers over general NLP, then higher score.
    """
    def priority_key(item: RecognizerResult):
        # Custom ROMANIAN_* recognizers take priority over broad spaCy tags
        is_custom = 1 if item.entity_type.startswith("ROMANIAN_") else 0
        return (is_custom, item.score, item.end - item.start)

    sorted_by_prio = sorted(results, key=priority_key, reverse=True)
    selected: list[RecognizerResult] = []

    for candidate in sorted_by_prio:
        has_overlap = False
        for s in selected:
            # Overlap check: max(start1, start2) < min(end1, end2)
            if max(candidate.start, s.start) < min(candidate.end, s.end):
                has_overlap = True
                break
        if not has_overlap:
            selected.append(candidate)

    return sorted(selected, key=lambda x: x.start)

def anonymize_and_store(text: str, analyzer: AnalyzerEngine, redis_client: redis.Redis) -> Tuple[str, str]:
    """Replace detected PII with placeholders and store its mapping in Redis."""
    # Raised score_threshold from 0.1 to 0.4 to prevent spaCy false positives
    raw_results = analyzer.analyze(text=text, language="ro", entities=ENTITY_TYPES, score_threshold=0.4)
    filtered_results: list[RecognizerResult] = []

    for result in raw_results:
        # Strip legal honorifics from names
        if result.entity_type == "PERSON":
            entity_str = text[result.start:result.end]
            match = LEGAL_PREFIX_REGEX.match(entity_str)
            if match:
                result.start += match.end()

        if result.start >= result.end:
            continue

        exact_text = text[result.start:result.end].strip().upper()
        if exact_text in FALSE_POSITIVES:
            continue
        if result.entity_type == "LOCATION" and ("STR." in exact_text or "NR." in exact_text):
            continue

        filtered_results.append(result)

    # Resolve overlapping intervals to prevent tag mutilation
    clean_results = resolve_overlaps(filtered_results)

    # Forward Pass: Aliasing
    alias_map = {}
    entity_counters = {}

    for res in clean_results:
        real_text = text[res.start:res.end]
        mapping_key = f"{res.entity_type}_{real_text}"

        if mapping_key not in alias_map:
            count = entity_counters.get(res.entity_type, 0)
            alias_map[mapping_key] = f"<{res.entity_type}_{count}>"
            entity_counters[res.entity_type] = count + 1

    # Backward Pass: Substitution
    session_id = str(uuid.uuid4())
    sorted_results = sorted(clean_results, key=lambda x: x.start, reverse=True)
    scrubbed_text = text

    for res in sorted_results:
        real_text = text[res.start:res.end]
        mapping_key = f"{res.entity_type}_{real_text}"
        placeholder = alias_map[mapping_key]

        redis_client.hset(session_id, placeholder, real_text)
        scrubbed_text = scrubbed_text[:res.start] + placeholder + scrubbed_text[res.end:]

    redis_client.expire(session_id, 600)
    return scrubbed_text, session_id

def restore_text(scrubbed_response: str, session_id: str, redis_client: redis.Redis) -> str:
    """Restore placeholders and immediately delete their Redis mapping."""
    # Uses the injected redis_client
    mapping = cast(dict[str, str], redis_client.hgetall(session_id))
    restored_text = scrubbed_response
    for placeholder, real_text in mapping.items():
        restored_text = restored_text.replace(placeholder, real_text)
        
    redis_client.delete(session_id)
    return restored_text