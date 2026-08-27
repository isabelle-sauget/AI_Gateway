import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

nlp = spacy.load("ro_core_news_sm")
print("✓ spaCy Romanian model loaded successfully!")
print("✓ Presidio engines imported successfully!")