"""Pydantic schemas for itinerary creation, responses, and LLM output validation."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class DayActivity(BaseModel):
    """A single day's activities within an itinerary.

    Used both for manually supplied itinerary days and for the days stored
    on an itinerary response.
    """

    day: int = Field(..., ge=1)
    activities: List[str] = Field(..., min_length=1)

    @field_validator("activities", mode="before")
    @classmethod
    def validate_activities(cls, value: List[str]) -> List[str]:
        """Strip whitespace from each activity and drop any that are empty.

        Args:
            value: The raw list of activity strings.

        Returns:
            The list of non-empty, stripped activity strings.
        """
        return [activity.strip() for activity in value if activity.strip()]


class ItineraryCreate(BaseModel):
    """Request payload for creating an itinerary, manually or via AI generation."""

    trip_id: int = Field(..., gt=0)
    generate_with_ai: bool = False
    days: Optional[List[DayActivity]] = None

    @model_validator(mode="after")
    def validate_days_or_ai(self) -> "ItineraryCreate":
        """Ensure a manual `days` list is supplied when AI generation is off.

        Returns:
            The validated model instance.

        Raises:
            ValueError: If `generate_with_ai` is False and `days` is empty or missing.
        """
        if not self.generate_with_ai and not self.days:
            raise ValueError("days is required when generate_with_ai is False")
        return self


class ItineraryResponse(BaseModel):
    """Response payload representing a saved itinerary."""

    trip_id: int
    itinerary: List[DayActivity]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message: str = "Itinerary created successfully"

    class Config:
        from_attributes = True


class LLMDayOutput(BaseModel):
    """Represents a single day in an LLM-generated itinerary response."""

    day: int = Field(..., ge=1)
    activities: List[str] = Field(..., min_length=3, max_length=5)

    @field_validator("activities", mode="after")
    @classmethod
    def validate_activities(cls, value: List[str]) -> List[str]:
        """Strip whitespace from each activity and reject empty entries.

        Args:
            value: The list of activity strings produced by the LLM.

        Returns:
            The list of stripped activity strings.

        Raises:
            ValueError: If any activity is empty after stripping whitespace.
        """
        stripped = [activity.strip() for activity in value]
        if any(not activity for activity in stripped):
            raise ValueError("each activity must be a non-empty string")
        return stripped


class LLMItineraryOutput(BaseModel):
    """Represents the full structured itinerary returned by the LLM.

    This model is used exclusively for validating and parsing the raw LLM
    response before saving to the database.
    """

    days: List[LLMDayOutput] = Field(..., min_length=1)

    @field_validator("days", mode="after")
    @classmethod
    def validate_sequential_days(cls, value: List[LLMDayOutput]) -> List[LLMDayOutput]:
        """Ensure day numbers are sequential starting from 1, with no gaps or duplicates.

        Args:
            value: The list of validated LLMDayOutput entries.

        Returns:
            The same list of days, unchanged.

        Raises:
            ValueError: If the day numbers are not exactly 1..N in order.
        """
        expected = list(range(1, len(value) + 1))
        actual = [day.day for day in value]
        if actual != expected:
            raise ValueError(
                f"day numbers must be sequential starting from 1 with no gaps or "
                f"duplicates, got {actual}"
            )
        return value
