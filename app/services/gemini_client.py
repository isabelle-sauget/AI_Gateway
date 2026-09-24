"""Connection logic for the external Gemini model."""

from google import genai
from google.genai import types

from app.core.config import settings


SYSTEM_INSTRUCTION = (
    "You are a professional legal compliance assistant. "
    "Summarize or process the text provided by the user. "
    "You MUST preserve all placeholder tags (like <PERSON_0> or "
    "<ROMANIAN_CNP_1>) exactly as they are without modifying or removing them."
)


def generate_summary(scrubbed_text: str) -> str:
    """Send anonymized text to Gemini and return its response."""
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=(
                "Please generate a professional summary of this document:\n\n"
                f"{scrubbed_text}"
            ),
            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
        )
        return response.text or ""
    except Exception as exc:
        raise RuntimeError(f"Gemini API Communication Error: {exc}") from exc