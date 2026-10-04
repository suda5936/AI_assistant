// T-15 인수 테스트: 목록 화면 PostListPage (AC-11, 12, 13, 14, 17, 23, 25). 실제 백엔드(8015)에 붙는다.
// 테스트는 위에서 아래로 순서대로 실행되며 DB 상태(글 0개 → 10개 → 11개 → 13개)가 이어진다.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test } from "vitest";
import { login, logout, signup } from "/src/api/auth";
import { createPost } from "/src/api/posts";
import { AuthProvider } from "/src/components/AuthProvider";
import PostListPage from "/src/pages/PostListPage";

const BACKEND = path.resolve(process.cwd(), "../backend");
const BASE = String(import.meta.env.VITE_API_BASE_URL);
const PORT = new URL(BASE).port;
const PW = "valid-pw-1";
let proc: ChildProcess;
let tmp: string;
const realFetch = globalThis.fetch.bind(globalThis);

class Jar {
  cookies = new Map<string, string>();
  fetch = async (url: RequestInfo | URL, init?: RequestInit) => {
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
const uname = () => `qc_${Date.now().toString(36)}_${seq++}`.slice(0, 20);

beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t15-"));
  const env = { PATH: process.env.PATH ?? "", DATABASE_URL: `sqlite:///${tmp}/t15.db` };
  const py = path.join(BACKEND, ".venv/bin/python");
  expect(spawnSync(py, ["-m", "alembic", "upgrade", "head"], { cwd: BACKEND, env }).status).toBe(0);
  proc = spawn(py, ["-m", "uvicorn", "board.main:app", "--port", PORT, "--host", "127.0.0.1"], {
    cwd: BACKEND,
    env,
    stdio: "ignore",
  });
  for (let i = 0; i < 100; i++) {
    try {
      if ((await realFetch(`${BASE}/api/auth/me`)).status === 401) return;
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
});

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="loc">{loc.pathname + loc.search}</div>;
}

function renderList(entry = "/") {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/" element={<PostListPage />} />
          <Route path="*" element={<div>other</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </AuthProvider>,
  );
}

async function asNewUser() {
  const u = uname();
  await signup(u, PW);
  await login(u, PW);
  return u;
}
async function makePosts(titles: string[]) {
  for (const t of titles) await createPost(t, "내용 " + t);
}
const items = () => within(screen.getByRole("list", { name: "게시글 목록" })).getAllByRole("listitem");
const nav = () => screen.queryByRole("navigation", { name: "페이지 이동" });
const indicator = () => screen.getByTestId("page-indicator").textContent;
const kst = (iso: string) => {
  const d = new Date(new Date(iso).getTime() + 9 * 3600_000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
};

describe("T-15 목록 화면", () => {
  test("AC-11: 글이 없으면 '게시글이 없습니다'만 보이고 목록·페이지 이동은 없다 (비로그인)", async () => {
    renderList();
    expect(await screen.findByText("게시글이 없습니다")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "게시글 목록" })).toBeNull();
    expect(nav()).toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "게시판" })).toBeTruthy();
  });

  test("AC-17: 비로그인이면 '글쓰기' 링크 없이 로그인 안내와 /login 링크가 보인다", async () => {
    renderList();
    expect(await screen.findByText("글을 쓰려면 로그인해 주세요.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "글쓰기" })).toBeNull();
    const l = screen.getByRole("link", { name: "로그인하러 가기" });
    expect(l.getAttribute("href")).toBe("/login");
  });

  test("AC-17: 로그인하면 '글쓰기'(/posts/new) 링크가 보이고 로그인 안내는 없다", async () => {
    await asNewUser();
    renderList();
    const l = await screen.findByRole("link", { name: "글쓰기" });
    expect(l.getAttribute("href")).toBe("/posts/new");
    expect(screen.queryByText("글을 쓰려면 로그인해 주세요.")).toBeNull();
    expect(screen.queryByRole("link", { name: "로그인하러 가기" })).toBeNull();
  });

  test("AC-13: 글이 정확히 10개면 10개가 보이고 페이지 이동 UI가 없다", async () => {
    await asNewUser();
    await makePosts(Array.from({ length: 10 }, (_, i) => `ten-${String(i).padStart(2, "0")}`));
    await logout();
    jar.cookies.clear();
    renderList();
    await screen.findByRole("list", { name: "게시글 목록" });
    expect(items()).toHaveLength(10);
    expect(nav()).toBeNull();
    expect(screen.queryByTestId("page-indicator")).toBeNull();
  });

  test("AC-12: 비로그인이 최신순으로 항목(제목 링크·작성자·KST 시각)을 본다", async () => {
    renderList();
    await screen.findByRole("list", { name: "게시글 목록" });
    const rows = items();
    const titles = rows.map((r) => within(r).getAllByRole("link")[0].textContent);
    expect(titles).toEqual(Array.from({ length: 10 }, (_, i) => `ten-${String(9 - i).padStart(2, "0")}`));
    for (const r of rows) {
      const a = within(r).getAllByRole("link")[0];
      expect(a.getAttribute("href")).toMatch(/^\/posts\/[1-9][0-9]*$/);
      const t = r.querySelector("time")!;
      expect(t.textContent).toMatch(/^\d{4}-\d\d-\d\d \d\d:\d\d$/);
      expect(t.textContent).toBe(kst(t.getAttribute("datetime")!));
      expect(r.textContent).toMatch(/qc_/);
      expect(r.textContent).not.toContain("내용 ten"); // 목록에는 내용 없음
    }
  });

  test("AC-13: 글이 11개면 1페이지 10개와 '1 / 2', '다음'만 있고, 다음을 누르면 2페이지 1개와 '이전'만 있다", async () => {
    await asNewUser();
    await makePosts(["eleven-first"]);
    await logout();
    jar.cookies.clear();
    renderList();
    await screen.findByRole("list", { name: "게시글 목록" });
    expect(items()).toHaveLength(10);
    expect(nav()).not.toBeNull();
    expect(indicator()).toBe("1 / 2");
    expect(screen.queryByRole("link", { name: "이전" })).toBeNull();
    const next = screen.getByRole("link", { name: "다음" });
    expect(next.getAttribute("href")).toBe("/?page=2");
    fireEvent.click(next);
    await waitFor(() => expect(indicator()).toBe("2 / 2"));
    await waitFor(() => expect(items()).toHaveLength(1));
    expect(items()[0].textContent).toContain("ten-00");
    expect(screen.queryByRole("link", { name: "다음" })).toBeNull();
    expect(screen.getByRole("link", { name: "이전" }).getAttribute("href")).toBe("/?page=1");
  });

  test("AC-25: 제목에 HTML/스크립트를 넣어도 목록에 글자 그대로 텍스트로 나오고 요소가 생기지 않는다", async () => {
    await asNewUser();
    await createPost("<script>alert(1)</script>", "<img src=x onerror=alert(1)>");
    await createPost("<b>bold</b> & &amp;", "c");
    await logout();
    jar.cookies.clear();
    const { container } = renderList();
    await screen.findByRole("list", { name: "게시글 목록" });
    expect(screen.getByText("<script>alert(1)</script>")).toBeTruthy();
    expect(screen.getByText("<b>bold</b> & &amp;")).toBeTruthy();
    expect(container.querySelectorAll("script, img, b").length).toBe(0);
    expect(container.innerHTML).not.toContain("<script");
  });

  test("AC-14: ?page=0, -1, abc, 빈 값, 1.5는 1페이지(1 / 2)로 보정되고 URL은 그대로다", async () => {
    for (const raw of ["0", "-1", "abc", "", "1.5", "+2", "%202"]) {
      renderList(`/?page=${raw}`);
      await screen.findByRole("list", { name: "게시글 목록" });
      expect(indicator(), raw).toBe("1 / 2");
      expect(items()).toHaveLength(10);
      expect(screen.getByTestId("loc").textContent).toBe(`/?page=${raw}`);
      cleanup();
    }
  });

  test("AC-14: 마지막 페이지 초과(99999, 아주 큰 수)와 앞의 0이 붙은 값은 숫자 값대로 보정된다", async () => {
    // 글 13개 → 2페이지(10 + 3)
    for (const raw of ["99999", "99999999999999999999", "3", "0000000002"]) {
      renderList(`/?page=${raw}`);
      await waitFor(() => expect(screen.queryByTestId("page-indicator")).not.toBeNull());
      expect(indicator(), raw).toBe("2 / 2");
      await waitFor(() => expect(items()).toHaveLength(3));
      expect(screen.queryByRole("link", { name: "다음" })).toBeNull();
      cleanup();
    }
    renderList("/?page=1e3");
    await screen.findByRole("list", { name: "게시글 목록" });
    expect(indicator()).toBe("1 / 2");
  });

  test("AC-14: 보정 링크는 서버 응답의 숫자로만 만들어진다 (?page=abc에서 '다음'은 /?page=2)", async () => {
    renderList("/?page=abc");
    const next = await screen.findByRole("link", { name: "다음" });
    expect(next.getAttribute("href")).toBe("/?page=2");
  });

  test("AC-23: 로그인한 작성자에게도 목록에는 수정·삭제 버튼/링크가 없다", async () => {
    await asNewUser();
    await createPost("mine-list", "c");
    renderList();
    await screen.findByRole("link", { name: "글쓰기" });
    await screen.findByText("mine-list");
    expect(screen.queryByRole("button", { name: /수정|삭제/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /수정|삭제/ })).toBeNull();
  });

  test("AC-23: 비로그인에게도 수정·삭제가 없다", async () => {
    renderList();
    await screen.findByRole("list", { name: "게시글 목록" });
    expect(screen.queryByText(/수정|삭제/)).toBeNull();
  });

  test("오류: 서버가 500이면 role=alert로 메시지가 보이고 목록은 없다", async () => {
    globalThis.fetch = (async (url: RequestInfo | URL) => {
      if (String(url).includes("/api/auth/me")) return new Response("{}", { status: 401, headers: { "content-type": "application/json" } });
      return new Response(
        JSON.stringify({ error: { code: "internal_error", message: "일시적인 오류가 발생했습니다." } }),
        { status: 500, headers: { "content-type": "application/json" } },
      );
    }) as typeof fetch;
    renderList();
    const a = await screen.findByRole("alert");
    expect(a.textContent).toContain("일시적인 오류가 발생했습니다.");
    expect(screen.queryByRole("list", { name: "게시글 목록" })).toBeNull();
  });
});
