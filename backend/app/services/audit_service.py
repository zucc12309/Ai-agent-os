from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.services.redaction import redact_error_message, redact_payload


async def log_audit_event(
    session: AsyncSession,
    *,
    agent_id,
    tool_name: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any] | None,
    status: str,
    error_message: str | None,
    approval_status: str,
    execution_time_ms: int,
    tool_id=None,
) -> AuditLog:
    result = await session.execute(
        select(AuditLog.event_hash).order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(1)
    )
    previous_event_hash = result.scalar_one_or_none()
    redacted_input = redact_payload(jsonable_encoder(input_payload))
    redacted_output = redact_payload(jsonable_encoder(output_payload) if output_payload is not None else None)
    payload_for_hash = {
        "agent_id": str(agent_id),
        "tool_id": str(tool_id) if tool_id is not None else None,
        "tool_name": tool_name,
        "input_payload": redacted_input,
        "output_payload": redacted_output,
        "status": status,
        "error_message": redact_error_message(error_message),
        "approval_status": approval_status,
        "execution_time_ms": execution_time_ms,
        "previous_event_hash": previous_event_hash,
    }
    event_hash = hashlib.sha256(
        json.dumps(payload_for_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    audit_log = AuditLog(
        agent_id=agent_id,
        tool_id=tool_id,
        tool_name=tool_name,
        input_payload=redacted_input,
        output_payload=redacted_output,
        status=status,
        error_message=redact_error_message(error_message),
        approval_status=approval_status,
        execution_time_ms=execution_time_ms,
        event_hash=event_hash,
        previous_event_hash=previous_event_hash,
    )
    session.add(audit_log)
    await session.flush()
    await session.refresh(audit_log)
    return audit_log


async def list_audit_logs(
    session: AsyncSession,
    *,
    agent_id=None,
    limit: int = 100,
    tool_name: str | None = None,
) -> list[AuditLog]:
    stmt: Select[tuple[AuditLog]] = (
        select(AuditLog)
        .options(selectinload(AuditLog.tool))
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if agent_id is not None:
        stmt = stmt.where(AuditLog.agent_id == agent_id)
    if tool_name is not None:
        stmt = stmt.where(AuditLog.tool_name == tool_name)

    result = await session.execute(stmt)
    return list(result.scalars().all())
