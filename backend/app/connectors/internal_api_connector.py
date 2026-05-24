from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.schemas.tool_schema import InternalApiInput, InternalApiOutput


class InternalApiConnector:
    connector_type = "internal_api"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _build_safe_url(self, path: str) -> str:
        if not self.settings.internal_api_base_url:
            raise ValueError("Internal API base URL is not configured.")

        if not path or not path.startswith("/"):
            raise ValueError("Internal API paths must be relative and start with '/'.")
        if any(marker in path for marker in ("..", "://", "//", "\\", "#", "?")):
            raise ValueError("Internal API paths cannot contain traversal or absolute URL markers.")

        base_url = self.settings.internal_api_base_url.strip()
        parsed_base = urlparse(base_url)
        if not parsed_base.scheme or not parsed_base.netloc:
            raise ValueError("Internal API base URL must be an absolute URL.")

        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    async def call_internal_api(
        self,
        session: AsyncSession,
        payload: InternalApiInput,
    ) -> dict[str, Any]:
        if not self.settings.internal_api_base_url:
            response = InternalApiOutput(
                method=payload.method.upper(),
                path=payload.path,
                status_code=503,
                response=None,
                note=(
                    "No INTERNAL_API_BASE_URL configured. Set the env var to enable real calls."
                ),
            )
            return response.model_dump(mode="json")

        method = payload.method.upper()
        if payload.headers:
            raise ValueError("User-supplied headers are not allowed for internal API calls.")

        url = self._build_safe_url(payload.path)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.request(
                method=method,
                url=url,
                params=payload.query_params,
                json=payload.json_body if payload.json_body else None,
            )

        try:
            body: Any = response.json()
        except ValueError:
            body = response.text

        result = InternalApiOutput(
            method=method,
            path=payload.path,
            status_code=response.status_code,
            response=body,
            note="Internal API call completed.",
        )
        return result.model_dump(mode="json")
