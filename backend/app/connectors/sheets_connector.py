from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tool_schema import AppendRowInput, AppendRowOutput, ReadSheetInput, ReadSheetOutput


class SheetsConnector:
    connector_type = "sheets"

    async def read_sheet(
        self,
        session: AsyncSession,
        payload: ReadSheetInput,
    ) -> dict:
        rows = [
            ["customer_id", "full_name", "lifetime_value"],
            [1, "Ada Lovelace", 1840],
            [2, "Grace Hopper", 2750],
        ]
        response = ReadSheetOutput(
            spreadsheet_id=payload.spreadsheet_id,
            range_name=payload.range_name,
            rows=rows,
            row_count=len(rows),
            note="TODO: replace with Google Sheets or Excel connector.",
        )
        return response.model_dump(mode="json")

    async def append_row(
        self,
        session: AsyncSession,
        payload: AppendRowInput,
    ) -> dict:
        response = AppendRowOutput(
            spreadsheet_id=payload.spreadsheet_id,
            sheet_name=payload.sheet_name,
            appended=True,
            row_count=len(payload.row_values),
            note="TODO: replace with Google Sheets or Excel append API.",
        )
        return response.model_dump(mode="json")

