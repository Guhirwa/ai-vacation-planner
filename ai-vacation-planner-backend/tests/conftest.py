"""
conftest.py

Shared pytest fixtures for the backend test suite.

Points the app at a fresh, file-based SQLite database (not the real
development database) before any app module is imported, so importing
app.main can never touch real data. Each test runs inside its own
transaction that is rolled back afterwards, so tests never leak state
into one another. All Anthropic calls are mocked by default so the main
suite never spends tokens or needs network access; the DeepEval suite
under tests/eval overrides this deliberately to call the real model.
"""

import os
import tempfile

_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_TEST_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key-not-real")

import pytest  # noqa: E402 (must come after the env vars above are set)
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine, get_database, session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    """Create every table once for the whole test run, then clean up the file."""
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    os.remove(_TEST_DB_PATH)


@pytest.fixture
def db_session():
    """A database session scoped to one test, rolled back afterwards."""
    connection = engine.connect()
    transaction = connection.begin()
    session = session_factory(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    """A FastAPI TestClient wired to the per-test database session."""

    def _override_get_database():
        yield db_session

    app.dependency_overrides[get_database] = _override_get_database
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Registers and logs in a real user through the actual auth endpoints.

    Returns an Authorization header dict ready to pass to client.get/post/etc.
    """
    email = "divin.araje@example.com"
    password = "TestPass123!"
    client.post(
        "/auth/register",
        json={"email": email, "username": "divinaraje", "password": password},
    )
    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Replaces every Anthropic call site with a canned response.

    Patches both the direct AsyncAnthropic clients (llm_service, speech_service)
    and the LangChain ChatAnthropic wrapper the agent graph uses, so no test
    in the main suite ever calls the real API or depends on network access.
    Returns a small object tests can configure to return a specific reply.
    """

    class _FakeUsage:
        input_tokens = 10
        output_tokens = 10

    class _FakeContentBlock:
        def __init__(self, text):
            self.text = text

    class _FakeMessage:
        def __init__(self, text):
            self.content = [_FakeContentBlock(text)]
            self.usage = _FakeUsage()

    class _FakeAIMessage:
        def __init__(self, text):
            self.content = text
            self.tool_calls = []
            self.usage_metadata = {"input_tokens": 10, "output_tokens": 10}

    state = {"text": '{"days": [{"day": 1, "activities": ["a", "b", "c"]}]}'}

    async def _fake_create(*args, **kwargs):
        return _FakeMessage(state["text"])

    async def _fake_ainvoke(self, messages, *args, **kwargs):
        return _FakeAIMessage(state["text"])

    monkeypatch.setattr(
        "app.services.llm_service._client.messages.create", _fake_create, raising=False
    )
    monkeypatch.setattr(
        "app.services.speech_service._anthropic_client.messages.create",
        _fake_create,
        raising=False,
    )
    monkeypatch.setattr(
        "langchain_anthropic.ChatAnthropic.ainvoke", _fake_ainvoke, raising=False
    )

    return state
