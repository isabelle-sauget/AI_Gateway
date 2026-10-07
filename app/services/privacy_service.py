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
    RomanianCompanyRecognizer,
    RomanianCUIRecognizer,
    RomanianTradeRegisterRecognizer,
    RomanianEUIDRecognizer,
    RomanianCAENRecognizer,
    RomanianInstitutionRecognizer,
)

ENTITY_TYPES = [
    "PERSON", "LOCATION", "ORGANIZATION", "ROMANIAN_CNP", "ROMANIAN_ID_SERIA",
    "ROMANIAN_ID_NUMAR", "EMAIL_ADDRESS", "ROMANIAN_PHONE", "ROMANIAN_ADDRESS_DETAIL",
    "ROMANIAN_STREET", "ROMANIAN_DATE", "NATIONALITY", "ROMANIAN_IBAN","ROMANIAN_CUI",
    "ROMANIAN_TRADE_REGISTER", "ROMANIAN_EUID", "ROMANIAN_CAEN","ROMANIAN_INSTITUTION"
]
FALSE_POSITIVES = {
    "CNP", "C.N.P.", "POSESOR AL CNP", "NR", "NR.", "CETATEAN", "CETĂȚEAN", "IBAN",
    "SUBSEMNATUL", "SUBSEMNATA", "SUBSEMNAȚII", "VÂNZĂTOR", "VANZATOR", "VÂNZĂTORUL",
    "CUMPĂRĂTOR", "CUMPARATOR", "CUMPĂRĂTORUL", "OBIECTUL", "OBIECTUL CONTRACTULUI",
    "TITULAR", "POSESOR", "ARTICOLUL", "PREȚUL", "PRETUL", "CONFIDENȚIALITATE",
    "CONTRACT", "CONTRACTUL", "CONTRACT DE VÂNZARE-CUMPĂRARE", "MODALITATEA DE PLATĂ",
    "MODALITATEA DE PLATA", "REGISTRUL COMERȚULUI", "REGISTRUL COMERTULUI","SEMNATURA","SEMNĂTURA",
    "CUI","(CUI)", "C.U.I.", "DIRECTOR", "DIRECTOR GENERAL", "ADMINISTRATOR", "REPREZENTANT", 
    "REPREZENTANT LEGAL", "ASOCIAT", "MANAGER"
    }

LEGAL_PREFIX_REGEX = re.compile(
    r"^(subsemnatul|subsemnata|subsemnații|subsemnatii|domnul|doamna|dl\.?|dna\.?)\s+",
    re.IGNORECASE,
)

COMPANY_PREFIX_REGEX = re.compile(
    r"^(societatea|s\.c\.|sc)\s+",
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
        RomanianCompanyRecognizer(), RomanianCUIRecognizer(), RomanianTradeRegisterRecognizer(), RomanianEUIDRecognizer(),
        RomanianCAENRecognizer(), RomanianInstitutionRecognizer()
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
    raw_results = analyzer.analyze(text=text, language="ro", entities=ENTITY_TYPES, score_threshold=0.4)
    filtered_results: list[RecognizerResult] = []

    for result in raw_results:
        if result.end - result.start > 70:
            continue

        entity_str = text[result.start:result.end]

        # 2. eliminates legal prefixes
        if result.entity_type in ("PERSON", "ORGANIZATION"):
            match = LEGAL_PREFIX_REGEX.match(entity_str)
            if match:
                result.start += match.end()
                entity_str = text[result.start:result.end]

            comp_match = COMPANY_PREFIX_REGEX.match(entity_str)
            if comp_match:
                result.start += comp_match.end()
                entity_str = text[result.start:result.end]

            sig_match = re.search(r"(\s*\n?\s*SEMNĂTUR[AĂ].*)$", entity_str, re.IGNORECASE)
            if sig_match:
                result.end -= len(sig_match.group(1))
                entity_str = text[result.start:result.end]

        if result.start >= result.end:
            continue

        exact_text = text[result.start:result.end].strip().upper()
        if "CONTRACT" in exact_text or exact_text in FALSE_POSITIVES:
            continue
        if result.entity_type == "LOCATION" and ("STR." in exact_text or "NR." in exact_text):
            continue

        filtered_results.append(result)

    clean_results = resolve_overlaps(filtered_results)

    alias_map = {}
    entity_counters = {}

    # FORWARD PASS
    for res in clean_results:
        real_text = text[res.start:res.end]
        normalized_text = " ".join(real_text.strip().upper().split())

        if normalized_text not in alias_map:
            count = entity_counters.get(res.entity_type, 0)
            alias_map[normalized_text] = f"<{res.entity_type}_{count}>"
            entity_counters[res.entity_type] = count + 1

    session_id = str(uuid.uuid4())
    sorted_results = sorted(clean_results, key=lambda x: x.start, reverse=True)
    scrubbed_text = text

    # BACKWARD PASS
    for res in sorted_results:
        real_text = text[res.start:res.end]
        normalized_text = " ".join(real_text.strip().upper().split())
        
        placeholder = alias_map[normalized_text]

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