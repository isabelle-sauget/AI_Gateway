# privacy_service.py
import uuid
from typing import Tuple, cast
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from redis_client import create_redis_client
from recognizers import (
    RomanianCNPRecognizer, RomanianIDSeriesRecognizer, RomanianIDNumberRecognizer,
    RomanianDateRecognizer, RomanianPhoneRecognizer, RomanianAddressDetailRecognizer,
    RomanianStreetRecognizer, RomanianNationalityRecognizer, RomanianIbanRecognizer
)

def initialize_analyzer() -> AnalyzerEngine:
    """Sets up the Presidio Analyzer with the Romanian NLP model and custom recognizers."""
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "ro", "model_name": "ro_core_news_sm"}],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["ro"])

    # Register custom recognizers
    recognizers = [
        RomanianCNPRecognizer(), RomanianIDSeriesRecognizer(), RomanianIDNumberRecognizer(),
        RomanianDateRecognizer(), RomanianPhoneRecognizer(), RomanianAddressDetailRecognizer(),
        RomanianStreetRecognizer(), RomanianNationalityRecognizer(), RomanianIbanRecognizer()
    ]
    for rec in recognizers:
        analyzer.registry.add_recognizer(rec)
        
    return analyzer

def anonymize_and_store(text: str, analyzer: AnalyzerEngine) -> Tuple[str, str]:
    """Top Bread: Analyzes text, applies strict filters, stores mapping in Redis, and injects placeholders."""
    
    # 1. Analyze the text
    results = analyzer.analyze(
        text=text, 
        language="ro", 
        entities=[
            "PERSON", "LOCATION", "ORGANIZATION", "ROMANIAN_CNP", "ROMANIAN_ID_SERIA",
            "ROMANIAN_ID_NUMAR", "EMAIL_ADDRESS", "ROMANIAN_PHONE", "ROMANIAN_ADDRESS_DETAIL",
            "ROMANIAN_STREET", "ROMANIAN_DATE", "NATIONALITY", "ROMANIAN_IBAN"
        ],
        score_threshold=0.1
    )

    # 2. Strict false positive filtering
    false_positives = ["CNP", "C.N.P.", "POSESOR AL CNP", "NR", "NR.", "CETATEAN", "CETĂȚEAN"]
    clean_results = []
    street_matches = [res for res in results if res.entity_type == "ROMANIAN_STREET"]

    for res in results:
        exact_text = text[res.start:res.end].upper()
        
        if exact_text in false_positives:
            continue
            
        # Assassinate bad LOCATION guesses overlapping with Streets or abbreviations
        if res.entity_type == "LOCATION" and ("STR." in exact_text or "NR." in exact_text):
            continue
            
        clean_results.append(res)

    # 3. Redis Sandwich - Top Bread
    session_id = str(uuid.uuid4())
    redis_client = create_redis_client()
    
    try:
        # Sort backwards to prevent index shifting during replacement
        sorted_results = sorted(clean_results, key=lambda x: x.start, reverse=True)
        scrubbed_text = text
        
        for index, res in enumerate(sorted_results):
            real_text = text[res.start:res.end]
            placeholder = f"<{res.entity_type}_{index}>"
            
            # Store in Redis Hash
            redis_client.hset(session_id, placeholder, real_text)
            
            # Slice and replace
            scrubbed_text = scrubbed_text[:res.start] + placeholder + scrubbed_text[res.end:]
            
        # Set self-destruct timer (10 minutes)
        redis_client.expire(session_id, 600)
        
        return scrubbed_text, session_id
        
    finally:
        redis_client.close()

def restore_text(scrubbed_response: str, session_id: str) -> str:
    """Bottom Bread: Fetches mapping from Redis and restores the original text."""
    redis_client = create_redis_client()
    try:
        coat_check_data = redis_client.hgetall(session_id)
        coat_check_data = cast(dict[str, str], redis_client.hgetall(session_id))
        final_text = scrubbed_response
        
        for placeholder, real_text in coat_check_data.items():
            final_text = final_text.replace(placeholder, real_text)
            
        # Clean up immediately after successful restoration
        redis_client.delete(session_id)
        
        return final_text
    finally:
        redis_client.close()