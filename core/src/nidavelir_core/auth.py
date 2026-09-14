from __future__ import annotations

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import SecretStr
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .settings import Settings

PUBLIC_PATHS = {"/health", "/ready"}


def _secret(settings_value: SecretStr | None) -> str | None:
    if settings_value is None:
        return None
    value = settings_value.get_secret_value().strip()
    return value or None


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self._tokens = tuple(
            token
            for token in (
                _secret(settings.operator_token),
                _secret(settings.service_token),
            )
            if token is not None
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS or not self._tokens:
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        scheme, _, credential = authorization.partition(" ")
        authorized = scheme.lower() == "bearer" and any(
            hmac.compare_digest(credential, token) for token in self._tokens
        )
        if not authorized:
            return JSONResponse(
                status_code=401,
                content={"detail": "operator authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
