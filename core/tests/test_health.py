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
