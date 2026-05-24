"use client";

import { useEffect, useState } from "react";

import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { gatewayFetch } from "@/lib/api";
import type { ToolRecord } from "@/lib/types";
import { useGatewaySession } from "@/lib/useGatewaySession";

export default function ToolsPage() {
  const { session, loading: sessionLoading } = useGatewaySession();
  const [tools, setTools] = useState<ToolRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionLoading) {
      return;
    }
    if (!session?.authenticated) {
      setTools([]);
      setLoading(false);
      setError("Connect an operator API key to view the tool registry.");
      return;
    }

    let active = true;
    async function load() {
      setLoading(true);
      try {
        const data = await gatewayFetch<ToolRecord[]>("/tools");
        if (active) {
          setTools(data);
          setError(null);
        }
      } catch (error) {
        if (active) {
          setError(error instanceof Error ? error.message : "Failed to load tools.");
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
        <h2 className="heading-font text-4xl font-semibold text-white">Tool Registry</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          Registered tools define the contract between agents and connectors. Each entry records schema, connector type,
          risk level, approval rules, and enablement state.
        </p>
      </section>

      {error ? (
        <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">{error}</div>
      ) : null}

      <DataTable
        headers={["Tool", "Connector", "Risk", "Approval", "Write", "Enabled"]}
        emptyMessage={loading ? "Loading tools…" : "No tools found."}
        rows={tools.map((tool) => [
          <div key={`${tool.id}-name`}>
            <div className="font-semibold text-white">{tool.tool_name}</div>
            <div className="mt-1 max-w-xl text-sm text-slate-400">{tool.description}</div>
          </div>,
          <span key={`${tool.id}-connector`} className="font-mono text-xs uppercase tracking-[0.2em] text-slate-300">
            {tool.connector_type}
          </span>,
          <StatusBadge key={`${tool.id}-risk`} status={tool.risk_level} />,
          <StatusBadge key={`${tool.id}-approval`} status={tool.requires_approval ? "pending" : "approved"} />,
          <StatusBadge key={`${tool.id}-write`} status={tool.is_write ? "high" : "low"} />,
          <StatusBadge key={`${tool.id}-enabled`} status={tool.enabled ? "enabled" : "disabled"} />,
        ])}
      />
    </div>
  );
}
