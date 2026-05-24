from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import AgentToolPermission
from app.models.approval import ApprovalRequest
from app.services.redaction import redact_error_message, redact_payload


async def create_approval_request(
    session: AsyncSession,
    *,
    agent_id,
    tool_id,
    tool_name: str,
    input_payload: dict[str, Any],
    decision_reason: str | None = None,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        agent_id=agent_id,
        tool_id=tool_id,
        tool_name=tool_name,
        input_payload=jsonable_encoder(input_payload),
        approval_status="pending",
        execution_status="not_run",
        decision_reason=decision_reason,
    )
    session.add(approval)
    await session.flush()
    await session.refresh(approval)
    return approval


async def list_approvals(
    session: AsyncSession,
    *,
    status: str | None = None,
    agent_id=None,
    limit: int = 100,
) -> list[ApprovalRequest]:
    stmt = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.tool), selectinload(ApprovalRequest.agent))
        .order_by(desc(ApprovalRequest.requested_at))
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(ApprovalRequest.approval_status == status)
    if agent_id is not None:
        stmt = stmt.where(ApprovalRequest.agent_id == agent_id)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_visible_approvals_for_agent(
    session: AsyncSession,
    *,
    agent,
    status: str | None = None,
    limit: int = 100,
) -> list[ApprovalRequest]:
    if agent.is_admin:
        return await list_approvals(session, status=status, limit=limit)

    approvable_tool_ids = (
        select(AgentToolPermission.tool_id).where(
            AgentToolPermission.agent_id == agent.id,
            AgentToolPermission.can_approve.is_(True),
        )
    )

    stmt = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.tool), selectinload(ApprovalRequest.agent))
        .where(
            (ApprovalRequest.agent_id == agent.id)
            | (ApprovalRequest.tool_id.in_(approvable_tool_ids))
        )
        .order_by(desc(ApprovalRequest.requested_at))
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(ApprovalRequest.approval_status == status)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_approval_by_id(
    session: AsyncSession,
    approval_id,
) -> ApprovalRequest | None:
    result = await session.execute(
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.tool), selectinload(ApprovalRequest.agent))
        .where(ApprovalRequest.id == approval_id)
    )
    return result.scalar_one_or_none()


async def get_approval_for_update(
    session: AsyncSession,
    approval_id,
) -> ApprovalRequest | None:
    result = await session.execute(
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.tool), selectinload(ApprovalRequest.agent))
        .where(ApprovalRequest.id == approval_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def mark_approval_decision(
    session: AsyncSession,
    approval: ApprovalRequest,
    *,
    decision: str,
    decided_by_agent_id=None,
    decision_reason: str | None = None,
) -> ApprovalRequest:
    approval.approval_status = decision
    approval.decided_by_agent_id = decided_by_agent_id
    approval.decision_reason = decision_reason
    approval.decided_at = datetime.now(timezone.utc)
    session.add(approval)
    await session.flush()
    await session.refresh(approval)
    return approval


async def mark_execution_result(
    session: AsyncSession,
    approval: ApprovalRequest,
    *,
    execution_status: str,
    output_payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> ApprovalRequest:
    approval.execution_status = execution_status
    approval.execution_output_payload = redact_payload(
        jsonable_encoder(output_payload) if output_payload is not None else None
    )
    approval.execution_error_message = redact_error_message(error_message)
    approval.executed_at = datetime.now(timezone.utc)
    session.add(approval)
    await session.flush()
    await session.refresh(approval)
    return approval
