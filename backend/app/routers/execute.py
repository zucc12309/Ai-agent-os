from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.schemas import ExecuteToolRequest, ToolExecutionResponse
from app.services.auth_service import get_current_agent
from app.services.execution_service import execute_tool
from app.services.rate_limit_service import rate_limit_service

router = APIRouter(tags=["execution"])


@router.post("/execute/{tool_name}", response_model=ToolExecutionResponse)
async def execute_tool_route(
    tool_name: str,
    payload: ExecuteToolRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
) -> ToolExecutionResponse:
    await rate_limit_service.enforce(str(current_agent.id), f"execute:{tool_name}")
    return await execute_tool(
        db,
        agent=current_agent,
        tool_name=tool_name,
        input_payload=payload.input_payload,
    )

