from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    tool_id: UUID | None = None
    tool_name: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None = None
    status: str
    error_message: str | None = None
    approval_status: str
    execution_time_ms: int
    event_hash: str | None = None
    previous_event_hash: str | None = None
    created_at: datetime
