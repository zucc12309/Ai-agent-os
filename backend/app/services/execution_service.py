from __future__ import annotations

import time
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.gmail_connector import GmailConnector
from app.connectors.internal_api_connector import InternalApiConnector
from app.connectors.postgres_connector import PostgresConnector
from app.connectors.sheets_connector import SheetsConnector
from app.models.agent import Agent
from app.models.approval import ApprovalRequest
from app.models.tool import Tool
from app.schemas.execution_schema import ToolExecutionResponse
from app.schemas.tool_schema import TOOL_INPUT_MODELS
from app.services.audit_service import log_audit_event
from app.services.approval_service import create_approval_request, mark_execution_result
from app.services.permission_service import (
    assert_agent_can_execute_tool,
    get_tool_by_name,
)
from app.services.redaction import redact_error_message
from app.services.tool_catalog import get_tool_spec


postgres_connector = PostgresConnector()
gmail_connector = GmailConnector()
sheets_connector = SheetsConnector()
internal_api_connector = InternalApiConnector()


async def _validate_and_build_payload(tool_name: str, input_payload: dict[str, Any]) -> Any:
    model = TOOL_INPUT_MODELS.get(tool_name)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Tool '{tool_name}' is registered but has no execution model yet.",
        )
    return model.model_validate(input_payload)


async def _execute_connector(
    session: AsyncSession,
    tool: Tool,
    tool_name: str,
    payload: Any,
) -> dict[str, Any]:
    if tool.connector_type == "postgres" and tool_name == "run_safe_select_query":
        return await postgres_connector.run_safe_select_query(session, payload)
    if tool.connector_type == "postgres" and tool_name == "get_customer_by_id":
        return await postgres_connector.get_customer_by_id(session, payload)
    if tool.connector_type == "gmail" and tool_name == "draft_email":
        return await gmail_connector.draft_email(session, payload)
    if tool.connector_type == "gmail" and tool_name == "send_email":
        return await gmail_connector.send_email(session, payload)
    if tool.connector_type == "sheets" and tool_name == "read_sheet":
        return await sheets_connector.read_sheet(session, payload)
    if tool.connector_type == "sheets" and tool_name == "append_row":
        return await sheets_connector.append_row(session, payload)
    if tool.connector_type == "internal_api" and tool_name == "call_internal_api":
        return await internal_api_connector.call_internal_api(session, payload)

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"No connector implementation is available for '{tool_name}'.",
    )


