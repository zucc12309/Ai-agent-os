from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.agent import Agent
from app.models.agent import AgentToolPermission
from app.models.tool import Tool
from app.schemas import ToolCreateRequest, ToolReadResponse
from app.services.auth_service import get_current_agent
from app.services.permission_service import assert_agent_can_manage_registry
from app.services.tool_catalog import get_tool_spec

router = APIRouter(tags=["tools"])


def _serialize_tool(tool: Tool) -> ToolReadResponse:
    return ToolReadResponse(
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
    )


@router.get("/tools", response_model=list[ToolReadResponse])
async def list_tools(
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> list[ToolReadResponse]:
    if current_agent.is_admin:
        result = await db.execute(select(Tool).order_by(Tool.created_at))
    else:
        result = await db.execute(
            select(Tool)
            .join(AgentToolPermission, AgentToolPermission.tool_id == Tool.id)
            .where(
                AgentToolPermission.agent_id == current_agent.id,
                Tool.enabled.is_(True),
                or_(
                    AgentToolPermission.can_execute.is_(True),
                    AgentToolPermission.can_approve.is_(True),
                ),
            )
            .order_by(Tool.created_at)
            .distinct()
        )
    tools = list(result.scalars().all())
    return [_serialize_tool(tool) for tool in tools]


@router.post("/tools", response_model=ToolReadResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    payload: ToolCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> ToolReadResponse:
    await assert_agent_can_manage_registry(current_agent)

    spec = get_tool_spec(payload.tool_name)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' is not part of the supported tool catalog.",
        )

    if payload.connector_type != spec.connector_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' must use connector '{spec.connector_type}'.",
        )
    if payload.risk_level.value != spec.risk_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' must use risk level '{spec.risk_level}'.",
        )
    if payload.requires_approval != spec.requires_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' must have requires_approval={spec.requires_approval}.",
        )
    if payload.is_write != spec.is_write:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' must have is_write={spec.is_write}.",
        )
    if payload.description != spec.description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' description must match the supported catalog.",
        )
    if payload.input_schema != spec.input_schema or payload.output_schema != spec.output_schema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool '{payload.tool_name}' schemas must match the supported catalog.",
        )

    tool = Tool(
        tool_name=payload.tool_name,
        description=spec.description,
        input_schema=spec.input_schema,
        output_schema=spec.output_schema,
        connector_type=spec.connector_type,
        risk_level=spec.risk_level,
        requires_approval=spec.requires_approval,
        enabled=payload.enabled,
        is_write=spec.is_write,
    )
    db.add(tool)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tool already exists.") from exc
    await db.refresh(tool)
    return _serialize_tool(tool)
