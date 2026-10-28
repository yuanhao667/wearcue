import { recoverExpiredSession } from "./client-auth";

const API_ROOT = "/api/backend";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export async function parseError(response: Response) {
  try {
    const payload = await response.json() as { detail?: unknown; error?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.error === "string") return payload.error;
    if (payload.error && typeof payload.error === "object" && "message" in payload.error) {
      const message = (payload.error as { message?: unknown }).message;
      if (typeof message === "string") return message;
    }
    return `请求失败（${response.status}）`;
  } catch {
    return `请求失败（${response.status}）`;
  }
}

export async function apiJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs, ...rest } = init ?? {};
  const signals = [rest.signal, timeoutMs ? AbortSignal.timeout(timeoutMs) : null].filter(Boolean) as AbortSignal[];
  let response: Response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...rest,
      headers: { "Content-Type": "application/json", ...rest.headers },
      cache: "no-store",
      signal: signals.length ? AbortSignal.any(signals) : undefined,
    });
  } catch (error) {
    // 后端卡住时不能让页面无限等待，统一给出可重试的提示。
    if (timeoutMs && error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("请求超时，请重试或换一张更清晰的单人穿搭照", 408);
    }
    throw error;
  }
  if (response.status === 401) recoverExpiredSession();
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.json() as Promise<T>;
}

export async function apiForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { method: "POST", body: form, cache: "no-store" });
  if (response.status === 401) recoverExpiredSession();
  if (!response.ok) throw new ApiError(await parseError(response), response.status);
  return response.json() as Promise<T>;
}

export function apiAsset(path: string) {
  return `${API_ROOT}${path}`;
}
