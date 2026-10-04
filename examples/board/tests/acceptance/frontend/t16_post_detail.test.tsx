// T-16 인수 테스트: 상세·삭제 화면 PostDetailPage (AC-15, 16, 22, 23, 25). 실제 백엔드(8016)에 붙는다.
// 테스트는 위에서 아래로 순서대로 실행되며 DB 상태가 이어진다.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { login, signup } from "/src/api/auth";
import { createPost } from "/src/api/posts";
import { AuthProvider } from "/src/components/AuthProvider";
import PostDetailPage from "/src/pages/PostDetailPage";

const BACKEND = path.resolve(process.cwd(), "../backend");
const BASE = String(import.meta.env.VITE_API_BASE_URL);
const PORT = new URL(BASE).port;
const PW = "valid-pw-1";
let proc: ChildProcess;
let tmp: string;
const realFetch = globalThis.fetch.bind(globalThis);

class Jar {
  cookies = new Map<string, string>();
  calls: string[] = [];
  fetch = async (url: RequestInfo | URL, init?: RequestInit) => {
    this.calls.push(`${init?.method ?? "GET"} ${String(url)}`);
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
const uname = () => `qd_${Date.now().toString(36)}_${seq++}`.slice(0, 20);
const use = (j: Jar) => {
  jar = j;
  globalThis.fetch = j.fetch as typeof fetch;
};

beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t16-"));
  const env = { PATH: process.env.PATH ?? "", DATABASE_URL: `sqlite:///${tmp}/t16.db` };
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
beforeEach(() => use(new Jar()));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  globalThis.fetch = realFetch;
});

