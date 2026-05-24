# Backend Code Review: Agent Gateway

## Executive Summary

The backend has a solid MVP foundation, but I did not find any P0 blockers that make the code obviously unbootable. The highest-risk problems are around audit integrity, approval attribution, and transaction boundaries: several failure paths are not audited, approvals do not record who approved them, and approval/audit/execution state is split across multiple commits.

The most important fixes before using this with real enterprise data are:

- Make execution failures and denied attempts auditable.
- Record the approver identity and prevent self-approval if separation of duties matters.
- Remove audit-log deletion paths and make approval/result writes atomic.
- Tighten SQL validation and registry validation so the tool layer cannot drift from the executor.

## Findings

### 1. [P1] Denied and malformed executions bypass audit logging

**Exact file path:** [backend/app/services/execution_service.py:103](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/execution_service.py#L103), [backend/app/services/execution_service.py:104](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/execution_service.py#L104), [backend/app/services/execution_service.py:145](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/execution_service.py#L145)

**Issue:** The permission check and tool-input validation happen before the `try` block that writes audit records. If `assert_agent_can_execute_tool()` rejects a request, or `model_validate()` raises a Pydantic validation error, the request exits without any audit entry. In the approval path, that can also leave an approval row stuck in `approved` or `pending` without a matching execution audit/result update.

**Why it matters:** The product requirement says every attempt should be audit logged. Right now, unauthorized calls and malformed payloads can disappear from the trail entirely, which is a serious observability and compliance gap for a gateway handling sensitive business tools.

**Suggested fix:** Move permission and payload validation into an audited path, or create an audit stub before validation and update it on success/failure. Catch `ValidationError` explicitly and return a proper 422/400 while still logging the rejected attempt. For approval-driven execution, update the approval row and audit record in the same workflow transaction.

### 2. [P1] Approval decisions do not record who approved them, and self-approval is possible

**Exact file path:** [backend/app/models/approval.py:21](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/models/approval.py#L21), [backend/app/models/approval.py:57](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/models/approval.py#L57), [backend/app/routers/approvals.py:66](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/approvals.py#L66), [backend/app/routers/approvals.py:79](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/approvals.py#L79)

**Issue:** `ApprovalRequest` stores the requester, tool, and decision timestamps, but it does not store `approved_by` or `rejected_by`. The approval routes also never persist the current approver identity. Because the only authorization check is `can_approve`, a single agent can approve its own request if it has both execute and approve permissions.

**Why it matters:** This breaks the accountability model for human approvals. You cannot reconstruct who actually authorized the action, and the current design does not enforce separation of duties. For enterprise use, that is a major control failure.

**Suggested fix:** Add a `decided_by_agent_id` field, or separate `approved_by_agent_id` / `rejected_by_agent_id` fields, and persist the current agent in the approve/reject routes. If self-approval is not allowed, add an explicit guard that rejects `approval.agent_id == current_agent.id`.

### 3. [P1] Approval, audit, and execution writes are split across independent commits

**Exact file path:** [backend/app/services/approval_service.py:34](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/approval_service.py#L34), [backend/app/services/approval_service.py:118](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/approval_service.py#L118), [backend/app/services/approval_service.py:136](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/approval_service.py#L136), [backend/app/services/audit_service.py:38](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/audit_service.py#L38), [backend/app/models/approval.py:57](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/models/approval.py#L57)

**Issue:** `create_approval_request()`, `mark_approval_decision()`, `mark_execution_result()`, `log_audit_event()`, and `authenticate_api_key_value()` all commit on their own. That means the approval row, audit row, and execution result can diverge on partial failure. The `ApprovalRequest.audit_log_id` column exists, but no code ever writes to it, so there is also no durable link from the approval record to the audit record that produced the final action.

**Why it matters:** A gateway for enterprise tools needs a consistent chain of custody. Right now a connector can succeed, the audit write can fail, and the approval row can remain in an impossible state. In the other direction, a log can be written even though the approval result never gets updated. That makes both troubleshooting and compliance reviews much harder.

**Suggested fix:** Stop committing inside the helper functions where possible. Use one `async with session.begin():` block per workflow, and let the route/service orchestration commit once after all related rows are updated. Set `audit_log_id` when the final execution audit row is created, or add an `approval_request_id` on `AuditLog` if that is the cleaner relationship.

### 4. [P1] Audit history can be deleted by ORM/database cascades

**Exact file path:** [backend/app/models/audit_log.py:21](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/models/audit_log.py#L21), [backend/app/models/tool.py:47](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/models/tool.py#L47)

**Issue:** `AuditLog.agent_id` is defined with `ondelete="CASCADE"`, so removing an agent can erase its audit rows. In addition, `Tool.audit_logs` is configured with `cascade="all, delete-orphan"`, which conflicts with audit retention and can delete audit history if a tool is removed through the ORM.

**Why it matters:** Audit logs should be treated as immutable evidence. Losing them through a routine delete turns the log into a weak operational artifact instead of a compliance-grade record.

**Suggested fix:** Keep audit logs forever unless you have a separate retention job. Change the agent/tool relationships to preserve audit rows, preferably with `SET NULL` or `RESTRICT`, and remove `delete-orphan` from the audit-log relationship.

### 5. [P2] MCP audit lookup does not match the REST API for admins

**Exact file path:** [backend/app/mcp_server/tools.py:104](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/mcp_server/tools.py#L104), [backend/app/mcp_server/tools.py:109](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/mcp_server/tools.py#L109)

**Issue:** The MCP `get_audit_logs` tool always filters by `agent.id`, even when the caller is an admin. The REST endpoint gives admins the full audit feed, but the MCP path does not.

**Why it matters:** Operators using MCP get a narrower and inconsistent view of the system than operators using REST. That makes the support story confusing and reduces the usefulness of the MCP surface for admin workflows.

**Suggested fix:** Mirror the REST route’s admin logic. If `agent.is_admin` is true, call `list_audit_logs(..., agent_id=None, ...)`; otherwise filter to the current agent.

### 6. [P2] Startup seeding is not safe for concurrent boots or partial state

**Exact file path:** [backend/app/main.py:27](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/main.py#L27), [backend/app/seed.py:154](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/seed.py#L154), [backend/app/seed.py:188](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/seed.py#L188)

**Issue:** The app seeds data from the FastAPI lifespan, and `seed_database()` returns early if either tools or agents already exist. That is not safe if multiple workers or replicas start at the same time, and it does not recover from partially seeded databases.

**Why it matters:** Startup can race itself, duplicate insert records, or skip critical demo data after a partial failure. For a deployment-ready starter, the bootstrap path should be deterministic and idempotent.

**Suggested fix:** Move seeding into a one-shot admin command or migration step, or guard it with a database lock and a seed-version sentinel row. Make the seed logic idempotent per entity instead of using an “any record exists” shortcut.

### 7. [P2] Safe PostgreSQL query validation is brittle and will reject valid reads

**Exact file path:** [backend/app/connectors/postgres_connector.py:21](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/connectors/postgres_connector.py#L21), [backend/app/connectors/postgres_connector.py:36](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/connectors/postgres_connector.py#L36), [backend/app/connectors/postgres_connector.py:45](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/connectors/postgres_connector.py#L45)

**Issue:** The `SELECT`-only guard uses raw regex scans over the query text. A harmless query such as `SELECT 'update' AS label` or a comment containing `drop` will be rejected even though it is read-only. The safety check is also not a real SQL parser.

**Why it matters:** The core PostgreSQL read path can refuse valid business queries unpredictably. That is a correctness problem, not just a security hardening concern.

**Suggested fix:** Validate the SQL structurally instead of scanning raw text. A proper AST/token-based check, combined with a read-only DB role, is much safer and far less brittle than regexing the raw query body.

### 8. [P2] Duplicate tool permissions turn into constraint failures instead of validation errors

**Exact file path:** [backend/app/routers/agents.py:78](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/agents.py#L78), [backend/app/routers/agents.py:93](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/agents.py#L93)

**Issue:** `allowed_tool_names` and `approvable_tool_names` are not deduplicated. If the same tool name appears twice in either list, the route inserts duplicate `AgentToolPermission` rows and hits the `(agent_id, tool_id)` unique constraint during commit.

**Why it matters:** A simple client typo becomes a database-level failure instead of a clean validation error. That is avoidable friction in an API that is supposed to manage permissions.

**Suggested fix:** Enforce uniqueness in the schema or normalize the inputs before inserting permissions. Return a 422/400 if duplicates are supplied.

### 9. [P2] Tool registry entries are only loosely validated, and execution does not enforce output contracts

**Exact file path:** [backend/app/routers/tools.py:62](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/tools.py#L62), [backend/app/schemas/tool_schema.py:112](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/schemas/tool_schema.py#L112), [backend/app/schemas/tool_schema.py:151](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/schemas/tool_schema.py#L151), [backend/app/services/execution_service.py:145](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/services/execution_service.py#L145)

**Issue:** The create-tool route accepts arbitrary `connector_type`/`tool_name` combinations and does not validate column-length limits against the database schema. Separately, the executor validates inputs but never validates connector outputs against `TOOL_OUTPUT_MODELS`, so contract drift will still be returned to the client as a successful result.

**Why it matters:** The registry can contain records that are impossible to execute, or requests can succeed with the wrong output shape and nobody will notice until a client breaks. That is the kind of silent drift that becomes expensive in production.

**Suggested fix:** Validate tool registration against the supported execution map, add field-length validators that mirror the DB column sizes, and validate connector outputs before returning them. If the output model does not match, fail the execution and write a failed audit record.

### 10. [P2] The MCP mount path setting is ignored at runtime

**Exact file path:** [backend/app/main.py:55](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/main.py#L55), [backend/app/config.py:32](/Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/config.py#L32)

**Issue:** `Settings.mcp_mount_path` exists and is returned by the health/root endpoints, but the actual mount call is hardcoded to `"/mcp"`.

**Why it matters:** The config looks adjustable but is not. If the mount path ever needs to change for deployment or reverse-proxy reasons, the app and its advertised runtime contract will diverge.

**Suggested fix:** Mount the MCP ASGI app with `settings.mcp_mount_path` and keep the docs, health output, and reverse-proxy config aligned with that single source of truth.

## What Is Working Well

- API keys are hashed with a pepper instead of being stored in plaintext.
- Tool execution uses Pydantic models for input validation, and the PostgreSQL connector at least tries to enforce a read-only boundary.
- High-risk tools are forced through the approval gate in the execution service, which is the right default for a gateway like this.

## Bottom Line

This is a credible starter, but I would not treat it as enterprise-safe yet. The backend needs stronger audit semantics, an attributable approval trail, and tighter transaction boundaries before it should handle sensitive data or real approval workflows.
