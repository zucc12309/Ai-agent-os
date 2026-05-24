from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    description: str | None = None
    api_key: str = Field(..., min_length=16, max_length=256)
    enabled: bool = True
    is_admin: bool = False
    allowed_tool_names: list[str] = Field(default_factory=list)
    approvable_tool_names: list[str] = Field(default_factory=list)


class AgentReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    api_key_prefix: str
    enabled: bool
    is_admin: bool
    allowed_tool_names: list[str] = Field(default_factory=list)
    approvable_tool_names: list[str] = Field(default_factory=list)
    created_at: datetime
    last_used_at: datetime | None = None


class AgentCreateResponse(AgentReadResponse):
    pass


class AgentPermissionUpdateRequest(BaseModel):
    allowed_tool_names: list[str] = Field(default_factory=list)
    approvable_tool_names: list[str] = Field(default_factory=list)
    is_admin: bool = False
    enabled: bool = True
