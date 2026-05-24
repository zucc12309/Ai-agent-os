"use client";

import { useEffect, useState } from "react";

import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { gatewayFetch } from "@/lib/api";
import { formatCompactJson, formatDateTime } from "@/lib/format";
import type { AuditLogRecord } from "@/lib/types";
import { useGatewaySession } from "@/lib/useGatewaySession";

export default function AuditPage() {
  const { session, loading: sessionLoading } = useGatewaySession();
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionLoading) {
      return;
    }
    if (!session?.authenticated) {
      setLogs([]);
      setLoading(false);
      setError("Connect an operator API key to inspect audit logs.");
      return;
    }

    let active = true;
    async function load() {
      setLoading(true);
      try {
        const data = await gatewayFetch<AuditLogRecord[]>("/audit-logs");
        if (active) {
          setLogs(data);
          setError(null);
        }
      } catch (error) {
        if (active) {
          setError(error instanceof Error ? error.message : "Failed to load audit logs.");
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
  }, [session?.agent_id, sessionLoading]);

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-[2rem] border border-white/10 p-6 shadow-glow">
        <h2 className="heading-font text-4xl font-semibold text-white">Audit Logs</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          Every execution attempt is recorded with the payload, status, approval state, and execution time. This is the
          operator-facing trail you can use for incident review and compliance checks.
        </p>
      </section>

      {error ? (
        <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">{error}</div>
      ) : null}

      <DataTable
        headers={["Time", "Tool", "Status", "Approval", "Duration", "Input", "Output", "Error", "Hash"]}
        emptyMessage={loading ? "Loading audit logs…" : "No audit events found."}
        rows={logs.map((log) => [
          <span key={`${log.id}-time`} className="text-slate-300">
            {formatDateTime(log.created_at)}
          </span>,
          <span key={`${log.id}-tool`} className="font-semibold text-white">
            {log.tool_name}
          </span>,
          <StatusBadge key={`${log.id}-status`} status={log.status} />,
          <StatusBadge key={`${log.id}-approval`} status={log.approval_status} />,
          <span key={`${log.id}-duration`} className="font-mono text-xs text-slate-300">
            {log.execution_time_ms} ms
          </span>,
          <span key={`${log.id}-input`} className="max-w-[280px] text-slate-300">
            {formatCompactJson(log.input_payload, 160)}
          </span>,
          <span key={`${log.id}-output`} className="max-w-[280px] text-slate-300">
            {formatCompactJson(log.output_payload, 160)}
          </span>,
          <span key={`${log.id}-error`} className="max-w-[260px] text-rose-200">
            {log.error_message ?? "—"}
          </span>,
          <span key={`${log.id}-hash`} className="font-mono text-[0.7rem] text-slate-400">
            {log.event_hash ? `${log.event_hash.slice(0, 12)}…` : "—"}
          </span>,
        ])}
      />
    </div>
  );
}
