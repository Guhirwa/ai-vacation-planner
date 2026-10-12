"""
test_itinerary_eval.py

DeepEval-based quality evaluation of the real itinerary-generation agent.

Unlike the main test suite, these tests call the real Claude API (both to
generate itineraries and to judge them), so they cost tokens and take
longer. They are marked @pytest.mark.eval and are never run by CI, run
them yourself with:

    pytest -m eval tests/eval -v
"""

import json
from pathlib import Path

import pytest
from deepeval.metrics import GEval
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.config import settings
from app.services.agent_service import generate_itinerary_with_agent

_GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
_FAKE_TRIP_ID = 999999  # no real trip needed, because the agent already has everything in the request text


def _load_golden_cases() -> list[dict]:
    with open(_GOLDEN_DATASET_PATH) as f:
        return json.load(f)


def _judge_model() -> AnthropicModel:
    """The model used to judge itinerary quality, reusing the same Anthropic key the app already uses."""
    return AnthropicModel(model=settings.agent_model, api_key=settings.anthropic_api_key)


def _build_relevance_metric() -> GEval:
    return GEval(
        name="Relevance",
        criteria=(
            "Determine whether the activities in the actual output are genuinely "
            "relevant to the destination, travel style, and budget described in "
            "the input. Activities should fit the destination (real, well-known "
            "or authentic local places), match the stated travel style (for "
            "example a 'luxury' trip should not suggest only free attractions, "
            "a 'budget' trip should not suggest expensive activities), and feel "
            "appropriate for the stated budget."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_judge_model(),
        threshold=0.7,
    )


def _build_completeness_metric() -> GEval:
    return GEval(
        name="Completeness",
        criteria=(
            "Determine whether the actual output covers every day requested in "
            "the input with no gaps, and whether each day has enough distinct "
            "activities to fill a full day (at least 3)."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_judge_model(),
        threshold=0.7,
    )


def _describe_request(case: dict) -> str:
    return (
        f"Plan a {case['days']}-day trip to {case['destination']} with a budget "
        f"of ${case['budget']:,.2f}, {case['trip_style']} style."
    )


def _describe_itinerary(days_list) -> str:
    lines = [
        f"Day {day.day}: " + ", ".join(day.activities)
        for day in days_list
    ]
    return "\n".join(lines)


@pytest.mark.eval
@pytest.mark.parametrize("case", _load_golden_cases(), ids=lambda c: c["name"])
@pytest.mark.asyncio
async def test_generated_itinerary_quality(case):
    days_list = await generate_itinerary_with_agent(
        trip_id=_FAKE_TRIP_ID,
        destination=case["destination"],
        days=case["days"],
        budget=case["budget"],
        trip_style=case["trip_style"],
    )

    # Validity/format: generate_itinerary_with_agent only returns successfully
    # when LLMItineraryOutput already validated the structure, re-asserted
    # here as an explicit sanity check rather than trusting that silently.
    assert len(days_list) == case["days"]
    assert [day.day for day in days_list] == list(range(1, case["days"] + 1))
    for day in days_list:
        assert 3 <= len(day.activities) <= 5

    test_case = LLMTestCase(
        input=_describe_request(case),
        actual_output=_describe_itinerary(days_list),
    )

    relevance = _build_relevance_metric()
    completeness = _build_completeness_metric()

    # a_measure (not the sync measure()) because deepeval's sync path patches
    # the event loop with nest_asyncio, which corrupts httpx/anthropic's
    # async backend detection for any async call made afterwards in the
    # same test run, like the next parametrized case's agent call.
    await relevance.a_measure(test_case)
    await completeness.a_measure(test_case)

    assert relevance.success, f"Relevance metric failed: {relevance.reason}"
    assert completeness.success, f"Completeness metric failed: {completeness.reason}"


@pytest.mark.eval
@pytest.mark.asyncio
async def test_relevance_metric_actually_discriminates():
    """Prove the relevance metric isn't a rubber stamp: a mismatched itinerary should fail it."""
    mismatched_case = LLMTestCase(
        input="Plan a 3-day trip to Tokyo with a budget of $2,000.00, comfort style.",
        actual_output=(
            "Day 1: Visit the Brandenburg Gate, walk through Tiergarten, dinner at a currywurst stand\n"
            "Day 2: Berlin Wall Memorial, East Side Gallery, Museum Island\n"
            "Day 3: Checkpoint Charlie, Berlin Cathedral, shopping on Kurfürstendamm"
        ),
    )
    relevance = _build_relevance_metric()
    await relevance.a_measure(mismatched_case)
    assert not relevance.success, (
        "Expected the relevance metric to fail on a Tokyo request answered with "
        f"an all-Berlin itinerary, but it passed with reason: {relevance.reason}"
    )
