from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas import ApprovalDecisionRequest, ApprovalResponse
from app.services.approval_service import (
    get_approval_for_update,
    list_visible_approvals_for_agent,
    mark_approval_decision,
)
from app.services.auth_service import get_current_agent
from app.services.execution_service import execute_tool
from app.services.permission_service import (
    assert_agent_can_approve_tool,
    assert_approval_is_not_self_approved,
)
from app.services.redaction import redact_payload

router = APIRouter(tags=["approvals"])


def _serialize_approval(approval) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        agent_id=approval.agent_id,
        tool_id=approval.tool_id,
        decided_by_agent_id=approval.decided_by_agent_id,
        tool_name=approval.tool_name,
        input_payload=redact_payload(approval.input_payload),
        approval_status=approval.approval_status,
        execution_status=approval.execution_status,
        decision_reason=approval.decision_reason,
        requested_at=approval.requested_at,
        decided_at=approval.decided_at,
        executed_at=approval.executed_at,
        execution_output_payload=redact_payload(approval.execution_output_payload),
        execution_error_message=approval.execution_error_message,
        created_at=approval.created_at,
        updated_at=approval.updated_at,
    )


@router.get("/approvals", response_model=list[ApprovalResponse])
async def get_approvals(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalResponse]:
    approvals = await list_visible_approvals_for_agent(db, agent=current_agent, limit=200)
    return [_serialize_approval(approval) for approval in approvals]


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    try:
        approval = await get_approval_for_update(db, approval_id)
        if approval is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")

        tool = approval.tool
        if tool is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")

        await assert_agent_can_approve_tool(db, current_agent, tool)
        await assert_approval_is_not_self_approved(current_agent, approval.agent_id)
        if approval.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval is already {approval.approval_status}.",
            )

        await mark_approval_decision(
            db,
            approval,
            decision="approved",
            decided_by_agent_id=current_agent.id,
            decision_reason=payload.decision_reason,
        )
        requesting_agent = approval.agent
        assert requesting_agent is not None
        await execute_tool(
            db,
            agent=requesting_agent,
            tool_name=approval.tool_name,
            input_payload=approval.input_payload,
            approval_request=approval,
            force_execute=True,
            commit=False,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return _serialize_approval(approval)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    try:
        approval = await get_approval_for_update(db, approval_id)
        if approval is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")

        tool = approval.tool
        if tool is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")

        await assert_agent_can_approve_tool(db, current_agent, tool)
        await assert_approval_is_not_self_approved(current_agent, approval.agent_id)
        if approval.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval is already {approval.approval_status}.",
            )

        approval = await mark_approval_decision(
            db,
            approval,
            decision="rejected",
            decided_by_agent_id=current_agent.id,
            decision_reason=payload.decision_reason,
        )
        approval.execution_status = "blocked"
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return _serialize_approval(approval)
