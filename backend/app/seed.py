from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal, init_db
from app.models.agent import Agent, AgentToolPermission
from app.models.customer import Customer
from app.models.tool import Tool
from app.services.auth_service import hash_api_key
from app.services.tool_catalog import SUPPORTED_TOOL_SPECS

settings = get_settings()

SAMPLE_TOOLS: list[dict[str, Any]] = [spec.as_tool_row() for spec in SUPPORTED_TOOL_SPECS.values()]


async def _seed_customers(session: AsyncSession) -> None:
    result = await session.execute(select(func.count()).select_from(Customer))
    count = result.scalar_one()
    if count and count > 0:
        return

    session.add_all(
        [
            Customer(full_name="Ada Lovelace", email="ada@example.com", segment="enterprise", status="active"),
            Customer(full_name="Grace Hopper", email="grace@example.com", segment="enterprise", status="active"),
            Customer(full_name="Linus Torvalds", email="linus@example.com", segment="developer", status="active"),
        ]
    )


async def _seed_tools(session: AsyncSession) -> None:
    result = await session.execute(select(Tool.tool_name))
    existing_tool_names = {row[0] for row in result.all()}
    for tool in SAMPLE_TOOLS:
        if tool["tool_name"] not in existing_tool_names:
            session.add(Tool(**tool))
    await session.flush()


async def _seed_demo_agent(session: AsyncSession) -> Agent:
    if not settings.demo_operator_api_key:
        raise RuntimeError(
            "DEMO_OPERATOR_API_KEY must be configured so the seeded admin agent can be authenticated."
        )

    demo_api_key = settings.demo_operator_api_key
    result = await session.execute(select(Agent).where(Agent.name == "demo-operator"))
    demo_agent = result.scalar_one_or_none()
    if demo_agent is None:
        demo_agent = Agent(
            name="demo-operator",
            description="Seeded admin agent for local development.",
            api_key_hash=hash_api_key(demo_api_key),
            api_key_prefix=demo_api_key[:12],
            enabled=True,
            is_admin=True,
            last_used_at=None,
        )
        session.add(demo_agent)
        await session.flush()
    else:
        demo_agent.api_key_hash = hash_api_key(demo_api_key)
        demo_agent.api_key_prefix = demo_api_key[:12]
        demo_agent.enabled = True
        demo_agent.is_admin = True
        if demo_agent.description is None:
            demo_agent.description = "Seeded admin agent for local development."
        session.add(demo_agent)
        await session.flush()

    permission_result = await session.execute(
        select(AgentToolPermission.tool_id).where(AgentToolPermission.agent_id == demo_agent.id)
    )
    existing_permission_tool_ids = {row[0] for row in permission_result.all()}

    tools = list((await session.execute(select(Tool))).scalars().all())
    for tool in tools:
        if tool.id not in existing_permission_tool_ids:
            session.add(
                AgentToolPermission(
                    agent_id=demo_agent.id,
                    tool_id=tool.id,
                    can_execute=True,
                    can_approve=True,
                )
            )

    await session.flush()
    return demo_agent


async def seed_database(
    session: AsyncSession,
    *,
    logger: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Seed sample tools, customers, and a demo admin agent."""

    await _seed_tools(session)
    await _seed_customers(session)
    await session.flush()
    demo_agent = await _seed_demo_agent(session)
    await session.commit()
    logger("Agent Gateway seed complete. Demo operator key is configured via environment.")

    return {
        "seeded": True,
        "demo_agent_name": demo_agent.name,
        "demo_agent_api_key_prefix": demo_agent.api_key_prefix,
        "tool_names": [tool.tool_name for tool in (await session.execute(select(Tool))).scalars().all()],
    }


async def _run() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        result = await seed_database(session)
        print(result)


if __name__ == "__main__":
    asyncio.run(_run())
