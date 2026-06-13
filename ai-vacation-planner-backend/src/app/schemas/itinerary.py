from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class DayActivity(BaseModel):
    day: int = Field(..., ge=1)
    activities: List[str] = Field(..., min_length=1)

    @field_validator("activities", mode="before")
    @classmethod
    def validate_activities(cls, value: List[str]) -> List[str]:
        return [activity.strip() for activity in value if activity.strip()]

class ItineraryCreate(BaseModel):
    trip_id: int = Field(..., gt=0)
    days: List[DayActivity] = Field(..., min_length=1)

class ItineraryResponse(BaseModel):
    trip_id: int
    itinerary: List[DayActivity]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message: str = "Itinerary Created Successfully"

    class Config:
        from_attributes = True


