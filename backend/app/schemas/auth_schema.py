from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    authenticated: bool
    agent_id: UUID
    agent_name: str
    api_key_prefix: str
    is_admin: bool
    enabled: bool
    session_expires_at: datetime

