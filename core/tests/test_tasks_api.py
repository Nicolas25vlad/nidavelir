from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base, get_session
from nidavelir_core.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    def override_session() -> Iterator[Session]:
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_task(client: TestClient) -> dict:
    response = client.post(
        "/tasks",
        json={
            "title": "Make Nidavelir useful",
            "description": "Ship the persistent task API.",
            "repository": "Nicolas25vlad/nidavelir",
            "base_branch": "main",
            "acceptance_criteria": ["task survives a new database session"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_task_crud_survives_new_sessions(client: TestClient) -> None:
    created = create_task(client)
    task_id = created["id"]

    assert created["state"] == "BACKLOG"
    assert created["transitions"] == []

    fetched = client.get(f"/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Make Nidavelir useful"

    updated = client.patch(
        f"/tasks/{task_id}",
        json={"title": "Make Nidavelir self-host itself"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Make Nidavelir self-host itself"

    listed = client.get("/tasks")
    assert listed.status_code == 200
    assert [task["id"] for task in listed.json()] == [task_id]


def test_full_lifecycle_persists_transition_history(client: TestClient) -> None:
    task = create_task(client)
    task_id = task["id"]
    lifecycle = [
        "QUEUED",
        "RUNNING",
        "AGENT_DONE",
        "VALIDATING",
        "APPROVED",
        "MERGED",
        "CLOSED",
    ]

    for state in lifecycle:
        response = client.post(
            f"/tasks/{task_id}/transitions",
            json={"state": state, "reason": f"move to {state}"},
        )
        assert response.status_code == 200
        assert response.json()["state"] == state

    persisted = client.get(f"/tasks/{task_id}").json()
    assert persisted["state"] == "CLOSED"
    assert [event["to_state"] for event in persisted["transitions"]] == lifecycle


def test_invalid_transition_returns_conflict(client: TestClient) -> None:
    task = create_task(client)

    response = client.post(
        f"/tasks/{task['id']}/transitions",
        json={"state": "RUNNING"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["current_state"] == "BACKLOG"
    assert "QUEUED" in response.json()["detail"]["allowed_states"]


def test_cancel_task_is_a_durable_transition(client: TestClient) -> None:
    task = create_task(client)

    response = client.delete(f"/tasks/{task['id']}")
    assert response.status_code == 204

    persisted = client.get(f"/tasks/{task['id']}").json()
    assert persisted["state"] == "CANCELLED"
    assert persisted["transitions"][0]["to_state"] == "CANCELLED"
