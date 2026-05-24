"use client";

import { useEffect, useState } from "react";

import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { gatewayFetch } from "@/lib/api";
import { formatCompactJson, formatDateTime } from "@/lib/format";
import type { ApprovalRecord, AuditLogRecord, LiveRecord, ReadinessRecord } from "@/lib/types";
import { useGatewaySession } from "@/lib/useGatewaySession";

type DashboardPayload = {
  live: LiveRecord | null;
  readiness: ReadinessRecord | null;
  approvals: ApprovalRecord[];
  auditLogs: AuditLogRecord[];
  error: string | null;
};

export default function HomePage() {
  const { session } = useGatewaySession();
  const [payload, setPayload] = useState<DashboardPayload>({
    live: null,
    readiness: null,
    approvals: [],
    auditLogs: [],
    error: null,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      try {
        const [live, readiness] = await Promise.all([
          gatewayFetch<LiveRecord>("/health"),
          gatewayFetch<ReadinessRecord>("/ready"),
        ]);
        if (active) {
          setPayload((current) => ({
            ...current,
            live,
            readiness,
            error: null,
          }));
        }

        let approvals: ApprovalRecord[] = [];
        let auditLogs: AuditLogRecord[] = [];

        if (session?.authenticated) {
          [approvals, auditLogs] = await Promise.all([
            gatewayFetch<ApprovalRecord[]>("/approvals"),
            gatewayFetch<AuditLogRecord[]>("/audit-logs"),
          ]);
        }

        if (active) {
          setPayload({
            live,
            readiness,
            approvals,
            auditLogs,
            error: null,
          });
        }
      } catch (error) {
        if (active) {
          setPayload((current) => ({
            ...current,
            live: current.live,
            readiness: current.readiness,
            error: error instanceof Error ? error.message : "Failed to load dashboard data.",
          }));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [session?.agent_id]);

  const live = payload.live;
  const readiness = payload.readiness;
  const cards = [
    { label: "Tools", value: readiness?.tool_count ?? 0, tone: "enabled" },
    { label: "Agents", value: readiness?.agent_count ?? 0, tone: "active" },
    { label: "Approvals", value: readiness?.approval_count ?? 0, tone: "pending" },
    { label: "Audit Logs", value: readiness?.audit_log_count ?? 0, tone: "success" },
  ];

  return (
    <div className="space-y-8">
      <section className="glass-panel overflow-hidden rounded-[2rem] border border-white/10 p-6 shadow-glow lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-slate-300">
              Command Center
            </div>
            <h2 className="heading-font max-w-2xl text-4xl font-semibold leading-tight text-white lg:text-6xl">
              A secure control plane for agents, tools, and approvals.
            </h2>
            <p className="max-w-2xl text-base leading-7 text-slate-300">
              Agent Gateway fronts PostgreSQL, Gmail, spreadsheets, and internal APIs with API-key auth, tool-level permissions,
              approval gating, and an audit trail that stays visible to operators.
            </p>
          </div>
          <div className="grid gap-3 rounded-3xl border border-white/10 bg-black/20 p-4 text-sm text-slate-300 lg:min-w-[280px]">
            <div className="flex items-center justify-between gap-3">
              <span>Status</span>
              <StatusBadge status={live?.status ?? "loading"} />
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Database</span>
              <span className="font-medium text-white">{readiness?.database ?? "…"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Environment</span>
              <span className="font-medium text-white">{live?.environment ?? "…"}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>MCP Path</span>
              <span className="font-mono text-xs text-mint-200">{live?.mcp_path ?? "/mcp"}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="glass-panel rounded-3xl border border-white/10 p-5 shadow-glow">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">{card.label}</p>
                <p className="heading-font mt-2 text-4xl font-semibold text-white">
                  {loading && !readiness ? "…" : card.value}
                </p>
              </div>
              <StatusBadge status={card.tone} />
            </div>
          </div>
        ))}
      </section>

      {payload.error ? (
        <div className="rounded-3xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
          {payload.error}
        </div>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-2">
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="heading-font text-2xl font-semibold text-white">Recent Approvals</h3>
              <p className="text-sm text-slate-400">Requests that are waiting for human review or recently resolved.</p>
            </div>
            <StatusBadge status={session?.authenticated ? "enabled" : "disabled"} />
          </div>

          <DataTable
            headers={["Tool", "Approval", "Execution", "Requested", "Decision"]}
            emptyMessage={
              session?.authenticated ? "No approval requests found." : "Connect an operator key to unlock approval data."
            }
            rows={payload.approvals.slice(0, 5).map((approval) => [
              approval.tool_name,
              <StatusBadge key={`${approval.id}-approval`} status={approval.approval_status} />,
              <StatusBadge key={`${approval.id}-exec`} status={approval.execution_status} />,
              <span key={`${approval.id}-requested`}>{formatDateTime(approval.requested_at)}</span>,
              <span key={`${approval.id}-decision`} className="text-slate-300">
                {approval.decision_reason ?? "—"}
              </span>,
            ])}
          />
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="heading-font text-2xl font-semibold text-white">Recent Audit Logs</h3>
            <p className="text-sm text-slate-400">Every tool attempt is captured here with status, errors, and timing.</p>
          </div>

          <DataTable
            headers={["Tool", "Status", "Approval", "Duration", "Payload"]}
            emptyMessage={
              session?.authenticated ? "No audit events yet." : "Connect an operator key to unlock audit data."
            }
            rows={payload.auditLogs.slice(0, 5).map((log) => [
              log.tool_name,
              <StatusBadge key={`${log.id}-status`} status={log.status} />,
              <StatusBadge key={`${log.id}-approval`} status={log.approval_status} />,
              <span key={`${log.id}-duration`} className="font-mono text-xs text-slate-300">
                {log.execution_time_ms} ms
              </span>,
              <span key={`${log.id}-payload`} className="text-slate-300">{formatCompactJson(log.input_payload)}</span>,
            ])}
          />
        </div>
      </section>
    </div>
  );
}
