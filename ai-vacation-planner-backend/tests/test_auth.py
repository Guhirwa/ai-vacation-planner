"""Tests for registration and login."""


def test_register_creates_a_user(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "gady.hirwa@example.com",
            "username": "gadyhirwa",
            "password": "TestPass123!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "gady.hirwa@example.com"
    assert body["username"] == "gadyhirwa"
    assert "id" in body


def test_register_rejects_a_duplicate_email(client):
    payload = {
        "email": "steven.cyubahiro@example.com",
        "username": "stevencyu",
        "password": "TestPass123!",
    }
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400


def test_login_succeeds_with_correct_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "prisca.masereri@example.com",
            "username": "priscamasereri",
            "password": "TestPass123!",
        },
    )
    response = client.post(
        "/auth/login",
        json={"email": "prisca.masereri@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_rejects_wrong_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "kelly.shema@example.com",
            "username": "kellyshema",
            "password": "TestPass123!",
        },
    )
    response = client.post(
        "/auth/login",
        json={"email": "kelly.shema@example.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


def test_me_requires_a_token(client):
    response = client.get("/users/me")
    assert response.status_code == 403


def test_me_returns_the_authenticated_user(client, auth_headers):
    response = client.get("/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "divin.araje@example.com"
