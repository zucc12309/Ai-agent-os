from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecuteToolRequest(BaseModel):
    input_payload: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool_name: str
    status: str
    approval_status: str
    approval_request_id: str | None = None
    output_payload: dict[str, Any] | None = None
    error_message: str | None = None
    execution_time_ms: int

