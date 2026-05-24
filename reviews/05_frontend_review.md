# Frontend Review: Agent Gateway

## Verdict
The dashboard is visually polished and the shared fetch helper is clean, but a few operator-facing flows are still too fragile for a system that can approve tool execution and expose enterprise logs. The biggest gaps are unsafe approval UX, confusing error/empty-state handling, and audit views that hide too much context for real review work.

## What Is Working
- The dashboard uses a single API wrapper in [frontend/lib/api.ts](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/lib/api.ts#L43>) to attach `X-API-Key` and normalize backend error payloads, which keeps the page components small.
- I did not find any route-name or HTTP-method mismatches between the dashboard calls and the backend endpoints.

## UI/UX Issues

### P1 - Approval actions can be triggered too easily
The approvals page asks for an optional note with `window.prompt` in [frontend/app/approvals/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/approvals/page.tsx#L43>), then immediately POSTs the decision in [frontend/app/approvals/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/approvals/page.tsx#L52>). There is no confirmation modal, no request summary, and no way to cancel the action once the prompt is dismissed. For a high-risk approval workflow, that is too easy to misclick and too weak for screen-reader/mobile users. Replace this with a modal that shows the agent, tool, and payload, and make "Cancel" actually cancel.

### P1 - Auth failures are rendered as empty states on list pages
The tools, audit, agents, and approvals pages all set an auth error string when no key is present in [frontend/app/tools/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/tools/page.tsx#L18>), [frontend/app/audit/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/audit/page.tsx#L19>), [frontend/app/agents/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/agents/page.tsx#L19>), and [frontend/app/approvals/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/approvals/page.tsx#L20>). But their tables still fall back to `No tools found`, `No audit events found`, `No agents found`, and `No approvals found` in [frontend/app/tools/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/tools/page.tsx#L67>), [frontend/app/audit/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/audit/page.tsx#L68>), [frontend/app/agents/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/agents/page.tsx#L68>), and [frontend/app/approvals/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/approvals/page.tsx#L80>). That makes access problems look like "the system has no data" instead of "you are not authenticated". The tables should be hidden or replaced with an auth gate state until the key is valid.

### P1 - Health and status pages hide failure states behind "loading" and zeros
The home page and status page both derive their badge and counters from `health?.status ?? "loading"` and `health?.tool_count ?? 0` style fallbacks in [frontend/app/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/page.tsx#L110>) and [frontend/app/status/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/status/page.tsx#L77>). If `/health` fails, the UI still looks like a loading or empty-but-valid system instead of a failed one. The error banner is present, but the main status surface is misleading. Add an explicit `error`/`unknown` state to the badge and suppress the zero-count cards when the health request fails.

### P2 - The audit and approval tables hide key context and truncate payloads
The backend already exposes `agent_id` and `tool_id` in [frontend/lib/types.ts](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/lib/types.ts#L41>) and [frontend/lib/types.ts](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/lib/types.ts#L59>), but the UI only renders tool name, status, and a compact JSON preview. The audit page truncates input and output payloads with `formatCompactJson(..., 160)` in [frontend/app/audit/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/audit/page.tsx#L82>) and the approvals page does the same for request input in [frontend/app/approvals/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/approvals/page.tsx#L91>). For a product that may handle sensitive enterprise data, that is not enough context to approve actions or investigate incidents. Add a detail drawer or expandable row, show `agent_id`/`tool_id`, and provide copy/full-view controls for payloads.

### P2 - The operator key UI does not validate or explain the active identity
The sidebar saves whatever text is entered in [frontend/components/Sidebar.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/components/Sidebar.tsx#L51>) into localStorage through [frontend/lib/api.ts](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/lib/api.ts#L14>). The field only has a placeholder, no real label, and no validation ping after save. The user cannot tell whether the saved key is valid or which agent identity it maps to. That is confusing in a shared operator console. Add a visible label, a "test key" or auto-validate step, and a current identity summary once the key is accepted.

## Broken API Calls / Integration Gaps

### No direct path or method mismatches were found
The frontend calls the expected endpoints for `/health`, `/tools`, `/agents`, `/audit-logs`, `/approvals`, and the approval decision routes. I did not find a broken route name or HTTP method in the dashboard code.

### P1 - The API base URL is build-time only and falls back to localhost
`API_BASE_URL` defaults to `http://localhost:8000` in [frontend/lib/api.ts](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/lib/api.ts#L1>). Because Next.js inlines `NEXT_PUBLIC_*` values at build time, any deployment that forgets to inject the variable will ship a client that points at the wrong host. That is a deployment breaker for anything beyond local development. Use a same-origin proxy or runtime config instead of a hardcoded localhost fallback.

### P2 - The home page loses partial data when one panel request fails
The home page loads approvals and audit logs in a single `Promise.all` block in [frontend/app/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/page.tsx#L48>). If either request fails, both panels are treated as failed and any successful response is discarded. That is a bad operator experience because one unauthorized section can blank out another valid section. Switch to independent fetch state or `Promise.allSettled` so a partial failure does not wipe the rest of the dashboard.

## Missing States

### P2 - The shared table component has no first-class loading, error, or retry state
`DataTable` in [frontend/components/DataTable.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/components/DataTable.tsx#L12>) only knows how to render headers, rows, and a static empty message. Every page has to layer error banners and ad hoc loading text around it. That is why the current UX cannot show a retry button or a proper skeleton state. Give the table an explicit loading/error slot or add per-page empty/loading/error subviews.

### P2 - The dashboard is read-only even though the backend exposes create endpoints
The frontend only lists agents and tools in [frontend/app/agents/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/agents/page.tsx#L52>) and [frontend/app/tools/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/tools/page.tsx#L51>). The backend already exposes `POST /agents` in [backend/app/routers/agents.py](</Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/agents.py#L56>) and `POST /tools` in [backend/app/routers/tools.py](</Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/tools.py#L62>), but there is no UI to create or edit them. The copy in the agents page also says operators can "create new agent identities", which the UI does not actually support. Either add creation flows or explicitly label the dashboard as read-only.

### P2 - There is no filtering, pagination, or search on the log-heavy views
The audit and approval pages render flat tables only in [frontend/app/audit/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/audit/page.tsx#L66>) and [frontend/app/approvals/page.tsx](</Users/priyanshupatel/Documents/GitHub/ai operating system/frontend/app/approvals/page.tsx#L78>). The backend already caps those lists at 200 rows in [backend/app/routers/audit.py](</Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/audit.py#L21>) and [backend/app/routers/approvals.py](</Users/priyanshupatel/Documents/GitHub/ai operating system/backend/app/routers/approvals.py#L28>), so these views will become hard to use quickly once real usage starts. Add at least server-side search/filter controls and pagination.

## Recommended Improvements
1. Replace the approval prompt with a confirmation modal that shows the full request context and requires an explicit confirm/reject action.
2. Separate authenticated, unauthorized, loading, empty, and failed states on every list page and on the health dashboard.
3. Add expand/copy/detail controls for audit and approval payloads, along with visible `agent_id` and `tool_id` fields.
4. Remove the build-time localhost fallback and use runtime or same-origin API configuration.
5. Add either create/edit flows for agents and tools or a clear read-only label, plus search/pagination for logs and approvals.
