from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TripCreate(BaseModel):
    destination: str = Field(..., min_length=1, max_length=100)
    days: int = Field(..., ge=1, le=365)
    budget: float = Field(..., ge=0)
    trip_style: str

    @field_validator("trip_style", mode="before")
    @classmethod
    def validate_trip_style(cls, value: str) -> str:
        allowed = ["budget", "luxury", "family", "adventure", "romantic", "business"]
        value_lower = value.lower()
        if value_lower not in allowed:
            raise ValueError(f"trip_style must be on of: {', '.join(allowed)}")
        return value_lower

class TripResponse(TripCreate):
    id: int
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message: str = "Trip created successfully"

    class Config:
        from_attributes = True

class TripUpdate(BaseModel):
    destination: Optional[str] = None
    days: Optional[int] = None
    budget: Optional[float] = None
    trip_style: Optional[str] = None