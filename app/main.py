"""FastAPI application, lifespan, and router registration."""

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


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(document.router)
