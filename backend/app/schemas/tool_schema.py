from __future__ import annotations

from enum import Enum
from typing import Any

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SafeSelectQueryInput(BaseModel):
    query: str = Field(
        ...,
        description="Read-only SQL query constrained to allowlisted business tables and columns.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Named parameters for the SQL query.",
    )
    limit: int = Field(default=100, ge=1, le=500)


class SafeSelectQueryOutput(BaseModel):
    rows: list[dict[str, Any]]
    row_count: int
    applied_limit: int


class GetCustomerByIdInput(BaseModel):
    customer_id: int = Field(..., ge=1)


class GetCustomerByIdOutput(BaseModel):
    found: bool
    customer: dict[str, Any] | None = None


class DraftEmailInput(BaseModel):
    to: str
    subject: str
    body: str
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)


class DraftEmailOutput(BaseModel):
    draft_id: str
    status: str
    preview: dict[str, Any]


class SendEmailInput(BaseModel):
    to: str
    subject: str
    body: str
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)


class SendEmailOutput(BaseModel):
    status: str
    delivery_mode: str
    message: str


class ReadSheetInput(BaseModel):
    spreadsheet_id: str
    range_name: str


class ReadSheetOutput(BaseModel):
    spreadsheet_id: str
    range_name: str
    rows: list[list[Any]]
    row_count: int
    note: str


class AppendRowInput(BaseModel):
    spreadsheet_id: str
    sheet_name: str
    row_values: list[Any]


class AppendRowOutput(BaseModel):
    spreadsheet_id: str
    sheet_name: str
    appended: bool
    row_count: int
    note: str


class InternalApiInput(BaseModel):
    method: str = Field(default="GET")
    path: str
    query_params: dict[str, Any] = Field(default_factory=dict)
    json_body: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Deprecated placeholder; user-supplied headers are rejected by the connector.",
    )

    @field_validator("method")
    @classmethod
    def _validate_method(cls, value: str) -> str:
        method = value.strip().upper()
        allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if method not in allowed_methods:
            raise ValueError(f"Internal API method must be one of: {', '.join(sorted(allowed_methods))}.")
        return method


class InternalApiOutput(BaseModel):
    method: str
    path: str
    status_code: int
    response: dict[str, Any] | list[Any] | str | None
    note: str


class ToolCreateRequest(BaseModel):
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    connector_type: str
    risk_level: RiskLevel = RiskLevel.low
    requires_approval: bool = False
    enabled: bool = True
    is_write: bool = False


class ToolReadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    connector_type: str
    risk_level: str
    requires_approval: bool
    enabled: bool
    is_write: bool
    created_at: datetime
    updated_at: datetime


TOOL_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "run_safe_select_query": SafeSelectQueryInput,
    "get_customer_by_id": GetCustomerByIdInput,
    "draft_email": DraftEmailInput,
    "send_email": SendEmailInput,
    "read_sheet": ReadSheetInput,
    "append_row": AppendRowInput,
    "call_internal_api": InternalApiInput,
}

TOOL_OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "run_safe_select_query": SafeSelectQueryOutput,
    "get_customer_by_id": GetCustomerByIdOutput,
    "draft_email": DraftEmailOutput,
    "send_email": SendEmailOutput,
    "read_sheet": ReadSheetOutput,
    "append_row": AppendRowOutput,
    "call_internal_api": InternalApiOutput,
}


def get_schema_for_model(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema()
