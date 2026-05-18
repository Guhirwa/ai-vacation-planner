from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_database
from app.dependencies.auth import get_current_user
from app.models import User, Trip
from app.schemas.trip import TripResponse, TripCreate, TripUpdate

router = APIRouter(prefix="/trips", tags=["Trips"])

@router.post("/", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(trip: TripCreate, database: Session = Depends(get_database()), current_user: User = Depends(get_current_user())):
    new_trip = Trip(
        destination=trip.destination,
        days=trip.days,
        budget=trip.budget,
        trip_style=trip.trip_style,
        user_id=current_user.id
    )
    database.add(new_trip)
    database.commit()
    database.refresh(new_trip)
    return TripResponse(
        id=new_trip.id,
        destination=new_trip.destination,
        days=new_trip.days,
        budget=new_trip.budget,
        trip_style=new_trip.trip_style,
        user_id=new_trip.user_id,
        created_at=new_trip.created_at,
        updated_at=new_trip.created_at
    )

@router.get("/")
def get_all_trips(database: Session = Depends(get_database()), current_user: User = Depends(get_current_user)):
    trips = database.query(Trip).filter(Trip.user_id == current_user.id).all()
    return trips

@router.get("/{trip_id}")
def get_trip(trip_id: int, database: Session = Depends(get_database()), current_user: User = Depends(get_current_user())):
    trip = database.query(Trip).filter(Trip.id == trip_id, Trip.user_id == current_user.id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

@router.put("/{trip_id}")
def update_trip(trip_id: int, trip_update: TripUpdate, database: Session = Depends(get_database()), current_user = Depends(get_current_user())):
    trip = database.query(Trip).filter(Trip.id == trip_id,Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    update_data = trip_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(trip, key, value)
    database.commit()
    return {"message": "Trip updated successfully"}

@router.delete("/{trip_id}")
def delete_trip(trip_id: int, database: Session = Depends(get_database()), current_user: User = Depends(get_current_user())):
    trip = database.query(User).filter(Trip.id == trip_id, Trip.user_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    database.delete(trip)
    database.commit()
    return {"message": "Trip deleted successfully"}