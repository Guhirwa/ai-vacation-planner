"""Application entry point: creates the FastAPI app, configures logging, and registers routers."""

import logging

from app.config import settings

# Must happen before anything below imports anthropic/langchain (routers do,
# transitively, through the services they use), since ddtrace can only patch
# a library if it gets there before that library is first imported anywhere
# in the process. This is what lets DD_TRACE_ENABLED=True in .env "just
# work" with a normal `uvicorn` start, instead of requiring the app to be
# launched through the separate ddtrace-run wrapper every time.
if settings.dd_trace_enabled:
    import ddtrace

    ddtrace.patch(raise_errors=False, anthropic=True, langchain=True)

    from ddtrace.llmobs import LLMObs

    LLMObs.enable(
        ml_app=settings.dd_service,
        api_key=settings.dd_api_key,
        env=settings.dd_env,
        agentless_enabled=True,
    )

from fastapi import FastAPI
from app.routers import auth, trips, itineraries, knowledge, voice, mcp
from app.routers.auth import user_router
from app.database import engine, Base
from app.observability import RequestContextFilter, RequestIDMiddleware

_app_log_handler = logging.StreamHandler()
_app_log_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s user_id=%(user_id)s]: %(message)s"
    )
)
_app_log_handler.addFilter(RequestContextFilter())

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

app.add_middleware(RequestIDMiddleware)

app.include_router(auth.router)
app.include_router(user_router)
app.include_router(trips.router)
app.include_router(itineraries.router)
app.include_router(knowledge.router)
app.include_router(voice.router)
app.include_router(mcp.router)

@app.get("/")
def root():
    return {"message": "AI Vacation Planner API", "version": settings.api_version, "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}