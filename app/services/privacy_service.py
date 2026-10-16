"""Local PII detection, masking, and placeholder restoration."""

import re
import uuid
from presidio_analyzer.nlp_engine import SpacyNlpEngine
from typing import cast, Tuple
import redis
from spacy.tokens import Doc, Span

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
    RomanianLicensePlateRecognizer,
)

ENTITY_TYPES = [
    "PERSON", "LOCATION", "ORGANIZATION", "ROMANIAN_CNP", "ROMANIAN_ID_SERIA",
    "ROMANIAN_ID_NUMAR", "EMAIL_ADDRESS", "ROMANIAN_PHONE", "ROMANIAN_ADDRESS_DETAIL",
    "ROMANIAN_STREET", "ROMANIAN_DATE", "NATIONALITY", "ROMANIAN_IBAN","ROMANIAN_CUI",
    "ROMANIAN_TRADE_REGISTER", "ROMANIAN_EUID", "ROMANIAN_CAEN","ROMANIAN_INSTITUTION",
    "ROMANIAN_LICENSE_PLATE"
]
# FALSE_POSITIVES = {
#     "CNP", "C.N.P.", "POSESOR AL CNP", "NR", "NR.", "CETATEAN", "CETĂȚEAN", "IBAN",
#     "SUBSEMNATUL", "SUBSEMNATA", "SUBSEMNAȚII", "VÂNZĂTOR", "VANZATOR", "VÂNZĂTORUL",
#     "CUMPĂRĂTOR", "CUMPARATOR", "CUMPĂRĂTORUL", "OBIECTUL", "OBIECTUL CONTRACTULUI",
#     "TITULAR", "POSESOR", "ARTICOLUL", "PREȚUL", "PRETUL", "CONFIDENȚIALITATE",
#     "CONTRACT", "CONTRACTUL", "CONTRACT DE VÂNZARE-CUMPĂRARE", "MODALITATEA DE PLATĂ",
#     "MODALITATEA DE PLATA", "REGISTRUL COMERȚULUI", "REGISTRUL COMERTULUI","SEMNATURA","SEMNĂTURA",
#     "CUI","(CUI)", "C.U.I.", "DIRECTOR", "DIRECTOR GENERAL", "ADMINISTRATOR", "REPREZENTANT", 
#     "REPREZENTANT LEGAL", "ASOCIAT", "MANAGER"
#     }

# Strips legal roles and honorifics attached to the front of detected names
LEGAL_PREFIX_REGEX = re.compile(
    r"^(?:subsemnatul|subsemnata|subscrisul|subscrisa|reclamantul|reclamanta|"
    r"pârâtul|pârâta|avocat|av\.|domnul|doamna|dl\.|d-na\.?|dna\.?|martorul|martora)\s+",
    re.IGNORECASE,
)

# Catches Roman numeral section headers like "I. SITUAȚIA DE FAPT" or "II. TEMEIURI DE DREPT"
SECTION_HEADER_REGEX = re.compile(r"^[IVXLCDM]+\.\s+")

COMPANY_PREFIX_REGEX = re.compile(
    r"^(societatea|s\.c\.|sc)\s+",
    re.IGNORECASE,
)

# Sensitive date trigger words (checks the 60 characters preceding a date)
SENSITIVE_DATE_CONTEXT_REGEX = re.compile(
    r"\b(?:născut(?:ă)?|nașter(?:e|ii)|eliberat(?:ă)?|emiterii|expiră|valabil(?:ă|itate)?)\b",
    re.IGNORECASE,
)

# Valid identity card trigger words (prevents masking "împuternicire avocațială seria BV")
ID_CARD_CONTEXT_REGEX = re.compile(
    r"\b(?:C\.?\s*I\.?|B\.?\s*I\.?|carte(?:a)?\s+de\s+identitate|buletin(?:ul)?)\b",
    re.IGNORECASE,
)

# Preceding context that guarantees the following entity is a human PERSON
PERSON_CONTEXT_REGEX = re.compile(
    r"\b(?:subsemnatul|subsemnata|subscrisul|subscrisa|reclamantul|reclamanta|"
    r"pârâtul|pârâta|avocat|av\.|domnul|doamna|dl\.|d-na\.?|dna\.?|martorul|martora)\s*$",
    re.IGNORECASE,
)

# Public institutions & courts that should NOT be masked as private ORGANIZATION PII
PUBLIC_INSTITUTION_REGEX = re.compile(
    r"^(?:tribunalul|judecătoria|curtea\s+de\s+apel|înalta\s+curte|parchetul|"
    r"oficiul\s+registrului\s+comerțului|spclep|spcep|scplep|spcje|depabd|"
    r"baroul|poliția|primăria|ministerul|anaf)\b",
    re.IGNORECASE,
)

