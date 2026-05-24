# Architecture Review - Agent Gateway

Overall assessment: the MVP has a coherent shape and the main product concepts are in the right place, but a few architectural seams are already showing. The biggest risks are startup side effects, a registry/runtime mismatch for tools, and an approval/audit flow that is not yet strong enough for enterprise-grade side effects.

## Architecture Issues

### 1. Startup bootstrapping mutates runtime state
Priority: P1

Evidence: [backend/app/main.py:27](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L27), [backend/app/main.py:31](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/main.py#L31), [backend/app/database.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/database.py#L34), [backend/app/seed.py:145](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/seed.py#L145)

Issue: application startup creates tables and seeds demo data inside the FastAPI lifespan. That means boot is not just "start the service"; it also mutates the database, prints a one-time API key, and assumes a blank database. A partially seeded database will not self-heal because the seed routine exits as soon as it sees any existing rows.

Recommended refactor: move table creation to explicit migrations and move demo seeding into a separate management command or one-off seed job. Keep the app lifespan focused on runtime initialization and health validation.

Missing component: a real migration path (for example Alembic) and a separate seed entrypoint.

### 2. The folder structure is layer-based, not domain-based
Priority: P2

Evidence: [README.md:53](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/README.md#L53), [backend/app/routers/agents.py:39](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L39), [backend/app/routers/approvals.py:23](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L23), [backend/app/services/execution_service.py:70](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/execution_service.py#L70)

Issue: the backend is organized into generic technical buckets (`routers`, `services`, `models`, `schemas`, `connectors`), but the actual work spans feature boundaries. Agent creation, approval handling, execution, and auditing already require touching many packages. That is acceptable for an MVP, but it will become harder to reason about as connectors and policy rules multiply.

Recommended refactor: reorganize by domain or feature slice, for example `app/features/agents`, `app/features/tools`, `app/features/approvals`, and `app/features/audit`, with each slice holding its router, service/use-case code, repository access, and schema types.

Missing component: a domain-oriented module boundary that makes ownership and change impact obvious.

### 3. Tool registry and execution are still coupled by hard-coded dispatch
Priority: P1

Evidence: [backend/app/connectors/base.py:6](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/base.py#L6), [backend/app/services/execution_service.py:43](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/execution_service.py#L43), [backend/app/schemas/tool_schema.py:112](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L112), [backend/app/schemas/tool_schema.py:141](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L141), [backend/app/routers/tools.py:62](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L62)

Issue: the registry accepts any `connector_type`, but the runtime can only execute a fixed set of hard-coded tool names and connector branches. `BaseConnector` is only a marker class, so the abstraction does not actually route execution or enforce a contract. This means the registry can advertise tools that the runtime cannot execute, and every new tool requires code changes in multiple places.

Recommended refactor: introduce a real connector interface and a registry that maps tool names or connector types to implementations. Validate connector types against an enum or registry table, and derive runtime dispatch from the same source of truth that stores the tool metadata.

Missing component: a connector manifest or registry with a concrete interface and versioned tool contract.

### 4. Approval flow is not atomic and does not record the approving actor
Priority: P0

Evidence: [backend/app/models/approval.py:21](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L21), [backend/app/models/approval.py:57](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/approval.py#L57), [backend/app/routers/approvals.py:51](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L51), [backend/app/routers/approvals.py:73](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L73), [backend/app/services/approval_service.py:107](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L107), [backend/app/services/approval_service.py:123](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/approval_service.py#L123)

Issue: approval decisions and execution are split across multiple commits with no transaction boundary, no conditional update, and no row-level lock. Two approvers can race, both observe a pending request, and both execute the side effect. The model also lacks `approved_by` or `rejected_by`, so the system cannot prove which human or API key actually made the decision. The `audit_log_id` field exists, but nothing populates it, so the intended approval-to-audit linkage is currently broken.

Recommended refactor: treat approval as a state machine. Use a conditional update such as "update only if pending", capture the acting agent on the approval record, and emit a linked approval/audit event with a correlation id. If execution remains synchronous, make the decision and the side effect part of one controlled workflow with idempotency protection.

Missing component: approver identity fields, a correlation id between approval and execution, and idempotent approval execution semantics.

### 5. Audit logs are append-only, but not yet operationally complete
Priority: P1

Evidence: [backend/app/models/audit_log.py:21](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L21), [backend/app/models/audit_log.py:34](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L34), [backend/app/models/audit_log.py:40](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/audit_log.py#L40), [backend/app/services/audit_service.py:13](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L13), [backend/app/services/audit_service.py:43](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/audit_service.py#L43), [backend/app/routers/audit.py:15](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/audit.py#L15)

Issue: the audit model stores full input and output payloads in JSONB, but it does not have a stable request/correlation id, approval reference, or retention strategy. The query path is also a simple recent-first limit, with no pagination or search contract. As the log table grows, recent scans and compliance lookups will become more expensive, and the trail will still be hard to reconstruct across approval and execution steps.

Recommended refactor: add correlation identifiers, a linked approval reference, and a retention or partitioning strategy. Expose pagination and filters in the audit API, and add indexes that match the primary access patterns (`created_at`, `agent_id`, `tool_name`).

Missing component: an evidentiary audit chain plus operational retention and query strategy.

### 6. Router handlers are doing too much application work
Priority: P2

Evidence: [backend/app/routers/agents.py:56](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L56), [backend/app/routers/agents.py:73](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L73), [backend/app/routers/tools.py:36](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L36), [backend/app/routers/approvals.py:51](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L51), [backend/app/routers/approvals.py:111](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/approvals.py#L111)

Issue: several routes are not thin HTTP adapters. They are doing authorization, ORM queries, mutation, permission mapping, and response construction in one place. That makes the same business logic harder to reuse from MCP or future jobs and makes testing the domain rules more difficult.

Recommended refactor: introduce dedicated use-case services for agent registry, tool registry, approval workflow, and audit queries. Keep routers focused on request parsing, response formatting, and dependency wiring.

Missing component: a clear application layer boundary between transport code and business workflows.

### 7. Tool metadata is not strongly constrained or versioned
Priority: P2

Evidence: [backend/app/models/tool.py:21](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/tool.py#L21), [backend/app/models/tool.py:25](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/tool.py#L25), [backend/app/models/tool.py:26](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/models/tool.py#L26), [backend/app/schemas/tool_schema.py:112](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/schemas/tool_schema.py#L112), [backend/app/routers/tools.py:70](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L70)

Issue: connector type and risk level are stored as free-form strings in the database, and the create-tool API will accept any connector type. There is no schema version on the tool registry entry, so runtime behavior, stored JSON schema, and connector implementation can drift apart over time.

Recommended refactor: constrain connector type and risk level with enums or a registry table, and add explicit tool schema versioning. Validate new or updated tools against a connector manifest before they are enabled.

Missing component: a versioned contract for tool definitions and runtime implementation.

### 8. REST and MCP repeat the same visibility and serialization rules
Priority: P2

Evidence: [backend/app/routers/tools.py:36](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L36), [backend/app/mcp_server/tools.py:38](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/mcp_server/tools.py#L38), [backend/app/routers/audit.py:15](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/audit.py#L15), [backend/app/mcp_server/tools.py:103](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/mcp_server/tools.py#L103), [backend/app/mcp_server/tools.py:127](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/mcp_server/tools.py#L127)

Issue: the REST API and the MCP layer both implement their own permission filtering and serialization for tools, audits, and approvals. The business rules are already duplicated in two transports, so any future change to visibility or output shape has to be made twice.

Recommended refactor: move tool listing, audit listing, and approval listing into shared use-case functions or presenters that return transport-agnostic DTOs. Let REST and MCP only adapt those DTOs to their respective payload formats.

Missing component: a single shared service contract for transport-neutral tool and audit queries.

## Missing Components

- A real migration workflow and explicit bootstrap command instead of `create_all` during app startup.
- An approval audit chain with approver identity, correlation ids, and a linked execution record.
- Pagination and filtering for audit logs and approvals.
- A real connector registry or manifest that defines supported connector types and versions.
- A proper rate-limiting backend instead of the current no-op placeholder.
- An integration test suite for approval, execution, and audit flows.

## What Is Working Well

- The shared API-key auth path is reused by both REST and MCP, which is a good base for consistent authorization behavior. Evidence: [backend/app/services/auth_service.py:30](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/services/auth_service.py#L30), [backend/app/mcp_server/tools.py:28](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/mcp_server/tools.py#L28), [backend/app/routers/agents.py:41](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/agents.py#L41).
- Permission-scoped tool listing is already in place for non-admin agents, which is the right direction for a gateway layer. Evidence: [backend/app/routers/tools.py:41](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/routers/tools.py#L41), [backend/app/mcp_server/tools.py:46](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/mcp_server/tools.py#L46).
- PostgreSQL read-only access is at least guarded with an explicit select-only check in the connector, which is a strong MVP safety baseline. Evidence: [backend/app/connectors/postgres_connector.py:36](/Users/priyanshupatel/Documents/GitHub/ai%20operating%20system/backend/app/connectors/postgres_connector.py#L36).
