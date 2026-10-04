// T-14 인수 테스트: api/posts, utils/postId, utils/datetime (AC-14, AC-15, AC-16 기반). 실제 백엔드(8014).
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test } from "vitest";
import { ApiError } from "/src/api/client";
import { login, logout, signup } from "/src/api/auth";
import { createPost, deletePost, getPost, getPosts, updatePost } from "/src/api/posts";
import { formatKst } from "/src/utils/datetime";

const BACKEND = path.resolve(process.cwd(), "../backend");
const PORT = 8014;
const BASE = `http://127.0.0.1:${PORT}`;
const PW = "valid-pw-1";
let proc: ChildProcess;
let tmp: string;
const realFetch = globalThis.fetch.bind(globalThis);

class Jar {
  cookies = new Map<string, string>();
  calls: { url: string; method: string; credentials?: string }[] = [];
  fetch = async (url: RequestInfo | URL, init?: RequestInit) => {
    this.calls.push({ url: String(url), method: init?.method ?? "GET", credentials: init?.credentials });
    const headers = new Headers(init?.headers);
    if (this.cookies.size) {
      headers.set("cookie", [...this.cookies].map(([k, v]) => `${k}=${v}`).join("; "));
    }
    const res = await realFetch(url, { ...init, headers });
    for (const c of res.headers.getSetCookie()) {
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
const uname = () => `qb_${Date.now().toString(36)}_${seq++}`.slice(0, 20);

beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t14-"));
  const env = { PATH: process.env.PATH ?? "", DATABASE_URL: `sqlite:///${tmp}/t14.db` };
  const py = path.join(BACKEND, ".venv/bin/python");
  expect(spawnSync(py, ["-m", "alembic", "upgrade", "head"], { cwd: BACKEND, env }).status).toBe(0);
  proc = spawn(py, ["-m", "uvicorn", "board.main:app", "--port", String(PORT), "--host", "127.0.0.1"], {
    cwd: BACKEND,
    env,
    stdio: "ignore",
  });
  for (let i = 0; i < 100; i++) {
    try {
      if ((await realFetch(`${BASE}/api/auth/me`)).status === 401) return;
    } catch {
      /* 기동 중 */
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
  globalThis.fetch = realFetch;
});

async function loggedIn() {
  const u = uname();
  await signup(u, PW);
  await login(u, PW);
  return u;
}
async function err(p: Promise<unknown>): Promise<ApiError> {
  const e = await p.then(
    () => null,
    (x) => x,
  );
  expect(e).toBeInstanceOf(ApiError);
  return e as ApiError;
}

describe("api/posts 서버 계약", () => {
  test("AC-11: 글이 없을 때 getPosts는 items=[] total=0 page=1 size=10 (파일 첫 테스트)", async () => {
    expect(await getPosts(null)).toEqual({ items: [], total: 0, page: 1, size: 10 });
  });

  test("AC-15: createPost는 Post를 돌려주고 비로그인 getPost로 같은 내용·작성자·UTC 시각이 읽힌다", async () => {
    const u = await loggedIn();
    const created = await createPost("제목", "첫줄\n둘째줄");
    expect(created.author.username).toBe(u);
    expect(created.content).toBe("첫줄\n둘째줄");
    expect(created.created_at).toMatch(/Z$/);
    await logout();
    jar.cookies.clear();
    const got = await getPost(created.id);
    expect(got).toEqual(created);
    expect(JSON.stringify(got)).not.toMatch(/password|hash/i);
  });

  test("쿠키 전송: 요청이 credentials include로 나가고 쿠키가 없으면 작성이 401", async () => {
    await loggedIn();
    await createPost("t", "c");
    expect(jar.calls.at(-1)?.credentials).toBe("include");
    jar.cookies.clear();
    const e = await err(createPost("t", "c"));
    expect([e.status, e.code]).toEqual([401, "unauthenticated"]);
  });

  test("AC-12: 목록은 최신순이고 항목에 content가 없다", async () => {
    await loggedIn();
    const a = await createPost("old-" + Date.now(), "c");
    const b = await createPost("new-" + Date.now(), "c");
    const page = await getPosts(null);
    const ids = page.items.map((i) => i.id);
    expect(ids.indexOf(b.id)).toBeLessThan(ids.indexOf(a.id));
    expect(page.items[0]).not.toHaveProperty("content");
  });

  test("AC-13: 글이 11개 이상이면 1페이지 10개, 마지막 페이지 이동 가능", async () => {
    await loggedIn();
    for (let i = 0; i < 11; i++) await createPost(`p${i}`, "c");
    const p1 = await getPosts(null);
    expect(p1.items).toHaveLength(10);
    expect(p1.total).toBeGreaterThanOrEqual(11);
    const last = Math.ceil(p1.total / 10);
    const pl = await getPosts(String(last));
    expect(pl.page).toBe(last);
    expect(pl.items.length).toBeGreaterThanOrEqual(1);
  });

  test("AC-14: 0, -1, abc, 빈 문자열, 1.5, 거대한 값, 앞의 0 값은 예외 없이 보정된다", async () => {
    await loggedIn();
    await createPost("x", "c");
    const total = (await getPosts(null)).total;
    const last = Math.max(1, Math.ceil(total / 10));
    for (const raw of ["0", "-1", "abc", "", "1.5", " 1", "-99999999999999999999"]) {
      expect((await getPosts(raw)).page, raw).toBe(1);
    }
    for (const raw of ["99999", "9".repeat(50)]) {
      expect((await getPosts(raw)).page, raw).toBe(last);
    }
    expect((await getPosts("0001")).page).toBe(1);
  });

  test("AC-14: page는 쿼리로만 인코딩되어 경로·다른 쿼리를 바꾸지 못한다", async () => {
    const sized = await getPosts("1&size=500");
    await getPosts("../1");
    await getPosts(null);
    const urls = jar.calls.map((c) => c.url);
    expect(urls[0]).toBe(`${BASE}/api/posts?page=1%26size%3D500`);
    expect(urls[1]).toContain("?page=..%2F1");
    expect(urls[2]).toBe(`${BASE}/api/posts`);
    expect(sized.size).toBe(10);
  });

  test("AC-16: 없는 글·삭제된 글의 getPost는 ApiError 404 post_not_found", async () => {
    const e = await err(getPost(99999999));
    expect([e.status, e.code]).toEqual([404, "post_not_found"]);
    await loggedIn();
    const p = await createPost("del", "c");
    await expect(deletePost(p.id)).resolves.toBeUndefined();
    const e2 = await err(getPost(p.id));
    expect([e2.status, e2.code]).toEqual([404, "post_not_found"]);
    const e3 = await err(deletePost(p.id));
    expect([e3.status, e3.code]).toEqual([404, "post_not_found"]);
  });

  test("AC-18/AC-19: 빈 제목·공백 내용·101자 제목은 422 validation_error, 100자·5000자 경계는 성공", async () => {
    await loggedIn();
    const before = (await getPosts(null)).total;
    const e1 = await err(createPost("", "c"));
    expect([e1.status, e1.code]).toEqual([422, "validation_error"]);
    expect(JSON.stringify(e1.details)).toContain("title");
    const e2 = await err(createPost("t", "   "));
    expect(e2.status).toBe(422);
    expect(JSON.stringify(e2.details)).toContain("content");
    const e3 = await err(createPost("가".repeat(101), "c"));
    expect(e3.status).toBe(422);
    expect((await getPosts(null)).total).toBe(before);
    const ok = await createPost("가".repeat(100), "나".repeat(5000));
    expect(ok.title).toHaveLength(100);
    const e4 = await err(createPost("t", "나".repeat(5001)));
    expect(e4.status).toBe(422);
  });

  test("AC-21: updatePost는 제목·내용만 바꾸고 id·작성자·created_at은 유지하며 반복 호출도 된다", async () => {
    await loggedIn();
    const p = await createPost("a", "b");
    const u1 = await updatePost(p.id, "a2", "b2");
    const u2 = await updatePost(p.id, "a2", "b2");
    expect(u2).toEqual(u1);
    expect(u1).toMatchObject({ id: p.id, title: "a2", content: "b2", created_at: p.created_at, author: p.author });
    const e = await err(updatePost(p.id, " ", "b"));
    expect([e.status, e.code]).toEqual([422, "validation_error"]);
    expect((await getPost(p.id)).title).toBe("a2");
    expect((await err(updatePost(99999999, "a", "b"))).status).toBe(404);
  });

  test("AC-24: 남의 글 updatePost·deletePost는 403 forbidden이고 글은 그대로, 비로그인은 401", async () => {
    await loggedIn();
    const p = await createPost("mine", "c");
    const ownerCookies = new Map(jar.cookies);
    jar.cookies.clear();
    await loggedIn();
    for (const f of [() => updatePost(p.id, "hack", "c"), () => deletePost(p.id)]) {
      const e = await err(f());
      expect([e.status, e.code]).toEqual([403, "forbidden"]);
    }
    jar.cookies.clear();
    for (const f of [() => updatePost(p.id, "hack", "c"), () => deletePost(p.id)]) {
      const e = await err(f());
      expect([e.status, e.code]).toEqual([401, "unauthenticated"]);
    }
    jar.cookies = ownerCookies;
    expect((await getPost(p.id)).title).toBe("mine");
  });

  test("오류 변환: 서버에 연결할 수 없으면 ApiError status 0 network_error", async () => {
    globalThis.fetch = (async () => {
      throw new TypeError("fetch failed");
    }) as typeof fetch;
    for (const f of [() => getPosts(null), () => getPost(1), () => createPost("a", "b"), () => deletePost(1)]) {
      const e = await err(f());
      expect([e.status, e.code]).toEqual([0, "network_error"]);
      expect(e.message).toBe("서버에 연결할 수 없습니다.");
    }
  });

  test("오류 변환: JSON 오류 형식이 아닌 응답은 unknown_error", async () => {
    globalThis.fetch = (async () => new Response("<html>bad gateway</html>", { status: 502 })) as typeof fetch;
    const e = await err(getPost(1));
    expect([e.status, e.code]).toEqual([502, "unknown_error"]);
    expect(e.message).toBe("일시적인 오류가 발생했습니다.");
  });
});

describe("서버 시각 변환", () => {
  test("AC-15: 서버가 준 created_at(UTC)을 formatKst로 바꾸면 +9시간 값이다", async () => {
    await loggedIn();
    const p = await createPost("t", "c");
    const d = new Date(p.created_at);
    const kst = new Date(d.getTime() + 9 * 3600_000).toISOString().slice(0, 16).replace("T", " ");
    expect(formatKst(p.created_at)).toBe(kst);
  });
});
