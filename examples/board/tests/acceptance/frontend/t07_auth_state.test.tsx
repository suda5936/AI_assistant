// T-07 인수 테스트: 프론트 API 계층·인증 상태 (AC-6, AC-8, AC-9). 실제 백엔드(8011)를 띄워 검증한다.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test } from "vitest";
import { ApiError, request } from "/src/api/client";
import { getMe, login, logout, signup } from "/src/api/auth";
import { AuthProvider } from "/src/components/AuthProvider";
import { useAuth, type AuthContextValue } from "/src/hooks/useAuth";

const BACKEND = path.resolve(process.cwd(), "../backend");
const PORT = 8011;
const BASE = `http://127.0.0.1:${PORT}`;
const PW = "valid-pw-1";
let proc: ChildProcess;
let tmp: string;

const realFetch = globalThis.fetch.bind(globalThis);

// 브라우저 쿠키 저장소 흉내 (credentials: include)
class Jar {
  cookies = new Map<string, string>();
  lastSetCookie: string[] = [];
  fetch = async (url: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers);
    if (this.cookies.size) {
      headers.set("cookie", [...this.cookies].map(([k, v]) => `${k}=${v}`).join("; "));
    }
    const res = await realFetch(url, { ...init, headers });
    const sc = res.headers.getSetCookie();
    this.lastSetCookie = sc;
    for (const c of sc) {
      const [pair] = c.split(";");
      const i = pair.indexOf("=");
      const k = pair.slice(0, i);
      const v = pair.slice(i + 1);
      if (v === "" || v === '""' || /max-age=0/i.test(c)) this.cookies.delete(k);
      else this.cookies.set(k, v);
    }
    return res;
  };
}
let jar: Jar;
let seq = 0;
const uname = () => `qa_${Date.now().toString(36)}_${seq++}`.slice(0, 20);

beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t07-"));
  const env = { PATH: process.env.PATH ?? "", DATABASE_URL: `sqlite:///${tmp}/t07.db` };
  const py = path.join(BACKEND, ".venv/bin/python");
  const mig = spawnSync(py, ["-m", "alembic", "upgrade", "head"], { cwd: BACKEND, env });
  expect(mig.status).toBe(0);
  proc = spawn(py, ["-m", "uvicorn", "board.main:app", "--port", String(PORT), "--host", "127.0.0.1"], {
    cwd: BACKEND,
    env,
    stdio: "ignore",
  });
  for (let i = 0; i < 100; i++) {
    try {
      const r = await realFetch(`${BASE}/api/auth/me`);
      if (r.status === 401) return;
    } catch {
      /* 아직 기동 중 */
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("backend did not start");
});
afterAll(() => {
  proc?.kill();
  fs.rmSync(tmp, { recursive: true, force: true });
});
beforeEach(() => {
  jar = new Jar();
  globalThis.fetch = jar.fetch as typeof fetch;
});
afterEach(() => {
  cleanup();
  globalThis.fetch = realFetch;
  localStorage.clear();
});

async function newUser() {
  const u = uname();
  await signup(u, PW);
  return u;
}

describe("API 클라이언트", () => {
  test("AC-6: login은 User를 돌려주고 HttpOnly 세션 쿠키가 설정되며 getMe가 같은 사용자를 돌려준다", async () => {
    const u = await newUser();
    const user = await login(u, PW);
    expect(user.username).toBe(u);
    expect(jar.lastSetCookie.join(";").toLowerCase()).toContain("httponly");
    expect(JSON.stringify(user)).not.toMatch(/password|hash/i);
    expect((await getMe())?.username).toBe(u);
  });

  test("AC-6: 아이디 대문자로 로그인해도 소문자 계정으로 로그인된다", async () => {
    const u = await newUser();
    const user = await login(u.toUpperCase(), PW);
    expect(user.username).toBe(u);
  });

  test("AC-7(상태): 틀린 비밀번호와 없는 아이디는 같은 ApiError(401)이고 로그인 상태가 되지 않는다", async () => {
    const u = await newUser();
    const e1 = await login(u, "wrong-pass-1").catch((e) => e);
    const e2 = await login("nobody_zz", PW).catch((e) => e);
    for (const e of [e1, e2]) {
      expect(e).toBeInstanceOf(ApiError);
      expect(e.status).toBe(401);
      expect(e.code).toBe("invalid_credentials");
    }
    expect(e1.message).toBe(e2.message);
    expect(await getMe()).toBeNull();
  });

  test("AC-8: 비로그인 getMe는 null (예외 아님)", async () => {
    expect(await getMe()).toBeNull();
  });

  test("AC-9: logout 후 getMe는 null이고, 이전 쿠키를 재사용해도 인증되지 않는다", async () => {
    const u = await newUser();
    await login(u, PW);
    const old = new Map(jar.cookies);
    expect(old.size).toBe(1);
    await expect(logout()).resolves.toBeUndefined();
    expect(await getMe()).toBeNull();
    jar.cookies = old; // 로그아웃 전 쿠키 재전송
    expect(await getMe()).toBeNull();
  });

  test("AC-9: 로그인하지 않은 상태의 logout도 오류 없이 끝난다 (반복 호출 포함)", async () => {
    await expect(logout()).resolves.toBeUndefined();
    await expect(logout()).resolves.toBeUndefined();
  });

  test("오류 변환: 중복 가입은 409 username_taken, 검증 오류는 details를 가진 ApiError", async () => {
    const u = await newUser();
    const dup = await signup(u, PW).catch((e) => e);
    expect(dup).toBeInstanceOf(ApiError);
    expect([dup.status, dup.code]).toEqual([409, "username_taken"]);
    const bad = await signup("ab", "short").catch((e) => e);
    expect(bad.status).toBe(422);
    expect(bad.details.map((d: { field: string }) => d.field)).toEqual(["username", "password"]);
  });

  test("오류 변환: 없는 경로 404는 JSON 오류 형식, 본문이 JSON이 아니면 unknown_error", async () => {
    const e = await request("GET", "/api/nope").catch((x) => x);
    expect([e.status, e.code]).toEqual([404, "not_found"]);
    globalThis.fetch = (async () => new Response("<html>oops</html>", { status: 502 })) as typeof fetch;
    const e2 = await request("GET", "/api/x").catch((x) => x);
    expect([e2.status, e2.code, e2.message]).toEqual([502, "unknown_error", "일시적인 오류가 발생했습니다."]);
  });

  test("오류 변환: 네트워크 실패는 status 0 network_error", async () => {
    globalThis.fetch = (async () => {
      throw new TypeError("fail");
    }) as typeof fetch;
    const e = await request("GET", "/api/auth/me").catch((x) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect([e.status, e.code, e.message]).toEqual([0, "network_error", "서버에 연결할 수 없습니다."]);
  });

  test("요청 형식: 비GET은 application/json과 본문 {}를, 쿠키 전송 옵션을 보낸다", async () => {
    let seen: { url: string; init?: RequestInit } | undefined;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      seen = { url, init };
      return new Response(null, { status: 204 });
    }) as typeof fetch;
    await request("POST", "/api/auth/logout");
    expect(seen?.url).toBe(`${BASE}/api/auth/logout`);
    expect(seen?.init?.credentials).toBe("include");
    expect(new Headers(seen?.init?.headers).get("content-type")).toBe("application/json");
    expect(seen?.init?.body).toBe("{}");
  });
});

