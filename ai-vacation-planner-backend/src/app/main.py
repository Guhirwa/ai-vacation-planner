from fastapi import FastAPI
from app.routers import auth, trips, itineraries
from app.database import engine, Base
from app.config import settings

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    debug=settings.debug
)

app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(itineraries.router)

@app.get("/")
def root():
    return {"message": "AI Vacation Planner API", "version": settings.api_version, "docs": "/docs"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}