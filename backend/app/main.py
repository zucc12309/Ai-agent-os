from __future__ import annotations

from contextlib import asynccontextmanager, AsyncExitStack
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.config import get_settings
from app.database import AsyncSessionLocal, dispose_db, init_db
from app.mcp_server.server import mcp
from app.models.agent import Agent
from app.models.approval import ApprovalRequest
from app.models.audit_log import AuditLog
from app.models.tool import Tool
from app.routers.auth import router as auth_router
from app.routers.agents import router as agents_router
from app.routers.approvals import router as approvals_router
from app.routers.audit import router as audit_router
from app.routers.execute import router as execute_router
from app.routers.tools import router as tools_router
from app.seed import seed_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.demo_seed_enabled:
        async with AsyncSessionLocal() as session:
            seed_result = await seed_database(session, logger=print)
            app.state.seed_result = seed_result
    else:
        app.state.seed_result = {"seeded": False, "reason": "demo seeding disabled"}
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())
        yield
    await dispose_db()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

app.include_router(agents_router)
app.include_router(auth_router)
app.include_router(tools_router)
app.include_router(execute_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.mount("/mcp", mcp.streamable_http_app())


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.environment,
        "mcp_path": settings.mcp_mount_path,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        agent_count = await session.scalar(select(func.count()).select_from(Agent))
        tool_count = await session.scalar(select(func.count()).select_from(Tool))
        approval_count = await session.scalar(select(func.count()).select_from(ApprovalRequest))
        audit_count = await session.scalar(select(func.count()).select_from(AuditLog))
    return {
        "status": "ok",
        "database": "connected",
        "app_name": settings.app_name,
        "environment": settings.environment,
        "agent_count": int(agent_count or 0),
        "tool_count": int(tool_count or 0),
        "approval_count": int(approval_count or 0),
        "audit_log_count": int(audit_count or 0),
        "mcp_path": settings.mcp_mount_path,
    }


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Agent Gateway backend is running.",
        "docs": "/docs",
        "health": "/health",
        "mcp": settings.mcp_mount_path,
    }
