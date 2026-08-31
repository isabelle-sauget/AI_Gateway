from typing import cast

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult as AnonymizerRecognizerResult

# Custom Recognizer for Romanian CNP (Cod Numeric Personal)
class RomanianCNPRecognizer(PatternRecognizer):
    def __init__(self):
        # A regex looking for exactly 13 digits starting with 1-9
        cnp_pattern = Pattern(
            name="cnp_regex",
            regex=r"\b[1-9]\d{12}\b",
            score=0.5
        )
        super().__init__(
            supported_entity="ROMANIAN_CNP",
            patterns=[cnp_pattern],
            context=["cnp", "cod numeric personal"],
            supported_language="ro"
        )

    def validate_result(self, pattern_text: str) -> bool:
        """
        Validates the extracted 13-digit string using the official Modulo-11 checksum.
        If it fails the math test, it's not a real CNP, so we return False.
        """
        if not pattern_text.isdigit() or len(pattern_text) != 13:
            return False
            
        # The official CNP multiplication weights
        weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
        
        # Multiply the first 12 digits by their weights and sum them up
        total_sum = sum(int(pattern_text[i]) * weights[i] for i in range(12))
        
        # Calculate the remainder
        remainder = total_sum % 11
        control_digit = 1 if remainder == 10 else remainder
        
        # Compare our calculated control digit with the 13th digit of the CNP
        return int(pattern_text[12]) == control_digit

def test_privacy_engine():
    print("Loading Romanian NLP model...")
    
    # 1. Configure spaCy to use the Romanian language model
    nlp_configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "ro", "model_name": "ro_core_news_sm"}],
    }
    
    # Initialize the NLP engine
    provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
    nlp_engine = provider.create_engine()
    
    # 2. Initialize Presidio Analyzer and Anonymizer
    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine, 
        supported_languages=["ro"]
    )

    analyzer.registry.add_recognizer(RomanianCNPRecognizer())
    
    anonymizer = AnonymizerEngine()
    
    # 3. The Test Data
    test_text = "Pacientul Popescu Ion, posesor al CNP 1900101123457, s-a prezentat la clinica cu adresa de email ion.popescu@spital.ro."
    
    # 4. Analyze the text for PII
    results = analyzer.analyze(text=test_text, language="ro", entities=["PERSON", "ROMANIAN_CNP", "EMAIL_ADDRESS"])

    # Words that the NLP commonly misidentifies
    false_positives = ["CNP", "C.N.P.", "POSESOR AL CNP"]
    
    # 3. Filter the results to remove false positives
    clean_results = [
        res for res in results 
        if test_text[res.start:res.end].upper() not in false_positives
    ]
    
    # 5. Anonymize the text based on the findings
    anonymized_result = anonymizer.anonymize(
        text=test_text, 
        analyzer_results=cast(list[AnonymizerRecognizerResult], clean_results)
    )
    
    # 6. Output the results
    print("\n--- RESULTS ---")
    print("Original:  ", test_text)
    print("Anonymized:", anonymized_result.text)

if __name__ == "__main__":
    test_privacy_engine()