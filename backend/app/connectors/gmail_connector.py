from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tool_schema import DraftEmailInput, DraftEmailOutput, SendEmailInput, SendEmailOutput


class GmailConnector:
    connector_type = "gmail"

    async def draft_email(
        self,
        session: AsyncSession,
        payload: DraftEmailInput,
    ) -> dict:
        draft = DraftEmailOutput(
            draft_id=f"draft_{uuid4().hex[:12]}",
            status="draft_created",
            preview={
                "to": payload.to,
                "subject": payload.subject,
                "body": payload.body,
                "cc": payload.cc,
                "bcc": payload.bcc,
                "note": "TODO: wire Gmail OAuth and draft creation.",
            },
        )
        return draft.model_dump(mode="json")

    async def send_email(
        self,
        session: AsyncSession,
        payload: SendEmailInput,
    ) -> dict:
        response = SendEmailOutput(
            status="queued",
            delivery_mode="approval_required_placeholder",
            message=(
                "Email send approved. TODO: connect Gmail OAuth and delivery APIs "
                "before enabling real sending."
            ),
        )
        return response.model_dump(mode="json")

