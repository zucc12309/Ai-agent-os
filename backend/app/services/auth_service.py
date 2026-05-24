from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.agent import Agent
from app.schemas.auth_schema import AuthSessionResponse

settings = get_settings()
SESSION_COOKIE_NAME = settings.session_cookie_name
SESSION_MAX_AGE_SECONDS = settings.session_max_age_seconds


def _b64encode_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode_json(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid session payload.")
    return payload


def _sign_session_payload(payload_b64: str) -> str:
    digest = hmac.new(
        settings.session_signing_secret.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_session_token(agent: Agent, *, now: datetime | None = None) -> tuple[str, datetime]:
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=SESSION_MAX_AGE_SECONDS)
    payload = {
        "agent_id": str(agent.id),
        "exp": int(expires_at.timestamp()),
        "iat": int(issued_at.timestamp()),
    }
    payload_b64 = _b64encode_json(payload)
    signature = _sign_session_payload(payload_b64)
    return f"{payload_b64}.{signature}", expires_at


def verify_session_token(token: str) -> tuple[UUID, datetime]:
    payload_b64, signature = token.split(".", 1)
    expected_signature = _sign_session_payload(payload_b64)
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid session signature.")

    payload = _b64decode_json(payload_b64)
    agent_id_raw = str(payload.get("agent_id") or "")
    exp = int(payload.get("exp") or 0)
    if not agent_id_raw or exp <= 0:
        raise ValueError("Invalid session payload.")

    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise ValueError("Session has expired.")
    return UUID(agent_id_raw), expires_at


def set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        expires=expires_at,
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def build_auth_session_response(agent: Agent, expires_at: datetime) -> AuthSessionResponse:
    return AuthSessionResponse(
        authenticated=True,
        agent_id=agent.id,
        agent_name=agent.name,
        api_key_prefix=agent.api_key_prefix,
        is_admin=agent.is_admin,
        enabled=agent.enabled,
        session_expires_at=expires_at,
    )


def hash_api_key(api_key: str) -> str:
    """Hash an API key with the configured pepper."""

    settings = get_settings()
    raw = f"{settings.api_key_pepper}:{api_key}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def authenticate_api_key_value(api_key: str, db: AsyncSession) -> Agent:
    """Resolve an API key to an active agent."""

    hashed = hash_api_key(api_key)
    result = await db.execute(select(Agent).where(Agent.api_key_hash == hashed))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    if not agent.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent is disabled.")

    agent.last_used_at = datetime.now(timezone.utc)
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def get_current_agent(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """FastAPI dependency that authenticates an agent from a session cookie or API key header."""

    if x_api_key:
        return await authenticate_api_key_value(x_api_key, db)

    if session_token:
        try:
            agent_id, _expires_at = verify_session_token(session_token)
        except ValueError as exc:  # pragma: no cover - exercised by API tests.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")
        if not agent.enabled:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent is disabled.")

        agent.last_used_at = datetime.now(timezone.utc)
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        return agent

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing X-API-Key header.",
    )
