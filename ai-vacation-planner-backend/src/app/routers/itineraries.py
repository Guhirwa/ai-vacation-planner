from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_database
from app.models.itinerary import Itinerary
from app.models.trip import Trip
from app.schemas.itinerary import ItineraryCreate, ItineraryResponse
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/itineraries", tags=["Itineraries"])

@router.post("/", response_model=ItineraryResponse, status_code=status.HTTP_201_CREATED)
def create_itinerary(itinerary: ItineraryCreate, database: Session = Depends(get_database), current_user: User = Depends(get_current_user)):
    trip = database.query(Trip).filter(Trip.id == itinerary.trip_id, Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or not owned by user")

    existing = database.query(Itinerary).filter(Itinerary.trip_id == itinerary.trip_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Itinerary already exists for this trip")

    database_itinerary = Itinerary(trip_id=itinerary.trip_id, days_data=[day.dict() for day in itinerary.days])
    database.add(database_itinerary)
    database.commit()
    database.refresh(database_itinerary)

    return ItineraryResponse(
        trip_id=itinerary.trip_id,
        itinerary=itinerary.days,
        created_at=database_itinerary.created_at,
        updated_at=database_itinerary.updated_at
    )

@router.get("/{trip_id}")
def get_itinerary(trip_id: int, database: Session = Depends(get_database), current_user: User = Depends(get_current_user)):
    trip = database.query(Trip).filter(Trip.id == trip_id, Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    itinerary = database.query(Itinerary).filter(Itinerary.trip_id == trip_id).first()
    if not itinerary:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    return {
        "trip_id": trip_id,
        "itinerary": itinerary.days_data,
        "created_at": itinerary.created_at,
        "updated_at": itinerary.updated_at
    }