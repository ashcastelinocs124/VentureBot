import json
import os

import pytest
from fastapi.testclient import TestClient

# Ensure the test database is isolated
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TEST_DB_PATH = os.path.abspath(os.path.join(DATA_DIR, "test_prompt_cache.sqlite3"))
os.environ.setdefault("VENTUREBOTS_DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")

from services.api_gateway.app.main import app  # noqa: E402
from services.api_gateway.app.database import SessionLocal, init_db, engine  # noqa: E402
from services.api_gateway.app.models import ChatSession, JourneyStage  # noqa: E402
from services.orchestrator.flows.staged_journey_flow import StagedJourneyExecutor  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    engine.dispose()
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    # Recreate tables for each test to ensure isolation
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_session(client: TestClient) -> str:
    response = client.post("/api/chat/sessions", json={"title": "Cache Test", "auto_start": False})
    assert response.status_code == 201
    return response.json()["session"]["id"]


def test_cached_prompt_endpoint_returns_cached_prompt(client: TestClient):
    session_id = _create_session(client)

    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        session.stage_context = json.dumps({"builder_prompt": "cached prompt value"})
        db.commit()

    response = client.get(f"/api/chat/sessions/{session_id}/cached_prompt")
    assert response.status_code == 200
    payload = response.json()
    assert payload["prompt"] == "cached prompt value"
    assert payload["session_id"] == session_id


def test_prompt_engineering_uses_cached_prompt_without_rerun(monkeypatch, client: TestClient):
    # Fail the test if the executor tries to run the prompt-engineering task
    monkeypatch.setattr(
        StagedJourneyExecutor,
        "_run_task",
        lambda *args, **kwargs: pytest.fail("Should not run task when cached"),
    )

    session_id = _create_session(client)

    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        session.stage_context = json.dumps({"builder_prompt": "cached prompt value"})
        session.current_stage = JourneyStage.PROMPT_ENGINEERING.value
        db.commit()

    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"role": "user", "content": "Generate prompts"},
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["assistant_message"]["content"] == "cached prompt value"
    assert payload["session"]["current_stage"] == JourneyStage.COMPLETE.value
