from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.schemas.tool_schema import (
    GetCustomerByIdInput,
    GetCustomerByIdOutput,
    SafeSelectQueryInput,
    SafeSelectQueryOutput,
)


class PostgresConnector:
    connector_type = "postgres"

    _allowed_table = "customers"
    _allowed_columns = {
        "id",
        "full_name",
        "email",
        "segment",
        "status",
        "created_at",
    }
    _forbidden_patterns = (
        r"\binsert\b",
        r"\bupdate\b",
        r"\bdelete\b",
        r"\bdrop\b",
        r"\balter\b",
        r"\btruncate\b",
        r"\bcreate\b",
        r"\breplace\b",
        r"\bgrant\b",
        r"\brevoke\b",
        r"\bmerge\b",
        r"\bcall\b",
        r"\bjoin\b",
        r"\bunion\b",
        r"\bintersect\b",
        r"\bexcept\b",
        r"\bcopy\b",
        r"\binto\b",
        r"\bpg_\w+\b",
        r"\binformation_schema\b",
    )

    def _validate_select_only(self, query: str) -> None:
        normalized = query.strip().rstrip(";")
        if not normalized:
            raise ValueError("SQL query cannot be empty.")
        if ";" in normalized or "--" in normalized or "/*" in normalized or "*/" in normalized:
            raise ValueError("Only a single safe SELECT statement is allowed.")
        if not re.match(r"^select\b", normalized, flags=re.IGNORECASE):
            raise ValueError("Only SELECT queries are allowed.")
        lowered = normalized.lower()
        for pattern in self._forbidden_patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                raise ValueError("The query contains unsupported SQL features.")

        statement_pattern = re.compile(
            r"^select\s+(?P<columns>.+?)\s+from\s+(?P<table>[a-z_][a-z0-9_]*)"
            r"(?:\s+where\s+(?P<where>.+?))?"
            r"(?:\s+order\s+by\s+(?P<order_by>.+?))?$",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = statement_pattern.match(normalized)
        if match is None:
            raise ValueError("The query must target a single allowlisted table.")

        table_name = match.group("table").lower()
        if table_name != self._allowed_table:
            raise ValueError("Only the customers table is available in the safe SQL connector.")

        select_columns = [column.strip() for column in match.group("columns").split(",")]
        if not select_columns or any(column == "*" for column in select_columns):
            raise ValueError("Explicit column selection is required.")
        for column in select_columns:
            normalized_column = column.split(".")[-1].lower()
            if normalized_column not in self._allowed_columns:
                raise ValueError(f"Column '{column}' is not allowed in safe select queries.")

        where_clause = match.group("where")
        if where_clause:
            clauses = [clause.strip() for clause in re.split(r"\s+and\s+", where_clause, flags=re.IGNORECASE)]
            for clause in clauses:
                clause_match = re.match(
                    r"^(?P<column>[a-z_][a-z0-9_\.]*)\s*=\s*(?P<value>:[a-z_][a-z0-9_]*|'[^']*'|\d+)$",
                    clause,
                    flags=re.IGNORECASE,
                )
                if clause_match is None:
                    raise ValueError(
                        "Safe select queries only allow simple equality filters joined by AND."
                    )
                normalized_column = clause_match.group("column").split(".")[-1].lower()
                if normalized_column not in self._allowed_columns:
                    raise ValueError(f"Column '{normalized_column}' cannot be filtered in safe queries.")

        order_by_clause = match.group("order_by")
        if order_by_clause:
            order_columns = [column.strip() for column in order_by_clause.split(",")]
            for column in order_columns:
                column_match = re.match(
                    r"^(?P<column>[a-z_][a-z0-9_\.]*)(?:\s+(asc|desc))?$",
                    column,
                    flags=re.IGNORECASE,
                )
                if column_match is None:
                    raise ValueError("ORDER BY only supports simple columns and optional ASC/DESC.")
                normalized_column = column_match.group("column").split(".")[-1].lower()
                if normalized_column not in self._allowed_columns:
                    raise ValueError(f"Column '{normalized_column}' cannot be used for ordering.")

    async def run_safe_select_query(
        self,
        session: AsyncSession,
        payload: SafeSelectQueryInput,
    ) -> dict[str, Any]:
        self._validate_select_only(payload.query)

        wrapped_query = f"SELECT * FROM ({payload.query.strip().rstrip(';')}) AS safe_gateway_query LIMIT :__limit"
        parameters = dict(payload.parameters)
        parameters["__limit"] = payload.limit

        result = await session.execute(text(wrapped_query), parameters)
        rows = [dict(row._mapping) for row in result.fetchall()]
        output = SafeSelectQueryOutput(
            rows=rows,
            row_count=len(rows),
            applied_limit=payload.limit,
        )
        return output.model_dump(mode="json")

    async def get_customer_by_id(
        self,
        session: AsyncSession,
        payload: GetCustomerByIdInput,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT id, full_name, email, segment, status, created_at
                FROM customers
                WHERE id = :customer_id
                """
            ),
            {"customer_id": payload.customer_id},
        )
        row = result.mappings().first()
        output = GetCustomerByIdOutput(
            found=row is not None,
            customer=dict(row) if row is not None else None,
        )
        return output.model_dump(mode="json")
