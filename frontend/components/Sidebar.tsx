"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { loginWithApiKey, logoutSession } from "@/lib/api";
import { notifyGatewaySessionChanged, useGatewaySession } from "@/lib/useGatewaySession";
import { StatusBadge } from "./StatusBadge";

const NAV_ITEMS = [
  { href: "/", label: "Command Center" },
  { href: "/status", label: "Status" },
  { href: "/tools", label: "Tools" },
  { href: "/audit", label: "Audit Logs" },
  { href: "/approvals", label: "Approvals" },
  { href: "/agents", label: "Agents" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { session, loading } = useGatewaySession();
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleConnect() {
    const apiKey = apiKeyInput.trim();
    if (!apiKey) {
      setError("Paste an operator API key to connect.");
      return;
    }

    setBusy(true);
    try {
      await loginWithApiKey(apiKey);
      setApiKeyInput("");
      setError(null);
      notifyGatewaySessionChanged();
    } catch (connectError) {
      setError(connectError instanceof Error ? connectError.message : "Failed to connect.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    setBusy(true);
    try {
      await logoutSession();
      setError(null);
      notifyGatewaySessionChanged();
    } catch (disconnectError) {
      setError(disconnectError instanceof Error ? disconnectError.message : "Failed to disconnect.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="glass-panel flex w-full flex-col gap-6 border-b border-white/10 px-5 py-6 lg:w-[320px] lg:min-h-screen lg:border-b-0 lg:border-r lg:sticky lg:top-0">
      <div className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-mint-500/20 bg-mint-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-mint-200">
          Agent Gateway
        </div>
        <div>
          <h1 className="heading-font text-2xl font-semibold text-white">Secure agent access, in one layer.</h1>
          <p className="mt-2 text-sm leading-6 text-slate-400">
            Authenticate once, then inspect tools, approvals, audit trails, and MCP activity from the same control plane.
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.24em] text-slate-400">Operator Key</p>
            <p className="text-xs text-slate-500">Managed by a secure session cookie after login.</p>
          </div>
          <StatusBadge status={session?.authenticated ? "enabled" : "disabled"} />
        </div>
        <input
          type="password"
          value={apiKeyInput}
          onChange={(event) => setApiKeyInput(event.target.value)}
          placeholder="Paste operator API key here"
          className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100 outline-none ring-0 transition placeholder:text-slate-600 focus:border-mint-400/50 focus:outline-none"
        />
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => void handleConnect()}
            disabled={busy || loading}
            className="rounded-2xl bg-mint-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-mint-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Connect
          </button>
          <button
            type="button"
            onClick={() => {
              setApiKeyInput("");
              void handleLogout();
            }}
            disabled={busy || loading}
            className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Disconnect
          </button>
        </div>
        {error ? <p className="mt-3 text-xs text-rose-200">{error}</p> : null}
        {session?.authenticated ? (
          <div className="mt-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-100">
            <div className="font-semibold">{session.agent_name}</div>
            <div className="mt-1">Prefix: {session.api_key_prefix}</div>
            <div className="mt-1">Session expires: {new Date(session.session_expires_at).toLocaleString()}</div>
          </div>
        ) : null}
      </div>

      <nav className="grid grid-cols-2 gap-2 lg:grid-cols-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-2xl border px-4 py-3 text-sm font-medium transition ${
                active
                  ? "border-mint-400/40 bg-mint-500/10 text-white shadow-glow"
                  : "border-white/10 bg-white/5 text-slate-300 hover:border-white/20 hover:bg-white/10"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-xs leading-6 text-slate-400">
        <p className="font-semibold uppercase tracking-[0.24em] text-slate-300">Local demo flow</p>
        <p className="mt-2">
          The seeded operator key is configured through environment variables and exchanged for an HttpOnly session cookie
          after login. The browser never stores the raw API key.
        </p>
      </div>
    </aside>
  );
}
