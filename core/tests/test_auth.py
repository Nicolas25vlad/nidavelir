from fastapi import FastAPI
from fastapi.testclient import TestClient

from nidavelir_core.auth import BearerAuthMiddleware
from nidavelir_core.settings import Settings


def _client(*, operator_token: str | None, service_token: str | None) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        BearerAuthMiddleware,
        settings=Settings(
            env="test",
            operator_token=operator_token,
            service_token=service_token,
        ),
    )

    @app.get("/tasks")
    def tasks() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/ready")
    def ready() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_control_plane_rejects_anonymous_requests() -> None:
    with _client(operator_token="operator", service_token="service") as client:
        response = client.get("/tasks")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_operator_and_service_tokens_are_independently_accepted() -> None:
    with _client(operator_token="operator", service_token="service") as client:
        operator = client.get("/tasks", headers={"Authorization": "Bearer operator"})
        service = client.get("/tasks", headers={"Authorization": "Bearer service"})
        invalid = client.get("/tasks", headers={"Authorization": "Bearer nope"})

    assert operator.status_code == 200
    assert service.status_code == 200
    assert invalid.status_code == 401


def test_health_and_ready_stay_public_for_probes() -> None:
    with _client(operator_token="operator", service_token="service") as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code == 200


def test_auth_can_remain_disabled_for_local_development() -> None:
    with _client(operator_token=None, service_token=None) as client:
        response = client.get("/tasks")

    assert response.status_code == 200
