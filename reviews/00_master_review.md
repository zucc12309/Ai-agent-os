# Master Review: Agent Gateway

## Executive Summary

Agent Gateway is a strong MVP skeleton: the backend, MCP layer, and dashboard all line up around a coherent tool registry, and the basic auth flow is consistent across REST and MCP. The codebase is not yet safe for sensitive enterprise data, though. The highest-risk problems are connector abuse, secret leakage, non-atomic approvals, and an auth model that leaves the operator API key sitting in browser storage.

The main strengths are worth preserving:

- API keys are hashed with a pepper before storage.
- Tool inputs are validated with Pydantic before execution.
- Tool listing is permission-scoped instead of globally exposed.
- REST and MCP share the same backend services for auth and execution.

The main blockers are also clear:

- The internal API connector is an SSRF/open-proxy risk.
- The PostgreSQL connector still executes arbitrary user SQL.
- The seeded demo API key is printed to logs and the dashboard stores bearer keys in localStorage.
- Approvals, audit rows, and execution state are split across multiple commits and can diverge.
- The frontend build is compiled against `localhost`, which breaks deployments outside the local laptop.

## Top 10 Highest-Risk Issues

### 1. Critical: Internal API connector is an SSRF/open proxy

The internal API connector accepts free-form method, path, headers, query params, and JSON body, then joins the path onto the configured base URL without constraining absolute URLs. This is a direct SSRF primitive and can be used to reach metadata endpoints, localhost admin ports, or arbitrary external hosts.

Affected files:

- [backend/app/connectors/internal_api_connector.py:24](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L24)
- [backend/app/connectors/internal_api_connector.py:37](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L37)
- [backend/app/connectors/internal_api_connector.py:40](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L40)

### 2. High: Safe-select PostgreSQL tool still allows broad data exfiltration

The "safe" SQL connector runs caller-supplied SQL directly against the application database role. The regex guard blocks obvious mutations, but it still allows broad reads from any table the role can access, including metadata tables and sensitive business tables.

Affected files:

