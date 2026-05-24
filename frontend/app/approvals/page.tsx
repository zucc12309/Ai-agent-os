"use client";

import { useEffect, useState } from "react";

import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { gatewayFetch } from "@/lib/api";
import { formatCompactJson, formatDateTime } from "@/lib/format";
import type { ApprovalRecord } from "@/lib/types";
import { useGatewaySession } from "@/lib/useGatewaySession";

export default function ApprovalsPage() {
  const { session, loading: sessionLoading } = useGatewaySession();
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyApprovalId, setBusyApprovalId] = useState<string | null>(null);

  async function refresh() {
    if (sessionLoading) {
      return;
    }
    if (!session?.authenticated) {
      setApprovals([]);
      setLoading(false);
      setError("Connect an operator API key to inspect approvals.");
      return;
    }

    setLoading(true);
    try {
      const data = await gatewayFetch<ApprovalRecord[]>("/approvals");
      setApprovals(data);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load approvals.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [session?.agent_id, sessionLoading]);

  async function handleDecision(id: string, action: "approve" | "reject") {
    const reason = window.prompt(
      action === "approve"
        ? "Optional approval note for the audit log:"
        : "Reason for rejection (optional, but recommended):",
    );

    setBusyApprovalId(id);
    try {
      await gatewayFetch(`/approvals/${id}/${action}`, {
        method: "POST",
        body: JSON.stringify({ decision_reason: reason || null }),
      });
      await refresh();
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : `Failed to ${action} approval.`);
    } finally {
      setBusyApprovalId(null);
    }
  }

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-[2rem] border border-white/10 p-6 shadow-glow">
        <h2 className="heading-font text-4xl font-semibold text-white">Approval Requests</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          High-risk and write-oriented tools create approval requests before execution. Approve or reject them here, then
          the backend will execute the tool only when the approval has been granted.
        </p>
      </section>

      {error ? (
        <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">{error}</div>
      ) : null}

      <DataTable
        headers={["Requested", "Tool", "Approval", "Execution", "Reviewed By", "Input", "Decision", "Actions"]}
        emptyMessage={loading ? "Loading approvals…" : "No approvals found."}
        rows={approvals.map((approval) => [
          <span key={`${approval.id}-requested`} className="text-slate-300">
            {formatDateTime(approval.requested_at)}
          </span>,
          <span key={`${approval.id}-tool`} className="font-semibold text-white">
            {approval.tool_name}
          </span>,
          <StatusBadge key={`${approval.id}-approval`} status={approval.approval_status} />,
          <StatusBadge key={`${approval.id}-execution`} status={approval.execution_status} />,
          <span key={`${approval.id}-reviewed-by`} className="font-mono text-xs text-slate-300">
            {approval.decided_by_agent_id ? approval.decided_by_agent_id.slice(0, 8) : "pending"}
          </span>,
          <span key={`${approval.id}-input`} className="max-w-[260px] text-slate-300">
            {formatCompactJson(approval.input_payload, 160)}
          </span>,
          <span key={`${approval.id}-decision`} className="text-slate-300">
            {approval.decision_reason ?? "—"}
          </span>,
          <div key={`${approval.id}-actions`} className="flex flex-wrap gap-2">
            {approval.approval_status === "pending" ? (
              <>
                <button
                  type="button"
                  disabled={busyApprovalId === approval.id}
                  onClick={() => void handleDecision(approval.id, "approve")}
                  className="rounded-2xl bg-mint-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-mint-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={busyApprovalId === approval.id}
                  onClick={() => void handleDecision(approval.id, "reject")}
                  className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm font-semibold text-rose-100 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Reject
                </button>
              </>
            ) : (
              <span className="text-sm text-slate-500">No action available</span>
            )}
          </div>,
        ])}
      />
    </div>
  );
}
