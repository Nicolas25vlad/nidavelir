import asyncio

from nidavelir_mcp.auth import CONTROL_SCOPE, StaticTokenVerifier, server_auth_kwargs
from nidavelir_mcp.settings import Settings


def test_static_token_verifier_accepts_only_exact_token() -> None:
    verifier = StaticTokenVerifier("secret-token", "https://nidavelir.example/mcp")

    accepted = asyncio.run(verifier.verify_token("secret-token"))
    rejected = asyncio.run(verifier.verify_token("secret-tokeN"))

    assert accepted is not None
    assert accepted.client_id == "nidavelir-operator"
    assert accepted.scopes == [CONTROL_SCOPE]
    assert accepted.resource == "https://nidavelir.example/mcp"
    assert rejected is None


def test_auth_kwargs_are_disabled_without_token() -> None:
    settings = Settings(auth_token=None)
    assert server_auth_kwargs(settings) == {}


def test_auth_kwargs_configure_resource_server() -> None:
    settings = Settings(
        auth_token="secret-token",
        resource_url="https://nidavelir.example/mcp",
        issuer_url="https://nidavelir.example",
    )

    kwargs = server_auth_kwargs(settings)

    assert kwargs["token_verifier"] is not None
    assert str(kwargs["auth"].resource_server_url) == "https://nidavelir.example/mcp"
    assert kwargs["auth"].required_scopes == [CONTROL_SCOPE]
