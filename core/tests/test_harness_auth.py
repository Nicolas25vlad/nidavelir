from nidavelir_core.execution import harness_auth
from nidavelir_core.settings import Settings


def settings(**values) -> Settings:
    return Settings(_env_file=None, installation_id="Test Install", **values)


def test_auth_volumes_are_namespaced_per_harness(monkeypatch):
    cfg = settings()
    monkeypatch.setattr(harness_auth, "persistent_auth_available", lambda _s, _h: True)

    codex = harness_auth.agent_auth_volumes(cfg, "codex")
    cursor = harness_auth.agent_auth_volumes(cfg, "cursor")

    assert codex == {
        "nidavelir-test-install-codex-auth": {
            "bind": "/home/nidavelir/.codex",
            "mode": "rw",
        }
    }
    assert cursor == {
        "nidavelir-test-install-cursor-auth": {
            "bind": "/home/nidavelir/.cursor",
            "mode": "rw",
        }
    }


def test_persistent_codex_auth_hides_api_key(monkeypatch):
    cfg = settings(openai_api_key="secret-key")
    monkeypatch.setattr(harness_auth, "persistent_auth_available", lambda _s, _h: True)

    environment = harness_auth.agent_auth_environment(cfg, "codex")

    assert environment == {"CODEX_HOME": "/home/nidavelir/.codex"}
    assert "OPENAI_API_KEY" not in environment


def test_api_key_is_fallback_when_persistent_auth_is_absent(monkeypatch):
    cfg = settings(openai_api_key="openai-secret", cursor_api_key="cursor-secret")
    monkeypatch.setattr(harness_auth, "persistent_auth_available", lambda _s, _h: False)

    assert harness_auth.agent_auth_environment(cfg, "codex") == {
        "OPENAI_API_KEY": "openai-secret"
    }
    assert harness_auth.agent_auth_environment(cfg, "cursor") == {
        "CURSOR_API_KEY": "cursor-secret"
    }


def test_harness_configured_accepts_persistent_login(monkeypatch):
    cfg = settings()
    monkeypatch.setattr(
        harness_auth,
        "persistent_auth_available",
        lambda _s, harness: harness == "cursor",
    )

    assert not harness_auth.harness_configured(cfg, "codex")
    assert harness_auth.harness_configured(cfg, "cursor")
