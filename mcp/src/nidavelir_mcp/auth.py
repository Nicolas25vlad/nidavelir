from __future__ import annotations

import hmac
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

from .settings import Settings

CONTROL_SCOPE = "nidavelir:control"


class StaticTokenVerifier(TokenVerifier):
    """Validate the appliance's single operator bearer token."""

    def __init__(self, token: str, resource_url: str) -> None:
        self._token = token
        self._resource_url = resource_url

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(
            token=token,
            client_id="nidavelir-operator",
            scopes=[CONTROL_SCOPE],
            resource=self._resource_url,
        )


def server_auth_kwargs(settings: Settings) -> dict[str, Any]:
    if settings.auth_token is None:
        return {}

    token = settings.auth_token.get_secret_value()
    return {
        "token_verifier": StaticTokenVerifier(token, settings.resource_url),
        "auth": AuthSettings(
            issuer_url=AnyHttpUrl(settings.issuer_url),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            required_scopes=[CONTROL_SCOPE],
            validate_token_resource=True,
        ),
    }
