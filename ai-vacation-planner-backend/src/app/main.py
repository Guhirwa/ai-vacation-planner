"""Application entry point: creates the FastAPI app, configures logging, and registers routers."""

import logging

from fastapi import FastAPI
from app.routers import auth, trips, itineraries, knowledge, voice
from app.routers.auth import user_router
from app.database import engine, Base
from app.config import settings

_app_log_handler = logging.StreamHandler()
_app_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.DEBUG)
_app_logger.addHandler(_app_log_handler)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    debug=settings.debug,
    redirect_slashes=False
)

app.include_router(auth.router)
app.include_router(user_router)
app.include_router(trips.router)
app.include_router(itineraries.router)
app.include_router(knowledge.router)
app.include_router(voice.router)

@app.get("/")
def root():
    return {"message": "AI Vacation Planner API", "version": settings.api_version, "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}