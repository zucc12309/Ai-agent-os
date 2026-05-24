"use client";

import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import { gatewayFetch } from "@/lib/api";
import type { LiveRecord, ReadinessRecord } from "@/lib/types";

export default function StatusPage() {
  const [live, setLive] = useState<LiveRecord | null>(null);
  const [ready, setReady] = useState<ReadinessRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      try {
        const [liveData, readyData] = await Promise.all([
          gatewayFetch<LiveRecord>("/health"),
          gatewayFetch<ReadinessRecord>("/ready"),
        ]);
        if (active) {
          setLive(liveData);
          setReady(readyData);
          setError(null);
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load health status.");
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
  }, []);

  const cards = [
    { label: "Database", value: ready?.database ?? "…" },
    { label: "Environment", value: live?.environment ?? "…" },
    { label: "App", value: live?.app_name ?? "…" },
    { label: "MCP", value: live?.mcp_path ?? "/mcp" },
  ];

  return (
    <div className="space-y-6">
      <section className="glass-panel rounded-[2rem] border border-white/10 p-6 shadow-glow">
        <h2 className="heading-font text-4xl font-semibold text-white">Status</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          A quick health surface for the deployment. This page stays public so you can confirm the backend is reachable before
          entering credentials in the sidebar.
        </p>
      </section>

      {error ? (
        <div className="rounded-3xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">{error}</div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="glass-panel rounded-3xl border border-white/10 p-5 shadow-glow">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">{card.label}</p>
            <p className="heading-font mt-3 text-2xl font-semibold text-white">{loading && !ready ? "…" : card.value}</p>
          </div>
        ))}
      </section>

      <section className="glass-panel rounded-[2rem] border border-white/10 p-6 shadow-glow">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="heading-font text-2xl font-semibold text-white">Service Health</h3>
            <p className="mt-2 text-sm text-slate-400">
              Liveness comes from `/health` and database readiness comes from `/ready`.
            </p>
          </div>
          <StatusBadge status={live?.status ?? "loading"} />
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">Tools</p>
            <p className="heading-font mt-2 text-3xl font-semibold text-white">{loading && !ready ? "…" : ready?.tool_count ?? 0}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">Approvals</p>
            <p className="heading-font mt-2 text-3xl font-semibold text-white">
              {loading && !ready ? "…" : ready?.approval_count ?? 0}
            </p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">Audit Events</p>
            <p className="heading-font mt-2 text-3xl font-semibold text-white">
              {loading && !ready ? "…" : ready?.audit_log_count ?? 0}
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