- [backend/app/connectors/postgres_connector.py:36](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L36)
- [backend/app/connectors/postgres_connector.py:54](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L54)
- [backend/app/database.py:17](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/database.py#L17)

### 3. High: Plaintext API keys leak in logs and API responses

The seed routine prints the demo key to stdout, and the create-agent route returns the plaintext key in the response body. That is a credential exposure path for logs, proxies, CI systems, and any operator with log access.

Affected files:

- [backend/app/seed.py:164](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L164)
- [backend/app/seed.py:189](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L189)
- [backend/app/routers/agents.py:132](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L132)

### 4. High: Browser localStorage stores the bearer credential

The dashboard persists the operator API key in localStorage and reuses it on every request. Any script running on the dashboard origin can read that key, which makes XSS, malicious extensions, and compromised bundles much more dangerous.

Affected files:

- [frontend/lib/api.ts:7](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L7)
- [frontend/lib/api.ts:14](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L14)
- [frontend/components/Sidebar.tsx:51](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/components/Sidebar.tsx#L51)

### 5. High: Approval workflow can double-execute write actions

Approvals are created, approved, executed, and audited in multiple separate commits with no row lock and no idempotency guard. Two approvers or a retry can race through the pending check and execute the same write side effect twice.

Affected files:

- [backend/app/routers/approvals.py:51](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L51)
- [backend/app/services/approval_service.py:107](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L107)
- [backend/app/services/execution_service.py:106](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/execution_service.py#L106)

### 6. High: Approval decisions are not attributable, and self-approval is allowed

The approval model stores request metadata but not the deciding reviewer. The route authenticates `current_agent`, but that identity is never persisted. Because `can_approve` is enough, a single agent can request and approve its own high-risk write if it holds both permissions.

Affected files:

- [backend/app/models/approval.py:13](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L13)
- [backend/app/routers/approvals.py:66](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L66)
- [backend/app/services/permission_service.py:72](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/permission_service.py#L72)

### 7. High: Audit trail stores raw payloads without redaction or immutability

Audit rows and approval rows persist full inputs, outputs, and error strings. The UI renders that data back to operators. There is no redaction layer, size limit, correlation id, or tamper-evident log chain, so sensitive data can live forever in the database and browser.

Affected files:

- [backend/app/services/audit_service.py:13](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L13)
- [backend/app/models/audit_log.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L34)
- [frontend/app/audit/page.tsx:66](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/audit/page.tsx#L66)

### 8. High: Frontend is compiled against `localhost`

The frontend API helper defaults to `http://localhost:8000`, and the Dockerfile bakes that in at build time. Any deployment accessed from another machine will point browser API calls at the user’s own localhost instead of the gateway backend.

Affected files:

- [frontend/lib/api.ts:1](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L1)
- [frontend/Dockerfile:9](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/Dockerfile#L9)
- [docker-compose.yml:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/docker-compose.yml#L34)

### 9. P1: Startup seeding and schema creation happen inside the app lifespan

The backend creates tables and seeds demo data during startup. That couples boot to database mutation, prints the demo key during startup, and leaves no real migration path for schema changes.

Affected files:

- [backend/app/main.py:27](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L27)
- [backend/app/database.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/database.py#L34)
- [backend/app/seed.py:145](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L145)

### 10. P1: Tool registry metadata and runtime dispatch are out of sync

The registry allows arbitrary connector types and tool names, but execution only knows about the hardcoded seed tools and branch-based connector dispatch. A tool can be created and listed successfully, then fail with `501 Not Implemented` at runtime.

Affected files:

- [backend/app/routers/tools.py:62](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L62)
- [backend/app/services/execution_service.py:33](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/execution_service.py#L33)
- [backend/app/schemas/tool_schema.py:112](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L112)

## P0 Fixes Needed Before Running

These should be treated as hard blockers before running this in any shared or sensitive environment.

- Remove plaintext key leakage from startup logs and API responses.
  - Stop printing the demo key in [backend/app/seed.py:164](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L164).
  - Do not return plaintext keys in [backend/app/routers/agents.py:132](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L132) except via a deliberate one-time secret handoff flow.
- Move the operator key out of browser localStorage.
  - Replace [frontend/lib/api.ts:7](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L7) persistence with in-memory storage or an `HttpOnly` cookie/session model.
- Lock down the internal API connector.
  - Reject absolute URLs and arbitrary headers in [backend/app/connectors/internal_api_connector.py:24](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L24).
- Replace the raw SQL connector or constrain it to a read-only account plus AST allowlisting.
  - The current implementation in [backend/app/connectors/postgres_connector.py:36](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L36) is too permissive for enterprise use.
- Remove the build-time `localhost` dependency from the frontend.
  - [frontend/lib/api.ts:1](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L1) must not ship with a localhost fallback for anything beyond local dev.

## P1 Fixes Needed Before Demo

- Make approval, audit, and execution writes atomic.
  - Use a row lock or conditional update in [backend/app/routers/approvals.py:51](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L51) and persist the result in one workflow.
- Add approver identity and prevent self-approval where separation of duties matters.
  - Extend [backend/app/models/approval.py:13](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L13) with reviewer identity fields.
- Add real migrations and stop relying on `create_all` in app startup.
  - Replace [backend/app/database.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/database.py#L34) with Alembic.
- Redact or summarize audit payloads before storing and rendering them.
  - The current storage path in [backend/app/services/audit_service.py:13](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L13) and UI rendering in [frontend/app/audit/page.tsx:66](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/audit/page.tsx#L66) is too raw for sensitive data.
- Make the tool registry validate supported runtime combinations before commit.
  - Reject unsupported connector/tool combinations in [backend/app/routers/tools.py:62](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L62).
- Add row locking or idempotency around approval decisions to prevent duplicate side effects.
  - The current approval flow in [backend/app/services/approval_service.py:107](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L107) needs a real state machine.
- Add backend and frontend readiness checks.
  - PostgreSQL already has a healthcheck in [docker-compose.yml:12](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/docker-compose.yml#L12), but the app containers do not.

## P2 Improvements

- Move from layer-based folders to feature/domain slices so agents, tools, approvals, and audit work are easier to change independently.
- Add pagination, filtering, and search for audit logs and approvals.
- Add detail drawers or expandable rows in the frontend so operators can inspect `agent_id`, `tool_id`, and full payloads when needed.
- Add tool schema versioning and a real connector registry instead of hardcoded dispatch branches.
- Validate duplicate permission inputs before commit in the agent creation flow.
- Make the health endpoint minimal and split liveness from readiness.
- Add a real rate-limiter backend instead of the current placeholder.
- Add create/edit UI for agents and tools, or explicitly label the dashboard as read-only.

## Security Risk Summary

- Critical
  - SSRF/open proxy via the internal API connector.
- High
  - Raw SQL exfiltration via the PostgreSQL connector.
  - Browser-stored bearer key in localStorage.
  - Plaintext API key leakage in logs and response bodies.
  - Approval double-execution / race conditions.
  - Raw audit payloads and errors stored without redaction.
- Medium / Low
  - Overly broad CORS and origin configuration for a bearer-key app.
  - Public health endpoint leaks operational metadata.

If this product may eventually handle enterprise data, the Critical and High items need to be resolved before the gateway is used beyond a local demo.

## Architecture Risk Summary

The architecture is coherent for an MVP, but the separation between registry, runtime, and approval state is still too weak for a gateway product.

- The tool registry is metadata-first but not execution-authoritative.
- REST and MCP duplicate visibility and serialization rules.
- Startup bootstrapping mutates live state instead of using migrations and a dedicated seed path.
- Approval and audit records are not yet a complete chain of custody.
- The backend is still organized by technical layers, which is workable now but will get harder as connector count and policy complexity grow.

## Recommended Implementation Order

1. Remove secret leakage and browser bearer storage.
2. Lock down the internal API connector and the PostgreSQL connector.
3. Make approval, audit, and execution atomic and attributable.
4. Add migrations and move schema/seed work out of app startup.
5. Redact audit payloads and make the audit trail retention-safe.
6. Decouple the frontend from localhost and add proper readiness checks.
7. Align the registry with runtime dispatch and add output-contract validation.
8. Expand operator UX for approvals, audit inspection, and identity visibility.

## Report Files

The six specialist review files are available here:

- [reviews/01_architecture_review.md](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/reviews/01_architecture_review.md)
- [reviews/02_backend_review.md](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/reviews/02_backend_review.md)
- [reviews/03_security_review.md](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/reviews/03_security_review.md)
- [reviews/04_agent_flows_review.md](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/reviews/04_agent_flows_review.md)
- [reviews/05_frontend_review.md](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/reviews/05_frontend_review.md)
- [reviews/06_devops_runtime_review.md](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/reviews/06_devops_runtime_review.md)

