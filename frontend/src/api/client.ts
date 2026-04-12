// Shared frontend API client helpers.

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1"

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function apiOrigin(): string {
  return API_BASE.replace("/api/v1", "")
}

export function teacherHeaders(includeContentType = true, password?: string): HeadersInit {
  const pw = password ?? localStorage.getItem("argus_teacher_pw") ?? ""
  const headers: Record<string, string> = {
    "X-Teacher-Password": pw,
  }
  if (includeContentType) {
    headers["Content-Type"] = "application/json"
  }
  return headers
}

function makeUrl(path: string): string {
  if (path.startsWith("http")) return path
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`
}

async function errorMessage(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({}))
  const detail = (err as { detail?: string }).detail
  return detail ?? fallback
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  errorLabel = "요청 실패",
): Promise<T> {
  const res = await fetch(makeUrl(path), init)
  if (res.status === 401) {
    throw new ApiError("비밀번호가 올바르지 않습니다", res.status)
  }
  if (!res.ok) {
    throw new ApiError(await errorMessage(res, `${errorLabel}: ${res.status}`), res.status)
  }
  return res.json() as Promise<T>
}

export async function apiFetchVoid(
  path: string,
  init?: RequestInit,
  errorLabel = "요청 실패",
): Promise<void> {
  const res = await fetch(makeUrl(path), init)
  if (res.status === 401) {
    throw new ApiError("비밀번호가 올바르지 않습니다", res.status)
  }
  if (!res.ok) {
    throw new ApiError(await errorMessage(res, `${errorLabel}: ${res.status}`), res.status)
  }
}
