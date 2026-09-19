from __future__ import annotations

import re

import docker
from docker.errors import DockerException, NotFound

from nidavelir_core.settings import Settings

AUTH_MOUNTS = {
    "codex": "/home/nidavelir/.codex",
    "cursor": "/home/nidavelir/.cursor",
}


def _namespace(settings: Settings) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", settings.installation_id.lower()).strip("-")
    return (value or "development")[:24].rstrip("-")


def auth_volume_name(settings: Settings, harness: str) -> str:
    if harness not in AUTH_MOUNTS:
        raise ValueError(f"unsupported harness: {harness}")
    return f"nidavelir-{_namespace(settings)}-{harness}-auth"


def api_key_configured(settings: Settings, harness: str) -> bool:
    if harness == "codex":
        return settings.openai_api_key is not None
    if harness == "cursor":
        return settings.cursor_api_key is not None
    return False


def persistent_auth_available(settings: Settings, harness: str) -> bool:
    if harness not in AUTH_MOUNTS:
        return False
    client = None
    try:
        client = docker.from_env()
        client.volumes.get(auth_volume_name(settings, harness))
        return True
    except (DockerException, NotFound):
        return False
    finally:
        if client is not None:
            try:
                client.close()
            except DockerException:
                pass


def harness_configured(settings: Settings, harness: str) -> bool:
    return api_key_configured(settings, harness) or persistent_auth_available(settings, harness)


def agent_auth_environment(settings: Settings, harness: str) -> dict[str, str]:
    if persistent_auth_available(settings, harness):
        if harness == "codex":
            return {"CODEX_HOME": AUTH_MOUNTS["codex"]}
        if harness == "cursor":
            return {"CURSOR_CONFIG_DIR": AUTH_MOUNTS["cursor"]}
        return {}

    if harness == "codex" and settings.openai_api_key is not None:
        return {"OPENAI_API_KEY": settings.openai_api_key.get_secret_value()}
    if harness == "cursor" and settings.cursor_api_key is not None:
        return {"CURSOR_API_KEY": settings.cursor_api_key.get_secret_value()}
    return {}


def agent_auth_volumes(settings: Settings, harness: str) -> dict[str, dict[str, str]]:
    if not persistent_auth_available(settings, harness):
        return {}
    return {
        auth_volume_name(settings, harness): {
            "bind": AUTH_MOUNTS[harness],
            "mode": "rw",
        }
    }
