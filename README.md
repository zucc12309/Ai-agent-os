# Agent Gateway

Agent Gateway is a secure MCP/API layer for AI agents that need to interact with business tools such as PostgreSQL, Gmail, Google Sheets/Excel, and internal APIs.

It gives you:

- A FastAPI backend with API-key auth and HttpOnly session cookies for the dashboard
- A Python MCP server mounted on the same service
- A tool registry with schema, risk, and approval metadata
- Tool-level permissions and approval gating
- Audit logs for every execution attempt
- A Next.js dashboard for operators
- Docker-first local development

## Architecture

```text
                    +----------------------+
                    |  Next.js Dashboard   |
                    |  Tools / Logs / UI   |
                    +----------+-----------+
                               |
                               | login with X-API-Key, then HttpOnly cookie
                               v
                    +----------+-----------+
                    |  FastAPI Backend     |
                    |  /agents /tools      |
                    |  /execute /approvals |
                    |  /audit-logs         |
                    +----+------------+----+
                         |            |
                         |            | audit + approvals
                         |            v
                         |     +------+------+
                         |     | PostgreSQL   |
                         |     | registry/log |
                         |     +-------------+
                         |
                         | MCP streamable HTTP
                         v
                  +------+------+
                  |   /mcp      |
                  | FastMCP SDK |
                  +------+------+
                         |
        +----------------+-------------------+
        |                |                   |
        v                v                   v
   PostgreSQL        Gmail / Sheets      Internal APIs
   connector         placeholders        connector
```

## Folder Layout

```text
agent-gateway/
  backend/
    app/
      main.py
      config.py
      database.py
      models/
      routers/
      services/
      connectors/
      mcp_server/
      schemas/
      seed.py
    requirements.txt
    Dockerfile
  frontend/
    app/
    components/
    lib/
    package.json
    Dockerfile
  docker-compose.yml
  README.md
  .env.example
```

## Setup

1. Copy the example environment file.

```bash
cp .env.example .env
```

2. Start the stack with Docker Compose.

```bash
docker compose up --build
```

3. Confirm the `DEMO_OPERATOR_API_KEY` value in `.env` or `docker-compose.yml`.

The first startup seeds:

- Sample tools
- Demo customer rows
- A demo admin agent
- A demo admin API key that is never printed by the backend

4. Paste that API key into the dashboard sidebar.

The dashboard exchanges the key for an HttpOnly session cookie and never stores the raw key in browser storage.

## Run with Docker

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Readiness: `http://localhost:8000/ready`
- MCP endpoint: `http://localhost:8000/mcp`
- OpenAPI docs: `http://localhost:8000/docs`
- Login session endpoint: `http://localhost:8000/auth/session`

## Example REST Calls

### List tools

```bash
curl -H "X-API-Key: <demo-api-key>" http://localhost:8000/tools
```

### Exchange an API key for a browser session

```bash
curl -X POST http://localhost:8000/auth/session \
  -H "X-API-Key: <demo-api-key>" \
  -c cookies.txt
```

Then reuse `cookies.txt` for the secure dashboard routes:

```bash
curl -b cookies.txt http://localhost:8000/approvals
```

### Run a safe PostgreSQL select

```bash
curl -X POST http://localhost:8000/execute/run_safe_select_query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <demo-api-key>" \
  -d '{
    "input_payload": {
      "query": "SELECT id, full_name, email FROM customers WHERE status = :status",
      "parameters": { "status": "active" },
      "limit": 50
    }
  }'
```

### List approvals

```bash
curl -H "X-API-Key: <demo-api-key>" http://localhost:8000/approvals
```

### Approve a request

```bash
curl -X POST http://localhost:8000/approvals/<approval-id>/approve \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <demo-api-key>" \
  -d '{"decision_reason": "Looks good"}'
```

## Example MCP Usage

The FastMCP server is mounted at `/mcp`, so any MCP client that supports streamable HTTP can connect to:

```text
http://localhost:8000/mcp
```

Example with the MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector
```

Then connect to `http://localhost:8000/mcp` and provide the same `X-API-Key` header used by the REST API.

The MCP tools exposed by Agent Gateway are:

- `list_tools`
- `execute_tool`
- `get_audit_logs`
- `get_pending_approvals`

## Security Model

- API keys are hashed in the database, not stored in plaintext.
- Browser access uses an HttpOnly session cookie after the API key is exchanged once.
- Rotate `API_KEY_PEPPER` and `SESSION_SIGNING_SECRET` for any non-development deployment.
- Every execution attempt is audited, payloads are redacted before storage and display, and audit rows are chained with event hashes.
- Tools are filtered by agent permissions.
- High-risk tools always require approval.
- Approval decisions are locked, attributed to the reviewer, and executed atomically.
- Write actions that require approval create approval requests instead of executing immediately.
- PostgreSQL connector queries are limited to a single allowlisted table and safe equality filters.
- The internal API connector rejects absolute URLs, traversal, and user-supplied headers.
- Tool inputs are validated with Pydantic models.
- A rate-limit placeholder is wired in and ready to be replaced with a real limiter.
- OAuth integrations for Gmail and Google Sheets are intentionally marked as TODOs for the MVP.

## Seed Data

The first boot seeds these tools:

- `run_safe_select_query`
- `get_customer_by_id`
- `draft_email`
- `send_email`
- `read_sheet`
- `append_row`
- `call_internal_api`

It also creates:

- A demo admin agent
- Demo customer rows
- A seeded admin API key configured via environment variables

## Future Roadmap

1. Add OAuth for Gmail and Google Sheets.
2. Add a real rate limiter and request quota tracking.
3. Add per-tenant workspace isolation.
4. Add migration automation and schema versioning for the database.
5. Add connector health checks and connector-specific secrets.
6. Add full-text search and filtering for logs and approvals.
7. Add production-grade SSO and workspace isolation for the dashboard.
