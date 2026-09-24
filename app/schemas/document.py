"""HTTP schemas for document processing."""

from pydantic import BaseModel, Field


class DocumentRequest(BaseModel):
    text: str = Field(min_length=1, description="Romanian text to process")


class DocumentResponse(BaseModel):
    session_id: str
    scrubbed_text: str
    llm_response: str
    final_restored_text: str


class HealthResponse(BaseModel):
    status: str
    redis: str
