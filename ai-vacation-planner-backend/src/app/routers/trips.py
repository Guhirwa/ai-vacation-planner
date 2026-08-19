from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_database
from app.dependencies.auth import get_current_user
from app.models import User, Trip
from app.schemas.trip import TripResponse, TripCreate, TripUpdate, MessageResponse

router = APIRouter(prefix="/trips", tags=["Trips"])


@router.post("", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TripResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_trip(
    trip: TripCreate,
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> TripResponse:
    """Create a new trip owned by the current user.

    Args:
        trip: The trip creation payload.
        database: The database session dependency.
        current_user: The authenticated user, injected via dependency.

    Returns:
        The created trip as a TripResponse.
    """
    new_trip = Trip(
        destination=trip.destination,
        days=trip.days,
        budget=trip.budget,
        trip_style=trip.trip_style,
        user_id=current_user.id,
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
        updated_at=new_trip.created_at,
        message="Trip created successfully",
    )


@router.get("", response_model=List[TripResponse])
@router.get("/", response_model=List[TripResponse], include_in_schema=False)
def get_all_trips(
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
):
    trips = database.query(Trip).filter(Trip.user_id == current_user.id).all()
    return trips


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: int,
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
):
    trip = (
        database.query(Trip)
        .filter(Trip.id == trip_id, Trip.user_id == current_user.id)
        .first()
    )
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.put("/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: int,
    trip_update: TripUpdate,
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> Trip:
    """Update fields on an existing trip owned by the current user.

    Args:
        trip_id: The ID of the trip to update.
        trip_update: The fields to update; unset fields are left unchanged.
        database: The database session dependency.
        current_user: The authenticated user, injected via dependency.

    Returns:
        The updated trip, serialized as a TripResponse.

    Raises:
        HTTPException(404): If the trip does not exist or does not belong
            to the current user.
    """
    trip = (
        database.query(Trip)
        .filter(Trip.id == trip_id, Trip.user_id == current_user.id)
        .first()
    )
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    update_data = trip_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(trip, key, value)
    database.commit()
    database.refresh(trip)
    return trip


@router.delete("/{trip_id}", response_model=MessageResponse)
def delete_trip(
    trip_id: int,
    database: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Delete a trip owned by the current user.

    Args:
        trip_id: The ID of the trip to delete.
        database: The database session dependency.
        current_user: The authenticated user, injected via dependency.

    Returns:
        A confirmation message.

    Raises:
        HTTPException(404): If the trip does not exist or does not belong
            to the current user.
    """
    trip = (
        database.query(Trip)
        .filter(Trip.id == trip_id, Trip.user_id == current_user.id)
        .first()
    )
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    database.delete(trip)
    database.commit()
    return MessageResponse(message="Trip deleted successfully")