function LocationProbe() {
  const l = useLocation();
  return <div data-testid="loc">{l.pathname + l.search}</div>;
}
function renderDetail(idRaw: string | number) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[`/posts/${idRaw}`]}>
        <Routes>
          <Route path="/posts/:id" element={<PostDetailPage />} />
          <Route path="*" element={<div>other</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </AuthProvider>,
  );
}
const loc = () => screen.getByTestId("loc").textContent;
async function asNewUser() {
  const u = uname();
  await signup(u, PW);
  await login(u, PW);
  return u;
}
const apiGet = (id: string | number) => realFetch(`${BASE}/api/posts/${id}`);
const kst = (iso: string) => {
  const d = new Date(new Date(iso).getTime() + 9 * 3600_000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
};
const NOTFOUND = "게시글을 찾을 수 없습니다.";

let author = "";
let authorJar: Jar;
let postId = 0;
let postCreated = "";
const CONTENT = "첫째 줄\n둘째 줄\n\n넷째 줄";

describe("T-16 상세·삭제 화면", () => {
  test("AC-15: 비로그인도 제목·내용(줄바꿈 유지)·작성자·KST 시각을 본다", async () => {
    author = await asNewUser();
    const p = await createPost("상세 제목", CONTENT);
    postId = p.id;
    postCreated = p.created_at;
    authorJar = jar;
    use(new Jar());

    renderDetail(postId);
    expect(await screen.findByRole("heading", { level: 1, name: "상세 제목" })).toBeTruthy();
    expect(screen.getByTestId("post-author").textContent).toBe(author);
    expect(screen.getByTestId("post-created-at").textContent).toBe(kst(postCreated));
    expect(screen.getByTestId("post-created-at").textContent).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
    const c = screen.getByTestId("post-content");
    expect(c.textContent).toBe(CONTENT);
    expect(getComputedStyle(c).whiteSpace).toBe("pre-wrap");
    expect(screen.getByRole("link", { name: "목록으로" }).getAttribute("href")).toBe("/");
  });

  test("AC-23: 비로그인에는 수정·삭제가 없다", async () => {
    renderDetail(postId);
    await screen.findByRole("heading", { level: 1, name: "상세 제목" });
    await waitFor(() => expect(jar.calls.some((c) => c.includes("/api/auth/me"))).toBe(true));
    await new Promise((r) => setTimeout(r, 500));
    expect(screen.queryByRole("link", { name: "수정" })).toBeNull();
    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
  });

  test("AC-23: 남의 글에는 수정·삭제가 없다 (로그인 상태 확정 뒤에도)", async () => {
    await asNewUser();
    renderDetail(postId);
    await screen.findByRole("heading", { level: 1, name: "상세 제목" });
    await waitFor(() => expect(jar.calls.some((c) => c.includes("/api/auth/me"))).toBe(true));
    await new Promise((r) => setTimeout(r, 500));
    expect(screen.queryByRole("link", { name: "수정" })).toBeNull();
    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
  });

  test("AC-23: 작성자 본인에게는 수정(/posts/{id}/edit)·삭제가 있다", async () => {
    use(authorJar);
    renderDetail(postId);
    const edit = await screen.findByRole("link", { name: "수정" });
    expect(edit.getAttribute("href")).toBe(`/posts/${postId}/edit`);
    expect(screen.getByRole("button", { name: "삭제" })).toBeTruthy();
  });

  test("AC-16: 없는 ID·잘못된 형식 ID는 같은 안내, 형식 오류는 API 호출 없음", async () => {
    for (const raw of ["999999", "99999999", "abc", "0", "-1", "01", "1.5", "9".repeat(30), "9223372036854775808"]) {
      use(new Jar());
      const { unmount } = renderDetail(raw);
      expect(await screen.findByRole("heading", { name: NOTFOUND }), raw).toBeTruthy();
      expect(screen.getByRole("link", { name: "목록으로" }).getAttribute("href")).toBe("/");
      expect(screen.queryByTestId("post-content")).toBeNull();
      if (!/^[1-9][0-9]{0,15}$/.test(raw)) {
        expect(
          jar.calls.filter((c) => c.includes("/api/posts")),
          raw,
        ).toEqual([]);
      }
      unmount();
    }
    for (const raw of ["999999", "abc", "0", "9".repeat(30)]) {
      const r = await apiGet(raw);
      expect(r.status).toBe(404);
      expect((await r.json()).error.code).toBe("post_not_found");
    }
  });

  test("AC-25: HTML이 든 제목·내용은 글자 그대로 텍스트로 보이고 요소가 되지 않는다", async () => {
    await asNewUser();
    const p = await createPost("<script>alert(1)</script>", "<img src=x onerror=alert(1)>");
    use(new Jar());
    const { container } = renderDetail(p.id);
    expect(await screen.findByRole("heading", { level: 1 })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("<script>alert(1)</script>");
    expect(screen.getByTestId("post-content").textContent).toBe("<img src=x onerror=alert(1)>");
    expect(container.querySelectorAll("script, img").length).toBe(0);
    expect(container.innerHTML).not.toContain("<script");
    expect(container.innerHTML).not.toContain("<img");
  });

  test("AC-22: 확인 창 취소하면 요청 없이 그대로 남는다", async () => {
    use(authorJar);
    const conf = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderDetail(postId);
    fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
    expect(conf).toHaveBeenCalledTimes(1);
    expect(jar.calls.some((c) => c.startsWith("DELETE"))).toBe(false);
    expect(loc()).toBe(`/posts/${postId}`);
    expect((await apiGet(postId)).status).toBe(200);
  });

  test("AC-22: 서버 오류(500)면 alert 표시, 이동 없음, 버튼 다시 활성화", async () => {
    use(authorJar);
    const base = jar.fetch;
    globalThis.fetch = (async (url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "DELETE") {
        return new Response(
          JSON.stringify({ error: { code: "internal_error", message: "일시적인 오류가 발생했습니다." } }),
          { status: 500, headers: { "content-type": "application/json" } },
        );
      }
      return base(url, init);
    }) as typeof fetch;
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderDetail(postId);
    fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
    expect((await screen.findByRole("alert")).textContent).toContain("일시적인 오류가 발생했습니다.");
    expect(loc()).toBe(`/posts/${postId}`);
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "삭제" }) as HTMLButtonElement).disabled).toBe(false),
    );
    expect((await apiGet(postId)).status).toBe(200);
  });

  test("AC-22: 이미 삭제된 글(DELETE 404)이어도 '/'로 이동한다", async () => {
    await asNewUser();
    const p = await createPost("이미 사라질 글", "x");
    const owner = jar;
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderDetail(p.id);
    const btn = await screen.findByRole("button", { name: "삭제" });
    const del = await realFetch(`${BASE}/api/posts/${p.id}`, {
      method: "DELETE",
      headers: {
        "content-type": "application/json",
        cookie: [...owner.cookies].map(([k, v]) => `${k}=${v}`).join("; "),
      },
      body: "{}",
    });
    expect(del.status).toBe(204);
    fireEvent.click(btn);
    await waitFor(() => expect(loc()).toBe("/"));
  });

  test("AC-22: 확인 창 수락하면 삭제되고 '/'로 이동, 이후 상세는 404 안내·API 404·목록에서 사라짐", async () => {
    use(authorJar);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderDetail(postId);
    fireEvent.click(await screen.findByRole("button", { name: "삭제" }));
    await waitFor(() => expect(loc()).toBe("/"));
    cleanup();
    const r = await apiGet(postId);
    expect(r.status).toBe(404);
    expect((await r.json()).error.code).toBe("post_not_found");
    renderDetail(postId);
    expect(await screen.findByRole("heading", { name: NOTFOUND })).toBeTruthy();
    const list = await (await realFetch(`${BASE}/api/posts`)).json();
    expect(list.items.some((i: { id: number }) => i.id === postId)).toBe(false);
  });
});
