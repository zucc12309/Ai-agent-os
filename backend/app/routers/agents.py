from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.agent import Agent, AgentToolPermission
from app.models.tool import Tool
from app.schemas import AgentCreateRequest, AgentCreateResponse, AgentReadResponse
from app.services.auth_service import get_current_agent, hash_api_key
from app.services.permission_service import assert_agent_can_manage_registry

router = APIRouter(tags=["agents"])


def _serialize_agent(
    agent: Agent,
    permissions: list[AgentToolPermission],
) -> AgentReadResponse:
    allowed_tool_names = [perm.tool.tool_name for perm in permissions if perm.can_execute]
    approvable_tool_names = [perm.tool.tool_name for perm in permissions if perm.can_approve]
    return AgentReadResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        api_key_prefix=agent.api_key_prefix,
        enabled=agent.enabled,
        is_admin=agent.is_admin,
        allowed_tool_names=allowed_tool_names,
        approvable_tool_names=approvable_tool_names,
        created_at=agent.created_at,
        last_used_at=agent.last_used_at,
    )


@router.get("/agents", response_model=list[AgentReadResponse])
async def list_agents(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> list[AgentReadResponse]:
    await assert_agent_can_manage_registry(current_agent)
    result = await db.execute(
        select(Agent)
        .options(
            selectinload(Agent.permissions).selectinload(AgentToolPermission.tool),
        )
        .order_by(Agent.created_at)
    )
    agents = list(result.scalars().all())
    return [_serialize_agent(agent, list(agent.permissions)) for agent in agents]


@router.post("/agents", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> AgentCreateResponse:
    await assert_agent_can_manage_registry(current_agent)

    api_key_hash = hash_api_key(payload.api_key)
    agent = Agent(
        name=payload.name,
        description=payload.description,
        api_key_hash=api_key_hash,
        api_key_prefix=payload.api_key[:12],
        enabled=payload.enabled,
        is_admin=payload.is_admin,
    )
    db.add(agent)
    await db.flush()

    selected_tools: dict[str, Tool] = {}

    if payload.allowed_tool_names or payload.approvable_tool_names:
        requested_tool_names = payload.allowed_tool_names + payload.approvable_tool_names
        tool_result = await db.execute(select(Tool).where(Tool.tool_name.in_(requested_tool_names)))
        selected_tools = {tool.tool_name: tool for tool in tool_result.scalars().all()}
        missing = sorted(
            set(requested_tool_names) - set(selected_tools.keys())
        )
        if missing:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool names: {', '.join(missing)}",
        )

        for tool_name in payload.allowed_tool_names:
            db.add(
                AgentToolPermission(
                    agent_id=agent.id,
                    tool_id=selected_tools[tool_name].id,
                    can_execute=True,
                    can_approve=tool_name in payload.approvable_tool_names,
                )
            )
        for tool_name in payload.approvable_tool_names:
            if tool_name not in payload.allowed_tool_names:
                db.add(
                    AgentToolPermission(
                        agent_id=agent.id,
                        tool_id=selected_tools[tool_name].id,
                        can_execute=False,
                        can_approve=True,
                    )
                )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent already exists.") from exc

    result = await db.execute(
        select(Agent)
        .options(
            selectinload(Agent.permissions).selectinload(AgentToolPermission.tool),
        )
        .where(Agent.id == agent.id)
    )
    created_agent = result.scalar_one()
    permissions = list(created_agent.permissions)
    read_model = _serialize_agent(created_agent, permissions)
    return AgentCreateResponse.model_validate(read_model.model_dump(mode="json"))
