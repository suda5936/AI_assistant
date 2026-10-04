import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, request } from "./client";
import { getMe, login, logout, signup } from "./auth";

function mockFetch(response: Response | Error) {
  const fetchMock = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response.clone()),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("request", () => {
  it("GET은 쿠키를 포함하고 본문과 Content-Type을 보내지 않는다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, { id: 1 }));
    const result = await request<{ id: number }>("GET", "/api/auth/me");
    expect(result).toEqual({ id: 1 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/auth/me");
    expect(init.credentials).toBe("include");
    expect(init.body).toBeUndefined();
    expect(init.headers).toBeUndefined();
  });

  it("POST는 JSON 헤더와 본문을 보내고, 본문이 없으면 {}를 보낸다", async () => {
    const fetchMock = mockFetch(jsonResponse(200, {}));
    await request("POST", "/api/x", { a: 1 });
    await request("POST", "/api/y");
    const first = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const second = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(first[1].headers).toEqual({ "Content-Type": "application/json" });
    expect(first[1].body).toBe('{"a":1}');
    expect(second[1].body).toBe("{}");
  });

  it("204면 undefined를 돌려준다", async () => {
    mockFetch(new Response(null, { status: 204 }));
    await expect(request("POST", "/api/auth/logout")).resolves.toBeUndefined();
  });

  it("오류 응답을 ApiError로 바꾼다 (details 포함)", async () => {
    mockFetch(
      jsonResponse(422, {
        error: {
          code: "validation_error",
          message: "입력값을 확인해 주세요.",
          details: [{ field: "username", message: "아이디를 입력해 주세요." }],
        },
      }),
    );
    const error = await request("POST", "/api/users", {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.code).toBe("validation_error");
    expect(apiError.message).toBe("입력값을 확인해 주세요.");
    expect(apiError.details).toEqual([{ field: "username", message: "아이디를 입력해 주세요." }]);
  });

  it("details가 없으면 빈 배열이다", async () => {
    mockFetch(jsonResponse(409, { error: { code: "username_taken", message: "중복" } }));
    const error = (await request("POST", "/api/users", {}).catch((e: unknown) => e)) as ApiError;
    expect(error.details).toEqual([]);
  });

  it("JSON 오류 형식이 아니면 unknown_error로 바꾼다", async () => {
    mockFetch(new Response("<html>bad gateway</html>", { status: 502 }));
    const error = (await request("GET", "/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.code).toBe("unknown_error");
    expect(error.message).toBe("일시적인 오류가 발생했습니다.");
  });

  it("JSON이지만 오류 형식이 아니어도 unknown_error다", async () => {
    mockFetch(jsonResponse(500, { detail: "x" }));
    const error = (await request("GET", "/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("unknown_error");
  });

  it("2xx인데 본문이 JSON이 아니면 unknown_error ApiError다", async () => {
    mockFetch(new Response("<html>ok</html>", { status: 200 }));
    const error = (await request("GET", "/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(200);
    expect(error.code).toBe("unknown_error");
    expect(error.message).toBe("일시적인 오류가 발생했습니다.");
  });

  it("details에서 field·message가 문자열인 요소만 남긴다", async () => {
    mockFetch(
      jsonResponse(422, {
        error: {
          code: "validation_error",
          message: "m",
          details: [{ field: "username", message: "a" }, { field: 1, message: "b" }, null, "x", {}],
        },
      }),
    );
    const error = (await request("POST", "/api/users", {}).catch((e: unknown) => e)) as ApiError;
    expect(error.details).toEqual([{ field: "username", message: "a" }]);
  });

  it("details가 배열이 아니면 빈 배열이다", async () => {
    mockFetch(jsonResponse(422, { error: { code: "c", message: "m", details: "x" } }));
    const error = (await request("POST", "/api/users", {}).catch((e: unknown) => e)) as ApiError;
    expect(error.details).toEqual([]);
  });

  it("VITE_API_BASE_URL이 있으면 URL 앞에 붙인다", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://h");
    const fetchMock = mockFetch(jsonResponse(200, {}));
    await request("GET", "/api/x");
    const [url] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://h/api/x");
  });

  it("네트워크 실패는 status 0, network_error다", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    const error = (await request("GET", "/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(0);
    expect(error.code).toBe("network_error");
    expect(error.message).toBe("서버에 연결할 수 없습니다.");
  });
});

describe("auth api", () => {
  it("signup, login은 해당 경로로 아이디·비밀번호를 보낸다", async () => {
    const user = { id: 1, username: "abcd", created_at: "2026-01-01T00:00:00Z" };
    const fetchMock = mockFetch(jsonResponse(200, user));
    await expect(signup("abcd", "password1")).resolves.toEqual(user);
    await expect(login("abcd", "password1")).resolves.toEqual(user);
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/users");
    expect(calls[1][0]).toBe("/api/auth/login");
    expect(calls[1][1].body).toBe('{"username":"abcd","password":"password1"}');
  });

  it("logout은 POST /api/auth/logout을 보낸다", async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }));
    await logout();
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/auth/logout");
    expect(calls[0][1].method).toBe("POST");
  });

  it("getMe는 401이면 null, 성공이면 User를 돌려준다", async () => {
    mockFetch(
      jsonResponse(401, { error: { code: "unauthenticated", message: "로그인이 필요합니다." } }),
    );
    await expect(getMe()).resolves.toBeNull();
    const user = { id: 2, username: "abcd", created_at: "2026-01-01T00:00:00Z" };
    mockFetch(jsonResponse(200, user));
    await expect(getMe()).resolves.toEqual(user);
  });

  it("getMe는 401 외의 오류를 그대로 던진다", async () => {
    mockFetch(jsonResponse(500, { error: { code: "internal_error", message: "오류" } }));
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });
});
