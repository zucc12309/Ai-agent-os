import type { AuthSessionRecord } from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

function buildApiUrl(path: string): string {
  if (!API_BASE_URL) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }
  return `${API_BASE_URL}${path}`;
}

function parseResponseBody(text: string): unknown {
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function gatewayFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  headers.set("Accept", "application/json");

  const hasBody = options.body != null;
  if (hasBody && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildApiUrl(path), {
    ...options,
    cache: "no-store",
    credentials: "include",
    headers,
  });

  const text = await response.text();
  const payload = parseResponseBody(text);

  if (!response.ok) {
    if (payload && typeof payload === "object" && "detail" in payload) {
      throw new Error(String((payload as { detail?: unknown }).detail));
    }
    if (payload && typeof payload === "object" && "message" in payload) {
      throw new Error(String((payload as { message?: unknown }).message));
    }
    throw new Error(typeof payload === "string" ? payload : `Request failed with ${response.status}`);
  }

  return payload as T;
}

export async function loginWithApiKey(apiKey: string): Promise<AuthSessionRecord> {
  return gatewayFetch<AuthSessionRecord>("/auth/session", {
    method: "POST",
    headers: {
      "X-API-Key": apiKey.trim(),
    },
  });
}

export async function logoutSession(): Promise<void> {
  await gatewayFetch<void>("/auth/session", {
    method: "DELETE",
  });
}
