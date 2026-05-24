# Security Review - Agent Gateway

Overall assessment: the backend has some solid baseline controls, especially hashed API keys and tool-level authorization, but it is not yet safe for sensitive enterprise data. The highest-risk problems are an SSRF/open-proxy internal API connector, a raw SQL read connector that still permits broad data exfiltration, plaintext API key exposure in logs, browser-side key storage, and a non-atomic approval flow that can double-execute write actions.

## What Is Working Well

- API keys are hashed with a pepper before storage instead of being persisted in plaintext. Evidence: [backend/app/services/auth_service.py:22](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/auth_service.py#L22), [backend/app/services/auth_service.py:26](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/auth_service.py#L26), [backend/app/models/agent.py:23](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/agent.py#L23).
- The request path reuses the same authentication dependency across REST and MCP instead of inventing a second auth mechanism. Evidence: [backend/app/services/auth_service.py:48](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/auth_service.py#L48), [backend/app/mcp_server/tools.py:28](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/mcp_server/tools.py#L28), [backend/app/routers/agents.py:41](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L41).
- Tool execution does check `enabled` and per-tool permission before calling a connector. Evidence: [backend/app/services/permission_service.py:46](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/permission_service.py#L46), [backend/app/services/execution_service.py:103](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/execution_service.py#L103).

## Findings

### 1. Internal API connector is an SSRF/open proxy

Severity: Critical

Affected files: [backend/app/schemas/tool_schema.py:96](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L96), [backend/app/schemas/tool_schema.py:97](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L97), [backend/app/schemas/tool_schema.py:99](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L99), [backend/app/schemas/tool_schema.py:101](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L101), [backend/app/connectors/internal_api_connector.py:24](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L24), [backend/app/connectors/internal_api_connector.py:37](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L37), [backend/app/connectors/internal_api_connector.py:40](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L40), [backend/app/connectors/internal_api_connector.py:43](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L43), [backend/app/connectors/internal_api_connector.py:45](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/internal_api_connector.py#L45)

Vulnerability: the internal API tool accepts an arbitrary HTTP method, path, query parameters, JSON body, and headers, then builds the final URL with `urljoin` and sends the request directly. Because `urljoin` honors absolute URLs, an agent can override the configured base URL entirely. This is an SSRF primitive and, in practice, an open outbound proxy.

Exploit scenario: an authenticated agent with permission to use `call_internal_api` can target cloud metadata endpoints, localhost admin ports, or arbitrary external services. For example, a malicious payload can set `path` to `http://169.254.169.254/latest/meta-data/iam/security-credentials/` or `http://localhost:2375/containers/json`, and can also supply attacker-controlled headers to satisfy token or auth handshakes.

Recommended fix: do not accept free-form URLs or arbitrary headers. Replace the connector with an allowlisted route map, reject absolute URLs, normalize and constrain paths to a known internal prefix, permit only a minimal method set, strip hop-by-hop and auth headers, and enforce network egress rules so the backend cannot reach sensitive internal addresses even if the connector is abused.

### 2. The PostgreSQL "safe select" tool still allows broad data exfiltration

Severity: High

Affected files: [backend/app/schemas/tool_schema.py:17](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L17), [backend/app/schemas/tool_schema.py:18](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L18), [backend/app/connectors/postgres_connector.py:36](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L36), [backend/app/connectors/postgres_connector.py:42](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L42), [backend/app/connectors/postgres_connector.py:49](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L49), [backend/app/connectors/postgres_connector.py:56](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L56), [backend/app/connectors/postgres_connector.py:60](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L60)

Vulnerability: the connector blocks obvious mutating keywords, but it still executes user-supplied SQL text directly. That is not a conventional SQL injection into a fixed query string; it is effectively arbitrary SQL execution for any agent that has permission to call the tool. There is no table, schema, or column allowlist, and no parser-based validation of the query AST.

Exploit scenario: a permitted agent can query `information_schema`, `pg_catalog`, or any business table readable by the database role and extract sensitive rows. The same path can also be used for expensive queries or recursive reads that tie up the database. In a sensitive enterprise deployment, that means "read-only" is still enough to dump confidential data.

Recommended fix: replace free-form SQL with prebuilt query templates or a strongly constrained query builder. If free-form analytics is required, parse the SQL AST and enforce an allowlist of schemas, tables, functions, and clauses, run the database role with least-privilege read access, and add a real statement timeout and row cap at the database layer rather than only an outer `LIMIT`.

### 3. Browser-side API key storage exposes the bearer credential to any script on the dashboard origin

Severity: High

Affected files: [frontend/lib/api.ts:7](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L7), [frontend/lib/api.ts:14](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L14), [frontend/lib/api.ts:21](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L21), [frontend/lib/api.ts:52](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/lib/api.ts#L52), [frontend/components/Sidebar.tsx:51](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/components/Sidebar.tsx#L51), [frontend/components/Sidebar.tsx:61](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/components/Sidebar.tsx#L61)

Vulnerability: the dashboard persists the operator API key in `localStorage` and reuses it on every request. That makes the key readable by any script running on the same origin, including injected scripts, compromised third-party bundles, malicious browser extensions, or a future XSS introduced elsewhere in the frontend.

Exploit scenario: if an attacker can execute JavaScript on the dashboard origin, they can read `localStorage["agent-gateway-api-key"]`, copy the bearer token, and then call `/agents`, `/tools`, `/approvals`, `/audit-logs`, `/execute/*`, and `/mcp` as the operator. Because the key is long-lived and bearer-based, theft is equivalent to account takeover.

Recommended fix: replace persistent client-side storage with a short-lived server session or an `HttpOnly`, `SameSite` cookie if you want browser persistence. If the MVP must stay API-key-based, keep the key only in memory, require re-entry after refresh, and add a strong Content Security Policy plus dependency review so the dashboard origin cannot be trivially scripted.

### 4. Plaintext API keys are emitted to logs and API responses

Severity: High

Affected files: [backend/app/seed.py:164](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L164), [backend/app/seed.py:189](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L189), [backend/app/seed.py:190](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L190), [backend/app/routers/agents.py:64](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L64), [backend/app/routers/agents.py:132](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L132)

Vulnerability: the seed routine prints the demo admin API key to stdout, and the create-agent endpoint returns the plaintext key in the JSON response body. The hash-at-rest story is good, but the operational handling still leaks the secret into places that often get copied into container logs, CI logs, or APM capture.

Exploit scenario: anyone who can read the backend logs gets the demo operator key and can immediately call admin-only endpoints. If the response body is recorded by a proxy, debugging tool, or application log pipeline, newly created keys can also be recovered later. That turns a bootstrap convenience into a real credential disclosure path.

Recommended fix: never print API keys to standard output or ordinary application logs. If the key must be shown once, surface it in a dedicated one-time bootstrap UI or a secured secret handoff channel, and redact `api_key` from any request/response logging middleware. Treat the seed output as a secret artifact, not a log line.

### 5. Approval decisions can race and double-execute write actions

Severity: High

Affected files: [backend/app/routers/approvals.py:58](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L58), [backend/app/routers/approvals.py:67](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L67), [backend/app/routers/approvals.py:73](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L73), [backend/app/routers/approvals.py:82](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L82), [backend/app/routers/approvals.py:118](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L118), [backend/app/services/approval_service.py:107](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L107), [backend/app/services/approval_service.py:114](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L114), [backend/app/services/execution_service.py:106](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/execution_service.py#L106)

Vulnerability: the approve path reads the approval as pending, writes the new decision in one commit, and then executes the tool in a separate step. There is no row lock, no conditional update that wins only once, and no idempotency key. Two concurrent requests can both pass the pending check before either transition is visible.

Exploit scenario: if two approvers click approve at nearly the same time, or a client retries the request, the same write action can run twice. For `send_email`, that means duplicate emails. For `append_row`, that means duplicate spreadsheet rows. For auditability, it means the trail can show a single decision while the side effect happens more than once.

Recommended fix: make approval a single atomic state transition. Use a row lock or a conditional `UPDATE ... WHERE approval_status = 'pending' RETURNING ...` pattern, record the acting approver on the approval row, and execute the tool only for the winner. Add an idempotency key or execution reference so retries cannot replay the same side effect.

### 6. Audit logs and approval records store raw payloads and errors without redaction

Severity: High

Affected files: [backend/app/services/audit_service.py:13](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L13), [backend/app/services/audit_service.py:30](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L30), [backend/app/services/audit_service.py:31](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L31), [backend/app/services/approval_service.py:24](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L24), [backend/app/services/approval_service.py:28](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L28), [backend/app/services/approval_service.py:131](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L131), [backend/app/models/audit_log.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L34), [backend/app/models/audit_log.py:35](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L35), [backend/app/models/audit_log.py:37](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L37), [backend/app/models/approval.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L34), [backend/app/models/approval.py:55](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L55), [backend/app/models/approval.py:56](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L56), [frontend/app/audit/page.tsx:81](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/audit/page.tsx#L81), [frontend/app/audit/page.tsx:84](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/audit/page.tsx#L84), [frontend/app/audit/page.tsx:87](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/audit/page.tsx#L87), [frontend/app/approvals/page.tsx:90](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/approvals/page.tsx#L90), [frontend/app/approvals/page.tsx:94](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/approvals/page.tsx#L94)

Vulnerability: every audit entry stores the full `input_payload`, `output_payload`, and `error_message`, and every approval request stores the raw input plus any execution output or error. The frontend then renders those values back to operators. There is no field-level redaction, no sensitivity classification, and no evidence of an append-only or tamper-evident log chain.

Exploit scenario: an agent that drafts an email, appends a spreadsheet row, or calls an internal API can place PII, secrets, tokens, or proprietary data into the payload. Those values are then written to Postgres and surfaced through `/audit-logs`, `/approvals`, and the MCP read tools. If the operator key is compromised, the attacker gains access not just to live actions but to the entire historical payload trail.

Recommended fix: default to metadata-only audit rows, and add explicit per-tool redaction rules for the few fields that truly need to be retained. Truncate large bodies, redact secret-bearing fields, and separate high-sensitivity payload storage into a restricted vault if the full body must be retained for compliance. If audit integrity matters, add a correlation id and a tamper-evident hash chain or external immutable sink.

### 7. The public health endpoint leaks operational metadata

Severity: Low

Affected files: [backend/app/main.py:58](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L58), [backend/app/main.py:61](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L61), [backend/app/main.py:62](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L62), [backend/app/main.py:63](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L63), [backend/app/main.py:64](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L64), [frontend/app/status/page.tsx:53](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/frontend/app/status/page.tsx#L53)

Vulnerability: `/health` is unauthenticated and returns the environment name, counts for agents, tools, approvals, and audit logs, and the MCP mount path. The public status page is built on top of that same endpoint.

Exploit scenario: an unauthenticated visitor can determine whether the service is live, how large the deployment is, and whether there is recent approval or audit activity. That is not a direct compromise, but it is avoidable reconnaissance data that helps an attacker decide when and how to target the system.

Recommended fix: keep the public health endpoint to a minimal liveness check such as `status: ok`, and move counts and environment metadata behind authenticated admin views. If you need a public status page, render only non-sensitive availability information there.

### 8. CORS is config-driven and too easy to broaden in a bearer-token design

Severity: Low

Affected files: [backend/app/main.py:41](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L41), [backend/app/main.py:44](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L44), [backend/app/main.py:46](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L46), [backend/app/config.py:25](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/config.py#L25), [backend/app/config.py:38](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/config.py#L38), [.env.example:3](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/.env.example#L3), [docker-compose.yml:23](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/docker-compose.yml#L23)

Vulnerability: the backend trusts a comma-separated `CORS_ORIGINS` value from the environment and enables `allow_credentials=True` even though the frontend uses header-based bearer auth and `credentials: "omit"`. That is not an exploit by itself with the current localhost defaults, but it becomes dangerous if production ever widens the origin list or uses a wildcard.

Exploit scenario: if a production deployment is configured with an overly broad origin or a shared parent domain, JavaScript from that origin can issue authenticated requests with the stored bearer API key. Because the key lives in browser storage, any allowed origin that can run script can abuse it.

Recommended fix: validate exact production origins at startup, reject wildcard origins for this app, and remove `allow_credentials` unless you switch to cookie-based auth. Pin the dashboard origin in deployment manifests rather than relying on an unvalidated free-form environment value.

## Summary

The codebase has a good security starting point, but it is not ready for sensitive enterprise data until the Critical and High issues above are addressed. The top blockers are the SSRF-capable internal API connector, the raw SQL select connector, the browser-stored bearer key, the plaintext key leak in bootstrap logs, the non-atomic approval flow, and the unredacted audit trail.