def is_grammatically_valid_entity(span, nlp) -> bool:
    """
    Algorithmically validates whether a spaCy NER span is a true Named Entity
    using Part-of-Speech (POS) tags instead of hardcoded false-positive lists.
    """
    text_clean = span.text.strip()
    if not text_clean or text_clean[0].islower():
        return False

    # Reject Roman numeral section headers (e.g., "I. SITUAȚIA DE FAPT", "III. PROBATORIUL")
    if SECTION_HEADER_REGEX.match(text_clean.upper()):
        return False

    # Reject short 2-4 letter ALL-CAPS acronyms guessed by spaCy (e.g., "CIM", "AWB", "CUI")
    if text_clean.isupper() and len(text_clean) <= 4 and " " not in text_clean:
        return False

    # If the ENTIRE span is ALL-CAPS (e.g., "TEMEIURI DE DREPT"),
    # re-parse in lowercase so ALL-CAPS formatting doesn't trick spaCy into assigning PROPN.
    if text_clean.isupper():
        lower_doc = nlp(text_clean.lower())
        return any(t.pos_ == "PROPN" for t in lower_doc)

    # For standard/mixed-case spans, trust the full-sentence contextual POS tag in spacy_doc:
    # Must contain at least one Proper Noun (PROPN), rejecting verbs ("Depunem") and nouns ("Reclamantul", "Anexă")
    return any(token.pos_ == "PROPN" for token in span if not token.is_punct and not token.is_space)