let ctx: AuthContextValue | undefined;
function Probe() {
  ctx = useAuth();
  return (
    <div>
      <span data-testid="status">{ctx.status}</span>
      <span data-testid="user">{ctx.user?.username ?? "-"}</span>
    </div>
  );
}
const mount = () =>
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

describe("AuthProvider / useAuth", () => {
  test("AC-8: 비로그인으로 마운트하면 loading 후 ready, user=null", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ready"));
    expect(screen.getByTestId("user").textContent).toBe("-");
  });

  test("AC-6: Context의 login 후 user가 설정된다", async () => {
    const u = await newUser();
    mount();
    await waitFor(() => expect(ctx?.status).toBe("ready"));
    await act(async () => {
      await ctx!.login(u, PW);
    });
    expect(screen.getByTestId("user").textContent).toBe(u);
  });

  test("AC-6: 로그인 실패는 ApiError로 던지고 user는 null 그대로", async () => {
    const u = await newUser();
    mount();
    await waitFor(() => expect(ctx?.status).toBe("ready"));
    let err: unknown;
    await act(async () => {
      err = await ctx!.login(u, "wrong-pass-1").catch((e) => e);
    });
    expect(err).toBeInstanceOf(ApiError);
    expect(screen.getByTestId("user").textContent).toBe("-");
  });

  test("AC-8: 로그인 쿠키가 있는 상태에서 새로 마운트(=새로고침)하면 user가 복원되고 저장소는 비어 있다", async () => {
    const u = await newUser();
    await login(u, PW);
    mount();
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe(u));
    expect(screen.getByTestId("status").textContent).toBe("ready");
    cleanup();
    mount(); // 한 번 더 새로고침
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe(u));
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test("AC-8: 마운트 시 getMe(GET /api/auth/me)를 한 번만 호출한다", async () => {
    let n = 0;
    const inner = jar.fetch;
    globalThis.fetch = (async (u: RequestInfo | URL, i?: RequestInit) => {
      if (String(u).endsWith("/api/auth/me")) n++;
      return inner(u, i);
    }) as typeof fetch;
    mount();
    await waitFor(() => expect(ctx?.status).toBe("ready"));
    expect(n).toBe(1);
  });

  test("AC-8: 복원 중 서버 오류(500)가 나면 user=null, ready", async () => {
    globalThis.fetch = (async () => new Response("boom", { status: 500 })) as typeof fetch;
    mount();
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ready"));
    expect(screen.getByTestId("user").textContent).toBe("-");
  });

  test("AC-9: Context의 logout 후 user=null이고 서버 세션도 끊긴다", async () => {
    const u = await newUser();
    await login(u, PW);
    const old = new Map(jar.cookies);
    mount();
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe(u));
    await act(async () => {
      await ctx!.logout();
    });
    expect(screen.getByTestId("user").textContent).toBe("-");
    jar.cookies = old;
    expect(await getMe()).toBeNull();
  });

  test("Provider 밖에서 useAuth를 부르면 Error", () => {
    const spy = console.error;
    console.error = () => {};
    try {
      expect(() => render(<Probe />)).toThrow();
    } finally {
      console.error = spy;
    }
  });
});
