from app.routers.auth import router as auth_router
from app.routers.trips import router as trips_router
from app.routers.itineraries import router as itineraries_router

__all__ = ["auth_router", "trips_router", "itineraries_router"]