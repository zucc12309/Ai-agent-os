from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApprovalDecisionRequest(BaseModel):
    decision_reason: str | None = Field(default=None, max_length=2000)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tool_id: UUID
    decided_by_agent_id: UUID | None = None
    tool_name: str
    input_payload: dict[str, Any]
    approval_status: str
    execution_status: str
    decision_reason: str | None = None
    requested_at: datetime
    decided_at: datetime | None = None
    executed_at: datetime | None = None
    execution_output_payload: dict[str, Any] | None = None
    execution_error_message: str | None = None
    created_at: datetime
    updated_at: datetime
