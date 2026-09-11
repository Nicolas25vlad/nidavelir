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


def create_task(client: TestClient, **overrides) -> dict:
    payload = {
        "title": "Make Nidavelir useful",
        "description": "Ship the persistent task API.",
        "repository": "Nicolas25vlad/nidavelir",
        "base_branch": "main",
        "acceptance_criteria": ["task survives a new database session"],
        **overrides,
    }
    response = client.post("/tasks", json=payload)
    assert response.status_code == 201
    return response.json()


def test_task_crud_survives_new_sessions(client: TestClient) -> None:
    created = create_task(client)
    task_id = created["id"]

    assert created["state"] == "BACKLOG"
    assert created["transitions"] == []
    assert created["merge_commit_sha"] is None
    assert created["supervisor_client"] is None

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


def test_supervisor_metadata_is_durable_and_filterable(client: TestClient) -> None:
    codex = create_task(
        client,
        title="Supervisor A task",
        supervisor_client="codex",
        supervisor_session_id="codex-chat-a",
        project_id="nidavelir",
    )
    create_task(
        client,
        title="Supervisor B task",
        supervisor_client="codex",
        supervisor_session_id="codex-chat-b",
        project_id="other-project",
    )

    fetched = client.get(f"/tasks/{codex['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["supervisor_client"] == "codex"
    assert fetched.json()["supervisor_session_id"] == "codex-chat-a"
    assert fetched.json()["project_id"] == "nidavelir"

    by_session = client.get("/tasks", params={"supervisor_session_id": "codex-chat-a"})
    assert by_session.status_code == 200
    assert [task["id"] for task in by_session.json()] == [codex["id"]]

    by_project = client.get("/tasks", params={"project_id": "nidavelir"})
    assert by_project.status_code == 200
    assert [task["id"] for task in by_project.json()] == [codex["id"]]

    unfiltered = client.get("/tasks")
    assert unfiltered.status_code == 200
    assert len(unfiltered.json()) == 2


def test_controlled_lifecycle_states_cannot_be_forced(client: TestClient) -> None:
    task = create_task(client)

    for state in ["AGENT_DONE", "VALIDATING", "APPROVED", "MERGED", "CLOSED"]:
        response = client.post(
            f"/tasks/{task['id']}/transitions",
            json={"state": state, "reason": "bypass"},
        )
        assert response.status_code == 409
        assert "controlled by execution" in response.json()["detail"]


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
