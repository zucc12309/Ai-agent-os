from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas import AuditLogResponse
from app.services.auth_service import get_current_agent
from app.services.audit_service import list_audit_logs
from app.services.redaction import redact_payload

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def get_audit_logs(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    agent_filter = None if current_agent.is_admin else current_agent.id
    logs = await list_audit_logs(db, agent_id=agent_filter, limit=200)
    return [
        AuditLogResponse(
            id=log.id,
            agent_id=log.agent_id,
            tool_id=log.tool_id,
            tool_name=log.tool_name,
            input_payload=redact_payload(log.input_payload),
            output_payload=redact_payload(log.output_payload),
            status=log.status,
            error_message=log.error_message,
            approval_status=log.approval_status,
            execution_time_ms=log.execution_time_ms,
            event_hash=log.event_hash,
            previous_event_hash=log.previous_event_hash,
            created_at=log.created_at,
        )
        for log in logs
    ]
