import { auth } from "./firebase";
import type { Auth } from "firebase/auth";

const BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;
  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

async function authHeader(custom?: Auth): Promise<Record<string, string>> {
  const a = custom ?? auth();
  const user = a.currentUser;
  if (!user) return {};
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  opts: { auth?: Auth; admin?: boolean; csrf?: string } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (!opts.admin) {
    Object.assign(headers, await authHeader(opts.auth));
  }
  if (opts.csrf) headers["X-CSRF-Token"] = opts.csrf;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: opts.admin ? "include" : "same-origin",
  });

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    const err = data.error ?? {};
    throw new ApiError(res.status, err.code ?? "error", err.message ?? "Erro", err.requestId);
  }
  return data as T;
}

export const api = {
  get: <T>(p: string, o?: { auth?: Auth; admin?: boolean }) => request<T>("GET", p, undefined, o),
  post: <T>(p: string, b?: unknown, o?: { auth?: Auth; admin?: boolean; csrf?: string }) =>
    request<T>("POST", p, b, o),
  patch: <T>(p: string, b?: unknown, o?: { admin?: boolean; csrf?: string }) =>
    request<T>("PATCH", p, b, o),
  del: <T>(p: string, o?: { admin?: boolean; csrf?: string }) =>
    request<T>("DELETE", p, undefined, o),
};