def initialize_analyzer() -> AnalyzerEngine:
    """Create the local Romanian Presidio analyzer and custom recognizers."""
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "ro", "model_name": "ro_core_news_lg"}],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["ro"])
    for recognizer in [
        RomanianCNPRecognizer(), RomanianIDSeriesRecognizer(), RomanianIDNumberRecognizer(),
        RomanianDateRecognizer(), RomanianPhoneRecognizer(), RomanianAddressDetailRecognizer(),
        RomanianStreetRecognizer(), RomanianNationalityRecognizer(), RomanianIbanRecognizer(),
        RomanianCompanyRecognizer(), RomanianCUIRecognizer(), RomanianTradeRegisterRecognizer(), RomanianEUIDRecognizer(),
        RomanianCAENRecognizer(), RomanianLicensePlateRecognizer()
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

DIACRITIC_MAP = str.maketrans({
    "ş": "ș",
    "ţ": "ț",
    "Ş": "Ș",
    "Ţ": "Ț",
})

def anonymize_and_store(text: str, analyzer: AnalyzerEngine, redis_client: redis.Redis) -> Tuple[str, str]:
    text = text.translate(DIACRITIC_MAP)

    # 1. Pre-compute spaCy NlpArtifacts once so Presidio and our POS filter share the same Doc
    nlp_engine = analyzer.nlp_engine
    nlp_artifacts = nlp_engine.process_text(text, language="ro")
    spacy_doc = nlp_artifacts.tokens
    spacy_engine = cast(SpacyNlpEngine, nlp_engine)
    spacy_model = spacy_engine.nlp["ro"] #type: ignore

    raw_results = analyzer.analyze(
        text=text,
        language="ro",
        entities=ENTITY_TYPES,
        score_threshold=0.4,
        nlp_artifacts=nlp_artifacts,
    )
    filtered_results: list[RecognizerResult] = []

    for result in raw_results:
        if result.end - result.start > 70:
            continue

        # Only mask dates preceded by birth or ID-issuance context
        if result.entity_type == "ROMANIAN_DATE":
            preceding_window = text[max(0, result.start - 60) : result.start]
            if not SENSITIVE_DATE_CONTEXT_REGEX.search(preceding_window):
                continue

        # Only mask ID series/numbers preceded by C.I. / B.I. (ignores "împuternicire avocațială seria BV")
        if result.entity_type in ("ROMANIAN_ID_SERIA", "ROMANIAN_ID_NUMAR"):
            preceding_window = text[max(0, result.start - 50) : result.start]
            if not ID_CARD_CONTEXT_REGEX.search(preceding_window):
                continue

        entity_str = text[result.start:result.end]

        # 2. Eliminates legal prefixes & corrects entity type if preceded by a human role/honorific
        if result.entity_type in ("PERSON", "ORGANIZATION", "LOCATION"):
            match = LEGAL_PREFIX_REGEX.match(entity_str)
            if match:
                result.start += match.end()
                entity_str = text[result.start:result.end]
                result.entity_type = "PERSON"
            else:
                # Check if the text immediately before the span is a human prefix ("Subscrisul ", "avocat ", "dl. ")
                preceding_prefix = text[max(0, result.start - 25) : result.start]
                if PERSON_CONTEXT_REGEX.search(preceding_prefix):
                    result.entity_type = "PERSON"

            comp_match = COMPANY_PREFIX_REGEX.match(entity_str)
            if comp_match:
                result.start += comp_match.end()
                entity_str = text[result.start:result.end]

            sig_match = re.search(r"(\s*\n?\s*SEMNĂTUR[AĂ].*)$", entity_str, re.IGNORECASE)
            if sig_match:
                result.end -= len(sig_match.group(1))
                entity_str = text[result.start:result.end]

            # Truncate trailing descriptions after a comma on PERSON tags (e.g., ", fostă asistentă comercială")
            if result.entity_type == "PERSON" and "," in entity_str:
                comma_idx = entity_str.index(",")
                result.end = result.start + comma_idx
                entity_str = text[result.start:result.end]

        # Trim leading/trailing whitespace so start/end offsets hug the exact words
        stripped_leading = len(entity_str) - len(entity_str.lstrip())
        stripped_trailing = len(entity_str) - len(entity_str.rstrip())
        result.start += stripped_leading
        result.end -= stripped_trailing

        if result.start >= result.end:
            continue

        clean_span = text[result.start:result.end]

        # Discard PERSON, LOCATION, or ORGANIZATION tags that start with a lowercase letter
        if result.entity_type in ("PERSON", "LOCATION", "ORGANIZATION") and clean_span[0].islower():
            continue

        # Do not mask public institutions, courts, or state registries as private ORGANIZATIONs
        if result.entity_type in ("ORGANIZATION", "LOCATION") and PUBLIC_INSTITUTION_REGEX.match(clean_span):
            continue

        exact_text = clean_span.upper()
        if result.entity_type == "LOCATION" and ("STR." in exact_text or "NR." in exact_text):
            continue

        # 3. Algorithmic POS validation for statistical spaCy guesses
        recognizer_name = (
            result.recognition_metadata.get("recognizer_name", "")
            if result.recognition_metadata
            else ""
        )
        if recognizer_name == "SpacyRecognizer" and result.entity_type in ("PERSON", "LOCATION", "ORGANIZATION"):
            char_span = spacy_doc.char_span(result.start, result.end, alignment_mode="expand")
            if char_span is None or not is_grammatically_valid_entity(char_span, spacy_model):
                continue

        filtered_results.append(result)

    clean_results = resolve_overlaps(filtered_results)

    # SECOND-PASS PROPAGATION: Catch unmasked occurrences (including ALL-CAPS or reversed PERSON names)
    known_entities: dict[str, tuple[str, float]] = {}
    for res in clean_results:
        if res.entity_type in ("PERSON", "LOCATION", "ORGANIZATION"):
            span_text = text[res.start:res.end].strip()
            if len(span_text) >= 3 and span_text not in known_entities:
                known_entities[span_text] = (res.entity_type, res.score)

    for span_text, (ent_type, ent_score) in known_entities.items():
        search_variants = {span_text}
        if ent_type == "PERSON":
            parts = span_text.split()
            if len(parts) == 2:
                search_variants.add(f"{parts[1]} {parts[0]}")

        for variant in search_variants:
            flags = re.IGNORECASE if ent_type == "PERSON" else 0
            pattern = re.compile(
                rf"(?<![A-Za-zĂÂÎȘȚăâîșț]){re.escape(variant)}(?![A-Za-zĂÂÎȘȚăâîșț])",
                flags=flags,
            )
            for m in pattern.finditer(text):
                filtered_results.append(
                    RecognizerResult(entity_type=ent_type, start=m.start(), end=m.end(), score=ent_score)
                )

    clean_results = resolve_overlaps(filtered_results)

    alias_map = {}
    entity_counters = {}

    def get_lookup_key(raw_str: str, entity_type: str) -> str:
        tokens = raw_str.strip().upper().split()
        if entity_type == "PERSON":
            tokens.sort()
        return " ".join(tokens)

    # FORWARD PASS
    for res in clean_results:
        real_text = text[res.start:res.end]
        lookup_key = get_lookup_key(real_text, res.entity_type)

        if lookup_key not in alias_map:
            count = entity_counters.get(res.entity_type, 0)
            alias_map[lookup_key] = f"<{res.entity_type}_{count}>"
            entity_counters[res.entity_type] = count + 1

    session_id = str(uuid.uuid4())
    sorted_results = sorted(clean_results, key=lambda x: x.start, reverse=True)
    scrubbed_text = text

    # BACKWARD PASS
    for res in sorted_results:
        real_text = text[res.start:res.end]
        lookup_key = get_lookup_key(real_text, res.entity_type)

        placeholder = alias_map[lookup_key]

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