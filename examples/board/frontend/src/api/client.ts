import type { ApiErrorBody, FieldErrorDetail } from "../types/api";

export class ApiError extends Error {
  status: number;
  code: string;
  details: FieldErrorDetail[];

  constructor(status: number, code: string, message: string, details: FieldErrorDetail[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

const UNKNOWN_ERROR_MESSAGE = "일시적인 오류가 발생했습니다.";
const NETWORK_ERROR_MESSAGE = "서버에 연결할 수 없습니다.";

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null) return false;
  const error = (value as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return false;
  const { code, message } = error as { code?: unknown; message?: unknown };
  return typeof code === "string" && typeof message === "string";
}

function toFieldErrors(details: unknown): FieldErrorDetail[] {
  if (!Array.isArray(details)) return [];
  return details.filter(
    (item): item is FieldErrorDetail =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as { field?: unknown }).field === "string" &&
      typeof (item as { message?: unknown }).message === "string",
  );
}

async function toApiError(response: Response): Promise<ApiError> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return new ApiError(response.status, "unknown_error", UNKNOWN_ERROR_MESSAGE);
  }
  if (!isErrorBody(payload)) {
    return new ApiError(response.status, "unknown_error", UNKNOWN_ERROR_MESSAGE);
  }
  const { code, message, details } = payload.error;
  return new ApiError(response.status, code, message, toFieldErrors(details));
}

/** 백엔드 API를 호출한다. 2xx가 아니거나 네트워크가 실패하면 ApiError를 던진다. */
export async function request<T>(method: HttpMethod, path: string, body?: unknown): Promise<T> {
  const baseUrl: string = import.meta.env.VITE_API_BASE_URL ?? "";
  const init: RequestInit = { method, credentials: "include" };
  if (method !== "GET") {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body ?? {});
  }

  let response: Response;
  try {
    response = await fetch(baseUrl + path, init);
  } catch {
    throw new ApiError(0, "network_error", NETWORK_ERROR_MESSAGE);
  }

  if (!response.ok) {
    throw await toApiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, "unknown_error", UNKNOWN_ERROR_MESSAGE);
  }
}
