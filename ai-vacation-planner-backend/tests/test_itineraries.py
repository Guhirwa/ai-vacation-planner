"""Tests for itinerary creation: manual mode, AI mode (mocked), and ownership."""


def _create_trip(client, auth_headers, **overrides):
    payload = {"destination": "Nairobi", "days": 2, "budget": 800.0, "trip_style": "adventure"}
    payload.update(overrides)
    return client.post("/trips/", json=payload, headers=auth_headers).json()


def test_create_manual_itinerary(client, auth_headers):
    trip = _create_trip(client, auth_headers)
    response = client.post(
        "/itineraries",
        json={
            "trip_id": trip["id"],
            "generate_with_ai": False,
            "days": [
                {"day": 1, "activities": ["Nairobi National Park", "Giraffe Centre"]},
                {"day": 2, "activities": ["Karen Blixen Museum"]},
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["itinerary"]) == 2


def test_itinerary_requires_trip_to_exist(client, auth_headers):
    response = client.post(
        "/itineraries",
        json={"trip_id": 999999, "generate_with_ai": False, "days": [{"day": 1, "activities": ["x"]}]},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_itinerary_rejects_duplicate_for_same_trip(client, auth_headers):
    trip = _create_trip(client, auth_headers)
    payload = {
        "trip_id": trip["id"],
        "generate_with_ai": False,
        "days": [{"day": 1, "activities": ["x"]}],
    }
    client.post("/itineraries", json=payload, headers=auth_headers)
    response = client.post("/itineraries", json=payload, headers=auth_headers)
    assert response.status_code == 400


def test_itinerary_for_another_users_trip_is_forbidden(client, auth_headers):
    trip = _create_trip(client, auth_headers)

    password = "TestPass123!"
    client.post(
        "/auth/register",
        json={"email": "olivier.mucyo@example.com", "username": "oliviermucyo", "password": password},
    )
    login = client.post(
        "/auth/login", json={"email": "olivier.mucyo@example.com", "password": password}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/itineraries",
        json={"trip_id": trip["id"], "generate_with_ai": False, "days": [{"day": 1, "activities": ["x"]}]},
        headers=other_headers,
    )
    assert response.status_code == 403


def test_ai_generated_itinerary_uses_the_mocked_model(client, auth_headers, mock_anthropic):
    mock_anthropic["text"] = (
        '{"days": ['
        '{"day": 1, "activities": ["Visit the market", "Try local food", "Walk the old town"]}'
        "]}"
    )
    trip = _create_trip(client, auth_headers)
    response = client.post(
        "/itineraries",
        json={"trip_id": trip["id"], "generate_with_ai": True},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["itinerary"][0]["day"] == 1
    assert "Visit the market" in body["itinerary"][0]["activities"]


def test_ai_generated_itinerary_fails_cleanly_on_invalid_model_output(client, auth_headers, mock_anthropic):
    mock_anthropic["text"] = "not valid json at all"
    trip = _create_trip(client, auth_headers)
    response = client.post(
        "/itineraries",
        json={"trip_id": trip["id"], "generate_with_ai": True},
        headers=auth_headers,
    )
    assert response.status_code == 500


def test_get_itinerary(client, auth_headers):
    trip = _create_trip(client, auth_headers)
    client.post(
        "/itineraries",
        json={
            "trip_id": trip["id"],
            "generate_with_ai": False,
            "days": [{"day": 1, "activities": ["Relax"]}],
        },
        headers=auth_headers,
    )
    response = client.get(f"/itineraries/{trip['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["itinerary"][0]["activities"] == ["Relax"]
