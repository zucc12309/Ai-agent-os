from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas import AuthSessionResponse
from app.services.auth_service import (
    SESSION_COOKIE_NAME,
    authenticate_api_key_value,
    build_auth_session_response,
    clear_session_cookie,
    create_session_token,
    set_session_cookie,
    verify_session_token,
)

router = APIRouter(tags=["auth"])


@router.get("/auth/session", response_model=AuthSessionResponse)
async def read_session(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    try:
        agent_id, expires_at = verify_session_token(session_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

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
    response.headers["Cache-Control"] = "no-store"
    return build_auth_session_response(agent, expires_at)


@router.post("/auth/session", response_model=AuthSessionResponse)
async def create_session(
    response: Response,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header.")

    agent = await authenticate_api_key_value(x_api_key, db)
    token, expires_at = create_session_token(agent, now=datetime.now(timezone.utc))
    set_session_cookie(response, token, expires_at)
    response.headers["Cache-Control"] = "no-store"
    return build_auth_session_response(agent, expires_at)


@router.delete("/auth/session", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(response: Response) -> None:
    clear_session_cookie(response)
    response.headers["Cache-Control"] = "no-store"
