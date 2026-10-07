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
            patterns=[Pattern(name="phone_regex", regex=r"(?:(?:\+40|0040)[-.\s]?|0)[237]\d{2}(?:[-.\s]?\d{3}){2}", score=0.85)],
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
            patterns=[Pattern(name="street_regex", regex=r"(?i)\b(?:str\.|strada|b-dul|bd\.|bulevardul|șos\.|șoseaua|calea|alee|aleea|intr\.|intrarea)\s+(?:[A-Za-zĂÂÎȘȚăâîșț\-]+\s*)+nr\.\s*[0-9A-Za-z]+", score=0.85)],
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

class RomanianCompanyRecognizer(PatternRecognizer):
    def __init__(self):
        # Explicitly added A-Z and uppercase diacritics to make it bulletproof
        company_pattern = Pattern(
            name="romanian_company",
            regex=r"(?i)\b(?:S\.C\.|SC|SOCIETATEA)?\s*(?:[A-Za-zĂÂÎȘȚăâîșț0-9\-&]+\s+){1,6}(?:S\.R\.L\.|SRL|S\.A\.|SA|S\.N\.C\.|SNC|S\.C\.S\.|SCS|S\.C\.A\.|SCA)\.?",
            score=0.85
        )
        super().__init__(
            supported_entity="ORGANIZATION",
            patterns=[company_pattern],
            supported_language="ro",
        )

class RomanianCUIRecognizer(PatternRecognizer):
    def __init__(self):
        # (?<![\d\.,]) -> Ensures the number doesn't start directly after a digit, period, or comma
        # (?![\.,]\d)  -> Ensures the number isn't followed immediately by a period/comma and another digit
        # Pattern 1: Safely catches "RO 39485718" (Allows 2-10 digits, no lookbehind needed)
        p1 = Pattern(
            name="cui_with_ro",
            regex=r"(?i)\bRO\s*([1-9]\d{1,9})\b",
            score=0.85
        )
        
        # Pattern 2: Catches standalone numbers "39485718" (Requires 6-10 digits to prevent matching prices)
        p2 = Pattern(
            name="cui_standalone",
            regex=r"(?<![\d\.,])\b([1-9]\d{5,9})\b(?![\.,]\d)",
            score=0.5
        )

        super().__init__(
            supported_entity="ROMANIAN_CUI",
            patterns=[p1, p2],
            context=["cui", "cif", "cod unic de inregistrare", "identificare fiscala"],
            supported_language="ro",
        )

    def validate_result(self, pattern_text: str) -> bool:
        """Applies the official Modulo-11 checksum for Romanian CUI/CIF."""
        # 1. Clean the string (remove 'RO' and whitespace)
        clean_text = pattern_text.upper().replace("RO", "").strip()
        
        # Ensure we only have digits left and length is between 2 and 10
        if not clean_text.isdigit() or not (2 <= len(clean_text) <= 10):
            return False

        # 2. Modulo-11 Setup
        # The official Romanian weights applied from right to left
        weights = [7, 5, 3, 2, 1, 7, 5, 3, 2]
        
        # Pad the base CUI with leading zeros to make it exactly 9 digits
        base_cui = clean_text[:-1].zfill(9)
        control_digit = int(clean_text[-1])
        
        # 3. Calculate Checksum
        checksum = sum(int(base_cui[i]) * weights[i] for i in range(9))
        calculated_control = (checksum * 10) % 11
        
        # If modulo results in 10, the control digit is 0
        if calculated_control == 10:
            calculated_control = 0
            
        # 4. Final Validation: If it returns True, Presidio boosts the score to 1.0!
        return control_digit == calculated_control

class RomanianTradeRegisterRecognizer(PatternRecognizer):
    def __init__(self):
        # Matches formats like: J40/1234/2026, F08/123/2015, J 40 / 1234 / 2026
        # [JFC] - Juridical, Physical, Cooperative
        # \d{1,2} - County code (1 to 52)
        # \d{1,6} - Order number
        # (?:19|20)\d{2} - Year (1900-2099)
        # (?i) - Case insensitive
        tr_pattern = Pattern(
            name="trade_register_regex",
            regex=r"(?i)\b[JFC]\s*(?:/)?\s*\d{1,2}\s*/\s*\d{1,6}\s*/\s*(?:19|20)\d{2}\b",
            score=0.85
        )
        super().__init__(
            supported_entity="ROMANIAN_TRADE_REGISTER",
            patterns=[tr_pattern],
            context=["registrul comertului", "onrc", "inmatriculare", "inregistrare", "nr. ord."],
            supported_language="ro",
        )

class RomanianEUIDRecognizer(PatternRecognizer):
    def __init__(self):
        # Matches: ROONRC.J40/1234/2026
        euid_pattern = Pattern(
            name="euid_regex",
            regex=r"(?i)\bROONRC\.[JFC]\s*(?:/)?\s*\d{1,2}\s*/\s*\d{1,6}\s*/\s*(?:19|20)\d{2}\b",
            score=0.95
        )
        super().__init__(
            supported_entity="ROMANIAN_EUID",
            patterns=[euid_pattern],
            context=["euid", "identificator unic european"],
            supported_language="ro",
        )

class RomanianCAENRecognizer(PatternRecognizer):
    def __init__(self):
        # Matches exactly 4 digits
        caen_pattern = Pattern(
            name="caen_regex",
            regex=r"\b\d{4}\b",
            score=0.3 # Low base score to prevent false positives with years/PINs
        )
        super().__init__(
            supported_entity="ROMANIAN_CAEN",
            patterns=[caen_pattern],
            context=["caen", "cod caen", "activitate principala", "activitate"],
            supported_language="ro",
        )

class RomanianInstitutionRecognizer(PatternRecognizer):
    def __init__(self):
        # Catches standard ID issuers, police, and courts + their subsequent locations/sectors
        inst_pattern = Pattern(
            name="institution_regex",
            regex=r"(?i)\b(?:SPCEP|SCPLEP|SPCLEP|SPCJE|DEPABD|Poliția|Primăria|Judecătoria|Tribunalul|Curtea de Apel)\s+(?:Sector\s*\d+|[A-Za-zĂÂÎȘȚăâîșț]+(?:[\s\-][A-Za-zĂÂÎȘȚăâîșț]+)*)",
            score=0.85
        )
        super().__init__(
            supported_entity="ORGANIZATION", # Maps seamlessly into your existing ORGANIZATION tags
            patterns=[inst_pattern],
            supported_language="ro",
        )