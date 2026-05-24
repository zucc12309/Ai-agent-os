from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from app.mcp_server.tools import register_mcp_tools


mcp = FastMCP(
    "Agent Gateway",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)

register_mcp_tools(mcp)


@asynccontextmanager
async def lifespan(_server: FastMCP):
    yield


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

