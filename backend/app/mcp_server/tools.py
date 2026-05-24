from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import or_, select

from app.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.agent import AgentToolPermission
from app.services.approval_service import list_visible_approvals_for_agent
from app.services.audit_service import list_audit_logs
from app.services.auth_service import authenticate_api_key_value
from app.services.execution_service import execute_tool as execute_tool_service
from app.services.rate_limit_service import rate_limit_service
from app.services.redaction import redact_payload
from app.schemas.tool_schema import ToolReadResponse
from app.models.tool import Tool


def _extract_headers(ctx: Context) -> Mapping[str, str]:
    request_context = getattr(ctx, "request_context", None)
    request = getattr(request_context, "request", None)
    headers = getattr(request, "headers", None)
    return headers or {}


async def _authenticate(ctx: Context) -> Agent:
    headers = _extract_headers(ctx)
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if not api_key:
        raise PermissionError("Missing X-API-Key header for MCP request.")

    async with AsyncSessionLocal() as session:
        return await authenticate_api_key_value(api_key, session)


def register_mcp_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_tools(ctx: Context) -> list[dict[str, Any]]:
        """List enabled tools for the authenticated agent."""

        agent = await _authenticate(ctx)
        async with AsyncSessionLocal() as session:
            await rate_limit_service.enforce(str(agent.id), "mcp:list_tools")
            if agent.is_admin:
                result = await session.execute(
                    select(Tool).where(Tool.enabled.is_(True)).order_by(Tool.created_at)
                )
            else:
                result = await session.execute(
                    select(Tool)
                    .join(AgentToolPermission, AgentToolPermission.tool_id == Tool.id)
                    .where(
                        AgentToolPermission.agent_id == agent.id,
                        Tool.enabled.is_(True),
                        or_(
                            AgentToolPermission.can_execute.is_(True),
                            AgentToolPermission.can_approve.is_(True),
                        ),
                    )
                    .order_by(Tool.created_at)
                    .distinct()
                )
            tools = [
                ToolReadResponse(
                    id=str(tool.id),
                    tool_name=tool.tool_name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    connector_type=tool.connector_type,
                    risk_level=tool.risk_level,
                    requires_approval=tool.requires_approval,
                    enabled=tool.enabled,
                    is_write=tool.is_write,
                    created_at=tool.created_at,
                    updated_at=tool.updated_at,
                ).model_dump(mode="json")
                for tool in result.scalars().all()
            ]
            return tools

    @mcp.tool()
    async def execute_tool(
        tool_name: str,
        input_payload: dict[str, Any],
        ctx: Context,
    ) -> dict[str, Any]:
        """Execute a tool using the authenticated agent's permissions."""

        agent = await _authenticate(ctx)
        async with AsyncSessionLocal() as session:
            await rate_limit_service.enforce(str(agent.id), f"mcp:execute:{tool_name}")
            result = await execute_tool_service(
                session,
                agent=agent,
                tool_name=tool_name,
                input_payload=input_payload,
            )
            return result.model_dump(mode="json")

    @mcp.tool()
    async def get_audit_logs(ctx: Context, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent audit logs for the authenticated agent."""

        agent = await _authenticate(ctx)
        async with AsyncSessionLocal() as session:
            logs = await list_audit_logs(session, agent_id=agent.id, limit=limit)
            return [
                {
                    "id": str(log.id),
                    "agent_id": str(log.agent_id),
                    "tool_id": str(log.tool_id) if log.tool_id else None,
                    "tool_name": log.tool_name,
                    "input_payload": redact_payload(log.input_payload),
                    "output_payload": redact_payload(log.output_payload),
                    "status": log.status,
                    "error_message": log.error_message,
                    "approval_status": log.approval_status,
                    "event_hash": log.event_hash,
                    "previous_event_hash": log.previous_event_hash,
                    "execution_time_ms": log.execution_time_ms,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]

    @mcp.tool()
    async def get_pending_approvals(ctx: Context, limit: int = 50) -> list[dict[str, Any]]:
        """Return pending approval requests for the authenticated agent."""

        agent = await _authenticate(ctx)
        async with AsyncSessionLocal() as session:
            approvals = await list_visible_approvals_for_agent(session, agent=agent, status="pending", limit=limit)
            return [
                {
                    "id": str(approval.id),
                    "agent_id": str(approval.agent_id),
                    "tool_id": str(approval.tool_id),
                    "decided_by_agent_id": str(approval.decided_by_agent_id) if approval.decided_by_agent_id else None,
                    "tool_name": approval.tool_name,
                    "input_payload": redact_payload(approval.input_payload),
                    "approval_status": approval.approval_status,
                    "execution_status": approval.execution_status,
                    "requested_at": approval.requested_at.isoformat() if approval.requested_at else None,
                }
                for approval in approvals
            ]
