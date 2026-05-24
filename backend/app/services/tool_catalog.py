from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.schemas.tool_schema import (
    AppendRowInput,
    AppendRowOutput,
    DraftEmailInput,
    DraftEmailOutput,
    GetCustomerByIdInput,
    GetCustomerByIdOutput,
    InternalApiInput,
    InternalApiOutput,
    ReadSheetInput,
    ReadSheetOutput,
    RiskLevel,
    SafeSelectQueryInput,
    SafeSelectQueryOutput,
    SendEmailInput,
    SendEmailOutput,
    get_schema_for_model,
)


@dataclass(frozen=True)
class ToolSpec:
    tool_name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    connector_type: str
    risk_level: str
    requires_approval: bool
    enabled: bool = True
    is_write: bool = False

    @property
    def input_schema(self) -> dict[str, Any]:
        return get_schema_for_model(self.input_model)

    @property
    def output_schema(self) -> dict[str, Any]:
        return get_schema_for_model(self.output_model)

    def as_tool_row(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "connector_type": self.connector_type,
            "risk_level": self.risk_level,
            "requires_approval": self.requires_approval,
            "enabled": self.enabled,
            "is_write": self.is_write,
        }


SUPPORTED_TOOL_SPECS: dict[str, ToolSpec] = {
    "run_safe_select_query": ToolSpec(
        tool_name="run_safe_select_query",
        description="Run a constrained read-only SQL query against the customers table.",
        input_model=SafeSelectQueryInput,
        output_model=SafeSelectQueryOutput,
        connector_type="postgres",
        risk_level=RiskLevel.low.value,
        requires_approval=False,
    ),
    "get_customer_by_id": ToolSpec(
        tool_name="get_customer_by_id",
        description="Fetch a customer record by primary key.",
        input_model=GetCustomerByIdInput,
        output_model=GetCustomerByIdOutput,
        connector_type="postgres",
        risk_level=RiskLevel.low.value,
        requires_approval=False,
    ),
    "draft_email": ToolSpec(
        tool_name="draft_email",
        description="Draft an email payload for human review.",
        input_model=DraftEmailInput,
        output_model=DraftEmailOutput,
        connector_type="gmail",
        risk_level=RiskLevel.medium.value,
        requires_approval=False,
    ),
    "send_email": ToolSpec(
        tool_name="send_email",
        description="Send an email through Gmail after approval.",
        input_model=SendEmailInput,
        output_model=SendEmailOutput,
        connector_type="gmail",
        risk_level=RiskLevel.high.value,
        requires_approval=True,
        is_write=True,
    ),
    "read_sheet": ToolSpec(
        tool_name="read_sheet",
        description="Read data from a Google Sheet or Excel worksheet.",
        input_model=ReadSheetInput,
        output_model=ReadSheetOutput,
        connector_type="sheets",
        risk_level=RiskLevel.low.value,
        requires_approval=False,
    ),
    "append_row": ToolSpec(
        tool_name="append_row",
        description="Append a row to a spreadsheet after approval.",
        input_model=AppendRowInput,
        output_model=AppendRowOutput,
        connector_type="sheets",
        risk_level=RiskLevel.medium.value,
        requires_approval=True,
        is_write=True,
    ),
    "call_internal_api": ToolSpec(
        tool_name="call_internal_api",
        description="Call a restricted internal HTTP API using allowlisted paths only.",
        input_model=InternalApiInput,
        output_model=InternalApiOutput,
        connector_type="internal_api",
        risk_level=RiskLevel.high.value,
        requires_approval=True,
        is_write=True,
    ),
}


def get_tool_spec(tool_name: str) -> ToolSpec | None:
    return SUPPORTED_TOOL_SPECS.get(tool_name)


def list_supported_tool_names() -> list[str]:
    return list(SUPPORTED_TOOL_SPECS.keys())

