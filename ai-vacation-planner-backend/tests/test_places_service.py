"""Tests for the shared Nominatim place-search helper, including its retry behavior."""

import httpx
import pytest

from app.guardrails.input_guardrails import InvalidSearchTerm
from app.services.places_service import search_places


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_search_places_rejects_invalid_input_without_any_network_call(monkeypatch):
    async def _should_not_be_called(*args, **kwargs):
        raise AssertionError("network call should not happen for invalid input")

    monkeypatch.setattr(httpx.AsyncClient, "get", _should_not_be_called)

    with pytest.raises(InvalidSearchTerm):
        await search_places("Paris}{&bad", "museum")


@pytest.mark.asyncio
async def test_search_places_succeeds_on_the_first_try(monkeypatch):
    call_count = {"n": 0}

    async def _fake_get(self, *args, **kwargs):
        call_count["n"] += 1
        return _FakeResponse([{"display_name": "Louvre Museum, Paris"}])

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

    names = await search_places("Paris", "museum")
    assert names == ["Louvre Museum, Paris"]
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_search_places_retries_after_a_timeout_then_succeeds(monkeypatch):
    call_count = {"n": 0}

    async def _fake_get(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ReadTimeout("simulated timeout")
        return _FakeResponse([{"display_name": "Eiffel Tower, Paris"}])

    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
    monkeypatch.setattr("app.services.places_service.PLACE_SEARCH_RETRY_DELAY_SECONDS", 0)

    names = await search_places("Paris", "landmark")
    assert names == ["Eiffel Tower, Paris"]
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_search_places_returns_empty_after_exhausting_all_retries(monkeypatch):
    call_count = {"n": 0}

    async def _always_fails(self, *args, **kwargs):
        call_count["n"] += 1
        raise httpx.ReadTimeout("simulated timeout")

    monkeypatch.setattr(httpx.AsyncClient, "get", _always_fails)
    monkeypatch.setattr("app.services.places_service.PLACE_SEARCH_RETRY_DELAY_SECONDS", 0)

    names = await search_places("Paris", "museum")
    assert names == []
    from app.services.places_service import PLACE_SEARCH_RETRIES
    assert call_count["n"] == PLACE_SEARCH_RETRIES + 1
