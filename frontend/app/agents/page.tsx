"use client";

import { useEffect, useState } from "react";

import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { gatewayFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AgentRecord } from "@/lib/types";
import { useGatewaySession } from "@/lib/useGatewaySession";

export default function AgentsPage() {
  const { session, loading: sessionLoading } = useGatewaySession();
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionLoading) {
      return;
    }
    if (!session?.authenticated) {
      setAgents([]);
      setLoading(false);
      setError("Connect an operator API key to inspect agents.");
      return;
    }

    let active = true;
    async function load() {
      setLoading(true);
      try {
        const data = await gatewayFetch<AgentRecord[]>("/agents");
        if (active) {
          setAgents(data);
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load agents.");
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
        <h2 className="heading-font text-4xl font-semibold text-white">Agents</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          API keys are hashed in the backend and the browser only receives a short-lived session cookie after login. Use the
          seeded operator key to manage the starter environment and create new agent identities with restricted permissions.
        </p>
      </section>

      {error ? (
        <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">{error}</div>
      ) : null}

      <DataTable
        headers={["Agent", "Admin", "Enabled", "Allowed", "Approvable", "Key Prefix", "Last Used"]}
        emptyMessage={loading ? "Loading agents…" : "No agents found."}
        rows={agents.map((agent) => [
          <div key={`${agent.id}-name`}>
            <div className="font-semibold text-white">{agent.name}</div>
            <div className="mt-1 text-sm text-slate-400">{agent.description ?? "—"}</div>
          </div>,
          <StatusBadge key={`${agent.id}-admin`} status={agent.is_admin ? "enabled" : "disabled"} />,
          <StatusBadge key={`${agent.id}-enabled`} status={agent.enabled ? "enabled" : "disabled"} />,
          <span key={`${agent.id}-allowed`} className="text-slate-300">
            {agent.allowed_tool_names.length}
          </span>,
          <span key={`${agent.id}-approvable`} className="text-slate-300">
            {agent.approvable_tool_names.length}
          </span>,
          <span key={`${agent.id}-prefix`} className="font-mono text-xs text-mint-200">
            {agent.api_key_prefix}
          </span>,
          <span key={`${agent.id}-last`} className="text-slate-300">
            {formatDateTime(agent.last_used_at)}
          </span>,
        ])}
      />
    </div>
  );
}
