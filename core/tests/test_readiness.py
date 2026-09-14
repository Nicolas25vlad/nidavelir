from types import SimpleNamespace

from nidavelir_core.readiness import readiness_report
from nidavelir_core.settings import Settings


class FakeImages:
    def __init__(self, missing: bool = False) -> None:
        self.missing = missing

    def get(self, image: str):
        if self.missing:
            from docker.errors import ImageNotFound

            raise ImageNotFound(image)
        return object()


class FakeDockerClient:
    def __init__(self, *, missing_image: bool = False) -> None:
        self.images = FakeImages(missing_image)

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None


def test_readiness_report_is_ready(monkeypatch) -> None:
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return SimpleNamespace()

    monkeypatch.setattr("nidavelir_core.readiness.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        "nidavelir_core.readiness.docker.from_env", lambda: FakeDockerClient()
    )

    ready, report = readiness_report(Settings(env="test", installation_id="ci"))

    assert ready is True
    assert report["status"] == "ready"
    assert all(component["ready"] for component in report["components"].values())


def test_readiness_report_fails_when_worker_image_is_missing(monkeypatch) -> None:
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return SimpleNamespace()

    monkeypatch.setattr("nidavelir_core.readiness.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        "nidavelir_core.readiness.docker.from_env",
        lambda: FakeDockerClient(missing_image=True),
    )

    ready, report = readiness_report(Settings(env="test", installation_id="ci"))

    assert ready is False
    assert report["components"]["worker_image"]["ready"] is False
