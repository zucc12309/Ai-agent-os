"use client";

type StatusBadgeProps = {
  status: string;
  className?: string;
};

function getTone(status: string): string {
  const normalized = status.toLowerCase();
  if (["success", "approved", "enabled", "active", "done", "queued", "ok", "connected"].includes(normalized)) {
    return "border-emerald-500/30 bg-emerald-500/15 text-emerald-200";
  }
  if (["pending", "pending_approval", "not_run", "in_progress"].includes(normalized)) {
    return "border-amber-500/30 bg-amber-500/15 text-amber-200";
  }
  if (["rejected", "failed", "blocked", "disabled", "error", "unauthorized", "rejected"].includes(normalized)) {
    return "border-rose-500/30 bg-rose-500/15 text-rose-200";
  }
  if (["low"].includes(normalized)) {
    return "border-sky-500/30 bg-sky-500/15 text-sky-200";
  }
  if (["medium"].includes(normalized)) {
    return "border-orange-500/30 bg-orange-500/15 text-orange-200";
  }
  if (["high"].includes(normalized)) {
    return "border-red-500/30 bg-red-500/15 text-red-200";
  }
  return "border-slate-500/30 bg-slate-500/15 text-slate-200";
}

function prettifyStatus(status: string): string {
  return status.replace(/_/g, " ");
}

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${getTone(
        status,
      )} ${className}`}
    >
      {prettifyStatus(status)}
    </span>
  );
}
