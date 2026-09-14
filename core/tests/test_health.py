from fastapi.testclient import TestClient

from nidavelir_core.main import app


def test_health_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("NIDAVELIR_ENV", "test")

    from nidavelir_core.settings import get_settings

    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "nidavelir-core",
        "environment": "test",
    }

    get_settings.cache_clear()


def test_ready_endpoint_reports_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        "nidavelir_core.main.readiness_report",
        lambda settings: (
            True,
            {
                "status": "ready",
                "service": "nidavelir-core",
                "installation_id": settings.installation_id,
                "components": {
                    "database": {"ready": True, "detail": "reachable"},
                    "docker": {"ready": True, "detail": "reachable"},
                    "worker_image": {
                        "ready": True,
                        "detail": "available",
                        "image": settings.worker_image,
                    },
                },
            },
        ),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["components"]["database"]["ready"] is True
    assert payload["components"]["docker"]["ready"] is True
    assert payload["components"]["worker_image"]["ready"] is True


def test_ready_endpoint_returns_503_when_dependency_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        "nidavelir_core.main.readiness_report",
        lambda settings: (
            False,
            {
                "status": "not_ready",
                "service": "nidavelir-core",
                "installation_id": settings.installation_id,
                "components": {
                    "database": {"ready": False, "detail": "OperationalError"},
                    "docker": {"ready": True, "detail": "reachable"},
                    "worker_image": {
                        "ready": False,
                        "detail": "worker image missing",
                        "image": settings.worker_image,
                    },
                },
            },
        ),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["components"]["database"]["ready"] is False
    assert payload["components"]["worker_image"]["ready"] is False
