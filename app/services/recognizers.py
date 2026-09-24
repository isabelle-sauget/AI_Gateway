"""Romanian-specific Presidio pattern recognizers."""

from presidio_analyzer import PatternRecognizer, Pattern


class RomanianCNPRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_CNP",
            patterns=[Pattern(name="cnp_regex", regex=r"\b[1-9]\d{12}\b", score=0.5)],
            context=["cnp", "cod numeric personal", "codul numeric personal"],
            supported_language="ro",
        )

    def validate_result(self, pattern_text: str) -> bool:
        if not pattern_text.isdigit() or len(pattern_text) != 13:
            return False
        weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
        control_digit = sum(int(pattern_text[index]) * weights[index] for index in range(12)) % 11
        control_digit = 1 if control_digit == 10 else control_digit
        return int(pattern_text[12]) == control_digit


class RomanianIDSeriesRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_ID_SERIA",
            patterns=[Pattern(name="id_series_regex", regex=r"(?i)(?<=seria )[A-Z]{2}\b|(?i)(?<=serie )[A-Z]{2}\b", score=1.0)],
            context=[],
            supported_language="ro",
        )


class RomanianIDNumberRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_ID_NUMAR",
            patterns=[Pattern(name="id_number_regex", regex=r"\b\d{6}\b", score=0.35)],
            context=["numar", "număr", "numarul", "numărul", "nr", "nr."],
            supported_language="ro",
        )


class RomanianDateRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_DATE",
            patterns=[Pattern(name="date_regex", regex=r"\b\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4}\b", score=0.85)],
            context=["data", "eliberat", "eliberării", "născut"],
            supported_language="ro",
        )


class RomanianPhoneRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_PHONE",
            patterns=[Pattern(name="phone_regex", regex=r"\b(?:\+40\s?|0)[237]\d(?:[\s\.\-]*\d){7}\b", score=0.85)],
            context=["telefon", "tel", "mobil", "fix", "contact"],
            supported_language="ro",
        )


class RomanianAddressDetailRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_ADDRESS_DETAIL",
            patterns=[Pattern(name="address_detail_regex", regex=r"(?i)\b(?:bl|bloc|sc|scara|et|etaj|ap|apartament)\.?\s*[A-Z0-9/-]+\b", score=0.85)],
            context=["str", "strada", "bulevardul", "domiciliul", "adresa"],
            supported_language="ro",
        )


class RomanianStreetRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_STREET",
            patterns=[Pattern(name="street_regex", regex=r"(?i)(?:str\.?|strada|bd\.?|bulevardul|aleea|intrarea).*?nr\.?\s*\d+[a-zA-Z]?", score=1.0)],
            context=[],
            supported_language="ro",
        )


class RomanianNationalityRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="NATIONALITY",
            patterns=[Pattern(name="nationality_regex", regex=r"(?i)(?<=cetățean )[a-zăîâșț]+\b|(?i)(?<=cetatean )[a-zăîâșț]+\b|(?i)(?<=cetățenie )[a-zăîâșț]+\b|(?i)(?<=cetatenie )[a-zăîâșț]+\b", score=1.0)],
            context=[],
            supported_language="ro",
        )


class RomanianIbanRecognizer(PatternRecognizer):
    def __init__(self):
        super().__init__(
            supported_entity="ROMANIAN_IBAN",
            patterns=[Pattern(name="iban_regex", regex=r"(?i)\bRO\d{2}(?:[\s\-]*[A-Z0-9]){20}\b", score=0.95)],
            context=["iban", "cont", "bancar", "banca", "virament", "plata"],
            supported_language="ro",
        )