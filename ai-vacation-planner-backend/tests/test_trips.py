"""Tests for trip CRUD and per-user ownership."""


def _create_trip(client, auth_headers, **overrides):
    payload = {
        "destination": "Kyoto",
        "days": 4,
        "budget": 1500.0,
        "trip_style": "family",
    }
    payload.update(overrides)
    return client.post("/trips/", json=payload, headers=auth_headers)


def test_create_trip(client, auth_headers):
    response = _create_trip(client, auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["destination"] == "Kyoto"
    assert body["days"] == 4


def test_create_trip_requires_auth(client):
    response = client.post(
        "/trips/",
        json={"destination": "Kyoto", "days": 4, "budget": 1500.0, "trip_style": "family"},
    )
    assert response.status_code == 403


def test_create_trip_rejects_invalid_style(client, auth_headers):
    response = _create_trip(client, auth_headers, trip_style="fancy")
    assert response.status_code == 422


def test_list_trips_returns_only_the_current_users_trips(client, auth_headers):
    _create_trip(client, auth_headers)
    _create_trip(client, auth_headers, destination="Oslo")

    other_user_headers = _register_and_login(client, "joseph.ishimwe@example.com", "josephishimwe")
    _create_trip(client, other_user_headers, destination="Lisbon")

    response = client.get("/trips/", headers=auth_headers)
    assert response.status_code == 200
    destinations = {trip["destination"] for trip in response.json()}
    assert destinations == {"Kyoto", "Oslo"}


def test_get_trip_by_id(client, auth_headers):
    created = _create_trip(client, auth_headers).json()
    response = client.get(f"/trips/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_trip_owned_by_another_user_is_not_found(client, auth_headers):
    created = _create_trip(client, auth_headers).json()
    other_user_headers = _register_and_login(client, "bertin.ndahayo@example.com", "bertinndahayo")
    response = client.get(f"/trips/{created['id']}", headers=other_user_headers)
    assert response.status_code == 404


def test_update_trip(client, auth_headers):
    created = _create_trip(client, auth_headers).json()
    response = client.put(
        f"/trips/{created['id']}", json={"budget": 2000.0}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["budget"] == 2000.0


def test_delete_trip(client, auth_headers):
    created = _create_trip(client, auth_headers).json()
    response = client.delete(f"/trips/{created['id']}", headers=auth_headers)
    assert response.status_code == 200

    follow_up = client.get(f"/trips/{created['id']}", headers=auth_headers)
    assert follow_up.status_code == 404


def _register_and_login(client, email, username):
    password = "TestPass123!"
    client.post(
        "/auth/register", json={"email": email, "username": username, "password": password}
    )
    login_response = client.post("/auth/login", json={"email": email, "password": password})
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
