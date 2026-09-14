from __future__ import annotations

from typing import Any

import docker
from docker.errors import DockerException, NotFound

from nidavelir_core.settings import Settings

AUTH_MOUNTS = {
    "codex": "/home/nidavelir/.codex",
    "cursor": "/home/nidavelir/.cursor",
}


def auth_volume_name(settings: Settings, harness: str) -> str:
    if harness == "codex":
        return settings.codex_auth_volume
    if harness == "cursor":
        return settings.cursor_auth_volume
    raise ValueError(f"unsupported harness {harness!r}")


def api_key_configured(settings: Settings, harness: str) -> bool:
    if harness == "codex":
        return settings.openai_api_key is not None
    if harness == "cursor":
        return settings.cursor_api_key is not None
    return False


def persistent_auth_available(
    settings: Settings,
    harness: str,
    *,
    client: Any | None = None,
) -> bool:
    own_client = client is None
    docker_client = client
    try:
        if docker_client is None:
            docker_client = docker.from_env()
        docker_client.volumes.get(auth_volume_name(settings, harness))
        return True
    except (DockerException, NotFound):
        return False
    finally:
        if own_client and docker_client is not None:
            try:
                docker_client.close()
            except DockerException:
                pass


def harness_configured(settings: Settings, harness: str) -> bool:
    return api_key_configured(settings, harness) or persistent_auth_available(settings, harness)


def agent_auth_environment(
    settings: Settings,
    harness: str,
    *,
    persistent_auth: bool,
) -> dict[str, str]:
    environment: dict[str, str] = {}
    if harness == "cursor":
        environment["CURSOR_CONFIG_DIR"] = AUTH_MOUNTS["cursor"]

    if persistent_auth:
        return environment

    if harness == "codex" and settings.openai_api_key is not None:
        environment["OPENAI_API_KEY"] = settings.openai_api_key.get_secret_value()
    elif harness == "cursor" and settings.cursor_api_key is not None:
        environment["CURSOR_API_KEY"] = settings.cursor_api_key.get_secret_value()
    return environment


def agent_auth_volumes(
    client: Any,
    settings: Settings,
    harness: str,
) -> dict[str, dict[str, str]]:
    volume_name = auth_volume_name(settings, harness)
    try:
        client.volumes.get(volume_name)
    except (DockerException, NotFound):
        return {}
    return {volume_name: {"bind": AUTH_MOUNTS[harness], "mode": "rw"}}
