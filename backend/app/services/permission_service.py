from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentToolPermission
from app.models.tool import Tool


async def get_tool_by_name(session: AsyncSession, tool_name: str) -> Tool | None:
    result = await session.execute(select(Tool).where(Tool.tool_name == tool_name))
    return result.scalar_one_or_none()


async def get_tool_with_permissions(session: AsyncSession, tool_name: str) -> Tool | None:
    result = await session.execute(
        select(Tool)
        .options(selectinload(Tool.permissions))
        .where(Tool.tool_name == tool_name)
    )
    return result.scalar_one_or_none()


async def list_agent_permissions(
    session: AsyncSession,
    agent_id,
) -> list[AgentToolPermission]:
    result = await session.execute(
        select(AgentToolPermission)
        .options(selectinload(AgentToolPermission.tool))
        .where(AgentToolPermission.agent_id == agent_id)
    )
    return list(result.scalars().all())


async def assert_agent_can_manage_registry(agent: Agent) -> None:
    if not agent.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges are required for this action.",
        )


async def assert_agent_can_execute_tool(
    session: AsyncSession,
    agent: Agent,
    tool: Tool,
) -> AgentToolPermission | None:
    if not tool.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tool is disabled.")

    if agent.is_admin:
        return None

    result = await session.execute(
        select(AgentToolPermission).where(
            AgentToolPermission.agent_id == agent.id,
            AgentToolPermission.tool_id == tool.id,
        )
    )
    permission = result.scalar_one_or_none()
    if permission is None or not permission.can_execute:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent is not permitted to use tool '{tool.tool_name}'.",
        )
    return permission


async def assert_agent_can_approve_tool(
    session: AsyncSession,
    agent: Agent,
    tool: Tool,
) -> AgentToolPermission | None:
    if agent.is_admin:
        return None

    result = await session.execute(
        select(AgentToolPermission).where(
            AgentToolPermission.agent_id == agent.id,
            AgentToolPermission.tool_id == tool.id,
        )
    )
    permission = result.scalar_one_or_none()
    if permission is None or not permission.can_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent cannot approve tool '{tool.tool_name}'.",
        )
    return permission


async def assert_approval_is_not_self_approved(
    approver: Agent,
    requester_agent_id,
) -> None:
    if approver.id == requester_agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agents cannot approve their own requests.",
        )
