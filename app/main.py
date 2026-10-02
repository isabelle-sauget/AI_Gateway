"""FastAPI application, lifespan, and router registration."""

import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import document
from app.core.config import settings
from app.services.privacy_service import initialize_analyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
	"""Load the local NLP analyzer once when the application starts."""
	app.state.analyzer = initialize_analyzer()
	yield
	app.state.analyzer = None



app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.include_router(document.router)

if __name__ == "__main__":
    # We pass "app.main:app" as a string so the --reload flag works properly.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


# docker start redis-stack
# docker stop redis-stack
