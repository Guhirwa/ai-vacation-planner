"""Tests for the structured-output validation schemas used to gate raw LLM output."""

import pytest
from pydantic import ValidationError

from app.schemas.itinerary import LLMDayOutput, LLMItineraryOutput
from app.schemas.voice import TripDetailsFromVoice


def test_llm_day_output_accepts_three_to_five_activities():
    day = LLMDayOutput(day=1, activities=["a", "b", "c"])
    assert len(day.activities) == 3


def test_llm_day_output_rejects_fewer_than_three_activities():
    with pytest.raises(ValidationError):
        LLMDayOutput(day=1, activities=["a", "b"])


def test_llm_day_output_rejects_more_than_five_activities():
    with pytest.raises(ValidationError):
        LLMDayOutput(day=1, activities=["a", "b", "c", "d", "e", "f"])


def test_llm_day_output_rejects_an_empty_activity_after_stripping():
    with pytest.raises(ValidationError):
        LLMDayOutput(day=1, activities=["a", "b", "   "])


def test_llm_itinerary_output_requires_sequential_days_starting_at_one():
    with pytest.raises(ValidationError):
        LLMItineraryOutput(
            days=[
                {"day": 1, "activities": ["a", "b", "c"]},
                {"day": 3, "activities": ["a", "b", "c"]},
            ]
        )


def test_llm_itinerary_output_accepts_sequential_days():
    output = LLMItineraryOutput(
        days=[
            {"day": 1, "activities": ["a", "b", "c"]},
            {"day": 2, "activities": ["a", "b", "c"]},
        ]
    )
    assert len(output.days) == 2


def test_trip_details_from_voice_rejects_zero_days():
    with pytest.raises(ValidationError):
        TripDetailsFromVoice(
            destination="Tokyo",
            days=0,
            budget=1000,
            trip_style="comfort",
            raw_transcript="x",
        )


def test_trip_details_from_voice_rejects_negative_budget():
    with pytest.raises(ValidationError):
        TripDetailsFromVoice(
            destination="Tokyo",
            days=5,
            budget=-100,
            trip_style="comfort",
            raw_transcript="x",
        )


def test_trip_details_from_voice_rejects_an_unknown_trip_style():
    with pytest.raises(ValidationError):
        TripDetailsFromVoice(
            destination="Tokyo",
            days=5,
            budget=1000,
            trip_style="fancy",
            raw_transcript="x",
        )


def test_trip_details_from_voice_accepts_valid_data():
    details = TripDetailsFromVoice(
        destination="Tokyo",
        days=5,
        budget=2000,
        trip_style="comfort",
        raw_transcript="I want to go to Tokyo",
    )
    assert details.fields_defaulted == []
