"use client";

import { useEffect, useState } from "react";

import { gatewayFetch } from "./api";
import type { AuthSessionRecord } from "./types";

export const GATEWAY_SESSION_UPDATED_EVENT = "agent-gateway-session-updated";

export function notifyGatewaySessionChanged(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(GATEWAY_SESSION_UPDATED_EVENT));
}

export function useGatewaySession(): {
  session: AuthSessionRecord | null;
  loading: boolean;
  isAuthenticated: boolean;
} {
  const [session, setSession] = useState<AuthSessionRecord | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function loadSession() {
      setLoading(true);
      try {
        const current = await gatewayFetch<AuthSessionRecord>("/auth/session");
        if (active) {
          setSession(current);
        }
      } catch {
        if (active) {
          setSession(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadSession();

    const sync = () => {
      void loadSession();
    };

    window.addEventListener(GATEWAY_SESSION_UPDATED_EVENT, sync);
    return () => {
      active = false;
      window.removeEventListener(GATEWAY_SESSION_UPDATED_EVENT, sync);
    };
  }, []);

  return {
    session,
    loading,
    isAuthenticated: session?.authenticated ?? false,
  };
}
