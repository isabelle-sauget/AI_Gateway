from presidio_analyzer import PatternRecognizer, Pattern

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
            context=["cnp", "cod numeric personal", "codul numeric personal"],
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

class RomanianIDSeriesRecognizer(PatternRecognizer):
    def __init__(self):
        # matches seria directly
        series_pattern = Pattern(
            name="id_series_regex",
            regex=r"(?i)(?<=seria )[A-Z]{2}\b|(?i)(?<=serie )[A-Z]{2}\b",
            score=1.0, # highest confidence score
        )
        super().__init__(
            supported_entity="ROMANIAN_ID_SERIA",
            patterns=[series_pattern],
            context=[], # empty because we already provided context
            supported_language="ro",
        )

class RomanianIDNumberRecognizer(PatternRecognizer):
    def __init__(self):
        # Matches exactly 6 continuous digits
        number_pattern = Pattern(
            name="id_number_regex",
            regex=r"\b\d{6}\b",
            score=0.35,  # Low baseline to avoid catching postal codes without context
        )
        super().__init__(
            supported_entity="ROMANIAN_ID_NUMAR",
            patterns=[number_pattern],
            context=[
                "numar",
                "număr",
                "numarul",
                "numărul",
                "nr",
                "nr.",
            ],
            supported_language="ro",
        )

class RomanianDateRecognizer(PatternRecognizer):
    def __init__(self):
        # Matches: 14.09.2026, 12/05/2023, 1-12-99
        date_pattern = Pattern(
            name="date_regex",
            regex=r"\b\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4}\b",
            score=0.85, 
        )
        super().__init__(
            supported_entity="ROMANIAN_DATE",
            patterns=[date_pattern],
            context=[
                "data",
                "eliberat",
                "eliberării",
                "născut",
            ],
            supported_language="ro",
        )

class RomanianPhoneRecognizer(PatternRecognizer):
    def __init__(self):
        # Matches Romanian phones with or without +40, spaces, dots, or dashes
        # Examples: "0722 123 456", "+40744.123.456", "0241-123-456", "0722123456"
        phone_pattern = Pattern(
            name="phone_regex",
            regex=r"\b(?:\+40\s?|0)[237]\d(?:[\s\.\-]*\d){7}\b",
            score=0.85, 
        )
        super().__init__(
            supported_entity="ROMANIAN_PHONE",
            patterns=[phone_pattern],
            context=["telefon", "tel", "mobil", "fix", "contact"],
            supported_language="ro",
        )

class RomanianAddressDetailRecognizer(PatternRecognizer):
    def __init__(self):
        #Matches specific building identifiers: bloc, scara, etaj, apartament
        #Examples: "bl. C4", "sc. A", "et. 2", "ap. 12", "ap 12"
        #Note: We purposely exclude "nr." here so it doesn't accidentally eat the ID card number!
        address_pattern = Pattern(
            name="address_detail_regex",
            regex=r"(?i)\b(?:bl|bloc|sc|scara|et|etaj|ap|apartament)\.?\s*[A-Z0-9/-]+\b",
            score=0.85,
        )
        super().__init__(
            supported_entity="ROMANIAN_ADDRESS_DETAIL",
            patterns=[address_pattern],
            context=["str", "strada", "bulevardul", "domiciliul", "adresa"],
            supported_language="ro",
        )

#recognizes Romanian street addresses, the artery type, the name and the number so as to avoid confusion
class RomanianStreetRecognizer(PatternRecognizer):
    def __init__(self):
        # The ultimate foolproof regex: "Match the street type, then grab literally anything until you hit 'nr.' and a number."
        street_pattern = Pattern(
            name="street_regex",
            regex=r"(?i)(?:str\.?|strada|bd\.?|bulevardul|aleea|intrarea).*?nr\.?\s*\d+[a-zA-Z]?",
            score=1.0, 
        )
        super().__init__(
            supported_entity="ROMANIAN_STREET",
            patterns=[street_pattern],
            context=[],
            supported_language="ro",
        )

class RomanianNationalityRecognizer(PatternRecognizer):
    def __init__(self):
        #Lookbehind Regex: Looks for "cetatean" or "cetatenie" (with or without diacritics)
        #Extracts the alphabetical word immediately following it (including Romanian diacritical letters).
        nationality_pattern = Pattern(
            name="nationality_regex",
            regex=r"(?i)(?<=cetățean )[a-zăîâșț]+\b|(?i)(?<=cetatean )[a-zăîâșț]+\b|(?i)(?<=cetățenie )[a-zăîâșț]+\b|(?i)(?<=cetatenie )[a-zăîâșț]+\b",
            score=1.0, 
        )
        super().__init__(
            supported_entity="NATIONALITY",
            patterns=[nationality_pattern],
            context=[], 
            supported_language="ro",
        )

class RomanianIbanRecognizer(PatternRecognizer):
    def __init__(self):
        #Matches Romanian IBANs (Starts with RO, 2 digits, then 20 alphanumeric chars)
        #The (?:[\s\-]*[A-Z0-9]){20} part allows for spaces or dashes anywhere inside.
        #Examples: "RO12 BTRL 1234 5678 9012 3456" or "RO12BTRL1234567890123456"
        iban_pattern = Pattern(
            name="iban_regex",
            regex=r"(?i)\bRO\d{2}(?:[\s\-]*[A-Z0-9]){20}\b",
            score=0.95, 
        )
        super().__init__(
            supported_entity="ROMANIAN_IBAN",
            patterns=[iban_pattern],
            context=["iban", "cont", "bancar", "banca", "virament", "plata"],
            supported_language="ro",
        )