async def execute_tool(
    session: AsyncSession,
    *,
    agent: Agent,
    tool_name: str,
    input_payload: dict[str, Any],
    approval_request: ApprovalRequest | None = None,
    force_execute: bool = False,
    commit: bool = True,
) -> ToolExecutionResponse:
    started = time.perf_counter()
    tool = await get_tool_by_name(session, tool_name)
    if tool is None:
        elapsed = int((time.perf_counter() - started) * 1000)
        error_message = redact_error_message(f"Unknown tool '{tool_name}'.")
        await log_audit_event(
            session,
            agent_id=agent.id,
            tool_id=None,
            tool_name=tool_name,
            input_payload=jsonable_encoder(input_payload),
            output_payload=None,
            status="rejected",
            error_message=error_message,
            approval_status="not_required",
            execution_time_ms=elapsed,
        )
        return ToolExecutionResponse(
            tool_name=tool_name,
            status="rejected",
            approval_status="not_required",
            error_message=error_message,
            execution_time_ms=elapsed,
        )

    spec = get_tool_spec(tool_name)
    if spec is None:
        elapsed = int((time.perf_counter() - started) * 1000)
        error_message = redact_error_message(
            f"Tool '{tool_name}' is not registered in the supported tool catalog."
        )
        await log_audit_event(
            session,
            agent_id=agent.id,
            tool_id=tool.id,
            tool_name=tool_name,
            input_payload=input_payload,
            output_payload=None,
            status="rejected",
            error_message=error_message,
            approval_status="not_required",
            execution_time_ms=elapsed,
        )
        if commit:
            await session.commit()
        return ToolExecutionResponse(
            tool_name=tool_name,
            status="rejected",
            approval_status="not_required",
            error_message=error_message,
            execution_time_ms=elapsed,
        )

    if (
        tool.connector_type != spec.connector_type
        or tool.is_write != spec.is_write
        or tool.requires_approval != spec.requires_approval
        or tool.risk_level != spec.risk_level
    ):
        elapsed = int((time.perf_counter() - started) * 1000)
        error_message = (
            f"Tool '{tool_name}' is misconfigured in the registry and does not match the supported catalog."
        )
        redacted_error_message = redact_error_message(error_message)
        await log_audit_event(
            session,
            agent_id=agent.id,
            tool_id=tool.id,
            tool_name=tool_name,
            input_payload=input_payload,
            output_payload=None,
            status="failed",
            error_message=redacted_error_message,
            approval_status="not_required",
            execution_time_ms=elapsed,
        )
        if commit:
            await session.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=redacted_error_message)

    await assert_agent_can_execute_tool(session, agent, tool)
    validated_payload = await _validate_and_build_payload(tool_name, input_payload)

    approval_required = force_execute is False and (
        tool.risk_level.lower() == "high" or tool.requires_approval
    )
    if approval_required:
        approval = await create_approval_request(
            session,
            agent_id=agent.id,
            tool_id=tool.id,
            tool_name=tool.tool_name,
            input_payload=validated_payload.model_dump(mode="json"),
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        await log_audit_event(
            session,
            agent_id=agent.id,
            tool_id=tool.id,
            tool_name=tool.tool_name,
            input_payload=validated_payload.model_dump(mode="json"),
            output_payload={
                "approval_request_id": str(approval.id),
                "message": "Approval required before execution.",
            },
            status="pending_approval",
            error_message=None,
            approval_status="pending",
            execution_time_ms=elapsed,
        )
        if commit:
            await session.commit()
        return ToolExecutionResponse(
            tool_name=tool.tool_name,
            status="pending_approval",
            approval_status="pending",
            approval_request_id=str(approval.id),
            output_payload={
                "approval_request_id": str(approval.id),
                "message": "Approval required before execution.",
            },
            execution_time_ms=elapsed,
        )

    try:
        output_payload = await _execute_connector(
            session,
            tool,
            tool_name,
            validated_payload,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        await log_audit_event(
            session,
            agent_id=agent.id,
            tool_id=tool.id,
            tool_name=tool.tool_name,
            input_payload=validated_payload.model_dump(mode="json"),
            output_payload=output_payload,
            status="success",
            error_message=None,
            approval_status=(
                approval_request.approval_status if approval_request is not None else "not_required"
            ),
            execution_time_ms=elapsed,
        )
        if approval_request is not None:
            await mark_execution_result(
                session,
                approval_request,
                execution_status="success",
                output_payload=output_payload,
            )
        if commit:
            await session.commit()
        return ToolExecutionResponse(
            tool_name=tool.tool_name,
            status="success",
            approval_status=(
                approval_request.approval_status if approval_request is not None else "not_required"
            ),
            output_payload=output_payload,
            execution_time_ms=elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - started) * 1000)
        error_message = redact_error_message(str(exc))
        await log_audit_event(
            session,
            agent_id=agent.id,
            tool_id=tool.id,
            tool_name=tool.tool_name,
            input_payload=validated_payload.model_dump(mode="json"),
            output_payload=None,
            status="failed",
            error_message=error_message,
            approval_status=(
                approval_request.approval_status if approval_request is not None else "not_required"
            ),
            execution_time_ms=elapsed,
        )
        if approval_request is not None:
            await mark_execution_result(
                session,
                approval_request,
                execution_status="failed",
                error_message=error_message,
            )
        if commit:
            await session.commit()
        return ToolExecutionResponse(
            tool_name=tool.tool_name,
            status="failed",
            approval_status=(
                approval_request.approval_status if approval_request is not None else "not_required"
            ),
            error_message=error_message,
            execution_time_ms=elapsed,
        )
