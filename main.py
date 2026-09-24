# main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from google import genai
from google.genai import types

#Load .env file
load_dotenv()

# 2. Configure the Gemini API client securely
gemini_client = genai.Client()

from privacy_service import initialize_analyzer, anonymize_and_store, restore_text

#openai_client = OpenAI()
#kept in lifespan loader
analyzer_engine = None

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """This runs exactly once when the server starts up."""
    global analyzer_engine
    print("Booting up Presidio NLP Analyzer (this takes a few seconds)...")
    analyzer_engine = initialize_analyzer()
    print("Analyzer ready! API is now accepting requests.")
    yield
    # Anything after the yield runs when the server shuts down
    print("Shutting down API...")

# Initialize the API framework
app = FastAPI(title="GDPR AI Gateway API", lifespan=lifespan)

# Define the expected JSON body for the Request
class DocumentRequest(BaseModel):
    text: str

# Define the expected JSON body for the Response
class DocumentResponse(BaseModel):
    session_id: str
    scrubbed_text: str
    llm_response: str
    final_restored_text: str

def call_gemini_llm(scrubbed_text: str) -> str:
    """Sends the scrubbed text to Google Gemini and returns its response."""
    if gemini_client is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    try:
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=f"Please generate a professional summary of this document:\n\n{scrubbed_text}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a professional legal compliance assistant. "
                    "Summarize or process the text provided by the user. "
                    "You MUST preserve all placeholder tags (like <PERSON_0> or <ROMANIAN_CNP_1>) "
                    "exactly as they are without modifying or removing them."
                )
            ),
        )

        return response.text or ""
        
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API Communication Error: {str(e)}")

@app.post("/api/v1/process-document", response_model=DocumentResponse)
async def process_document(request: DocumentRequest):
    if not analyzer_engine:
        raise HTTPException(status_code=500, detail="NLP Analyzer not loaded.")

    try:
        # 1. TOP BREAD: Scrub and Store
        safe_text, session_id = anonymize_and_store(request.text, analyzer_engine)
        
        # 2. THE MEAT: Send to Gemini
        llm_output = call_gemini_llm(safe_text)
        
        # 3. BOTTOM BREAD: Restore real data
        final_text = restore_text(llm_output, session_id)
        
        return DocumentResponse(
            session_id=session_id,
            scrubbed_text=safe_text,
            llm_response=llm_output,
            final_restored_text=final_text
            )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# OpenAI LLM call variant

# def call_openai_llm(scrubbed_text: str) -> str:
#     """Sends the scrubbed text to OpenAI and returns its response."""
#     try:
#         response = openai_client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": (
#                         "You are a professional legal compliance assistant. "
#                         "Summarize or process the text provided by the user. "
#                         "You MUST preserve all placeholder tags (like <PERSON_0> or <ROMANIAN_CNP_1>) "
#                         "exactly as they are without modifying or removing them."
#                     )
#                 },
#                 {
#                     "role": "user",
#                     "content": f"Please generate a professional summary of this document:\n\n{scrubbed_text}"
#                 }
#             ],
#             temperature=0.0
#         )
#         content = response.choices[0].message.content
#         return content or ""
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI API Communication Error: {str(e)}")

# @app.post("/api/v1/process-document", response_model=DocumentResponse)
# async def process_document(request: DocumentRequest):
#     """
#     1. Top Bread: Scrub PII and store mapping in Redis.
#     2. The Meat: Send scrubbed text to OpenAI.
#     3. Bottom Bread: Restore PII using Redis.
#     """
#     if not analyzer_engine:
#         raise HTTPException(status_code=500, detail="Services not fully initialized.")
#     try:
#         #1.TOP BREAD: Scrub and Store
#         safe_text, session_id = anonymize_and_store(request.text, analyzer_engine)
        
#         #2.THE MEAT: Send to LLM
#         llm_output = call_openai_llm(safe_text)
        
#         #3.BOTTOM BREAD: Restore real data
#         final_text = restore_text(llm_output, session_id)
        
#         #Return the full lifecycle
#         return DocumentResponse(
#             session_id=session_id,
#             scrubbed_text=safe_text,
#             llm_response=llm_output,
#             final_restored_text=final_text
#         )
#     except HTTPException as he:
#         raise he  #Re-raise known HTTP exceptions
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)