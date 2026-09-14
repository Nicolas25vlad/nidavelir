from __future__ import annotations

from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import SessionLocal
from .settings import Settings


def _database_ready() -> tuple[bool, str]:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True, "reachable"
    except SQLAlchemyError as error:
        return False, error.__class__.__name__


def _docker_ready(worker_image: str) -> tuple[bool, str, bool, str]:
    client = None
    try:
        client = docker.from_env()
        client.ping()
        try:
            client.images.get(worker_image)
        except ImageNotFound:
            return True, "reachable", False, "worker image missing"
        return True, "reachable", True, "available"
    except DockerException as error:
        return False, error.__class__.__name__, False, "docker unavailable"
    finally:
        if client is not None:
            try:
                client.close()
            except DockerException:
                pass


def readiness_report(settings: Settings) -> tuple[bool, dict[str, Any]]:
    database_ok, database_detail = _database_ready()
    docker_ok, docker_detail, image_ok, image_detail = _docker_ready(settings.worker_image)
    ready = database_ok and docker_ok and image_ok
    return ready, {
        "status": "ready" if ready else "not_ready",
        "service": "nidavelir-core",
        "installation_id": settings.installation_id,
        "components": {
            "database": {"ready": database_ok, "detail": database_detail},
            "docker": {"ready": docker_ok, "detail": docker_detail},
            "worker_image": {
                "ready": image_ok,
                "detail": image_detail,
                "image": settings.worker_image,
            },
        },
    }
