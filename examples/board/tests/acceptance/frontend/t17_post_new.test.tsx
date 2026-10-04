// T-17 인수 테스트: 글쓰기 화면 PostNewPage/PostForm (AC-17, 18, 19, 20). 실제 백엔드(8017)에 붙는다.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { login, signup } from "/src/api/auth";
import { AuthProvider } from "/src/components/AuthProvider";
import PostNewPage from "/src/pages/PostNewPage";

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
const uname = () => `qn_${Date.now().toString(36)}_${seq++}`.slice(0, 20);
const use = (j: Jar) => {
  jar = j;
  globalThis.fetch = j.fetch as typeof fetch;
};

beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t17-"));
  const env = { PATH: process.env.PATH ?? "", DATABASE_URL: `sqlite:///${tmp}/t17.db` };
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
function renderNew() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/posts/new"]}>
        <Routes>
          <Route path="/posts/new" element={<PostNewPage />} />
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
const total = async () => ((await (await realFetch(`${BASE}/api/posts`)).json()) as { total: number }).total;
const fill = (title: string, content: string) => {
  fireEvent.change(screen.getByLabelText("제목"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("내용"), { target: { value: content } });
};
const submit = () => fireEvent.click(screen.getByRole("button", { name: "저장" }));
const posts = () => jar.calls.filter((c) => c.startsWith("POST ") && c.includes("/api/posts"));
async function openForm() {
  const u = await asNewUser();
  renderNew();
  await screen.findByRole("heading", { level: 1, name: "글쓰기" });
  return u;
}

describe("T-17 글쓰기 화면", () => {
  test("AC-17: 비로그인은 폼 없이 로그인 안내만 보고 POST도 없고 API는 401", async () => {
    const before = await total();
    renderNew();
    expect(await screen.findByText("글을 쓰려면 로그인해 주세요.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "로그인하러 가기" }).getAttribute("href")).toBe("/login");
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(screen.queryByLabelText("내용")).toBeNull();
    expect(screen.queryByRole("button", { name: "저장" })).toBeNull();
    expect(loc()).toBe("/posts/new");
    expect(posts()).toEqual([]);
    const res = await realFetch(`${BASE}/api/posts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ title: "t", content: "c" }),
    });
    expect(res.status).toBe(401);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("unauthenticated");
    expect(await total()).toBe(before);
  });

  test("AC-17: 로그아웃된(무효) 쿠키로도 안내만 보인다", async () => {
    await asNewUser();
    const stale = new Map(jar.cookies);
    await jar.fetch(`${BASE}/api/auth/logout`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    });
    const j = new Jar();
    j.cookies = stale;
    use(j);
    renderNew();
    expect(await screen.findByText("글을 쓰려면 로그인해 주세요.")).toBeTruthy();
    expect(screen.queryByLabelText("제목")).toBeNull();
  });

  test("AC-18: 로그인 사용자가 저장하면 /posts/{id}로 이동하고 작성자는 본인, 줄바꿈 유지", async () => {
    const u = await openForm();
    expect(screen.getByText("100자 이하")).toBeTruthy();
    expect(screen.getByText("5000자 이하, 줄바꿈은 그대로 저장됩니다")).toBeTruthy();
    const before = await total();
    const content = "첫 줄\n둘째 줄\n\n넷째 줄";
    fill("내 첫 글", content);
    submit();
    await waitFor(() => expect(loc()).toMatch(/^\/posts\/[1-9][0-9]*$/));
    const id = Number(loc()!.split("/")[2]);
    const got = (await (await realFetch(`${BASE}/api/posts/${id}`)).json()) as {
      title: string;
      content: string;
      author: { username: string };
    };
    expect(got.title).toBe("내 첫 글");
    expect(got.content).toBe(content);
    expect(got.author.username).toBe(u);
    expect(await total()).toBe(before + 1);
    expect(posts().length).toBe(1);
  });

  test("AC-19: 제목 비움 → 안내, 글 안 생김, 입력값 유지, 버튼 재활성화", async () => {
    await openForm();
    const before = await total();
    fill("", "내용만 있음");
    submit();
    expect(await screen.findByText("제목을 입력해 주세요.")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("제목을 입력해 주세요.");
    expect(loc()).toBe("/posts/new");
    expect((screen.getByLabelText("내용") as HTMLTextAreaElement).value).toBe("내용만 있음");
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "저장" }) as HTMLButtonElement).disabled).toBe(false),
    );
    expect(await total()).toBe(before);
  });

  test("AC-19: 공백·탭·줄바꿈·전각공백뿐인 제목/내용 거부", async () => {
    await openForm();
    const before = await total();
    fill("  \t\n　 ", "정상 내용");
    submit();
    expect(await screen.findByText("제목을 입력해 주세요.")).toBeTruthy();
    fill("정상 제목", " \n\t　 ");
    submit();
    expect(await screen.findByText("내용을 입력해 주세요.")).toBeTruthy();
    expect(screen.queryByText("제목을 입력해 주세요.")).toBeNull();
    expect(await total()).toBe(before);
  });

  test("AC-19: 둘 다 비면 두 메시지가 모두 보이고, 고쳐서 다시 제출하면 저장된다", async () => {
    await openForm();
    const before = await total();
    fill("", "");
    submit();
    expect(await screen.findByText("제목을 입력해 주세요.")).toBeTruthy();
    expect(await screen.findByText("내용을 입력해 주세요.")).toBeTruthy();
    expect(screen.getAllByRole("alert").length).toBe(2);
    fill("고친 제목", "고친 내용");
    submit();
    await waitFor(() => expect(loc()).toMatch(/^\/posts\/\d+$/));
    expect(await total()).toBe(before + 1);
  });

  test("AC-20: 제목 100자 저장, 101자 거부", async () => {
    await openForm();
    const before = await total();
    fill("가".repeat(101), "내용");
    submit();
    expect(await screen.findByText("제목은 100자 이하여야 합니다.")).toBeTruthy();
    expect(loc()).toBe("/posts/new");
    expect(await total()).toBe(before);
    fill("가".repeat(100), "내용");
    submit();
    await waitFor(() => expect(loc()).toMatch(/^\/posts\/\d+$/));
    const id = loc()!.split("/")[2];
    const got = (await (await realFetch(`${BASE}/api/posts/${id}`)).json()) as { title: string };
    expect(got.title).toBe("가".repeat(100));
    expect(await total()).toBe(before + 1);
  });

  test("AC-20: 내용 5000자 저장, 5001자 거부", async () => {
    await openForm();
    const before = await total();
    fill("제목", "나".repeat(5001));
    submit();
    expect(await screen.findByText("내용은 5000자 이하여야 합니다.")).toBeTruthy();
    expect(await total()).toBe(before);
    fill("제목", "나".repeat(5000));
    submit();
    await waitFor(() => expect(loc()).toMatch(/^\/posts\/\d+$/));
    expect(await total()).toBe(before + 1);
  });

  test("AC-20: 이모지 제목 100자·내용 5000자도 저장되고, 공백 101자 제목은 빈 값 오류", async () => {
    await openForm();
    const before = await total();
    fill(" ".repeat(101), "내용");
    submit();
    expect(await screen.findByText("제목을 입력해 주세요.")).toBeTruthy();
    expect(screen.queryByText("제목은 100자 이하여야 합니다.")).toBeNull();
    fill("😀".repeat(100), "😀".repeat(5000));
    submit();
    await waitFor(() => expect(loc()).toMatch(/^\/posts\/\d+$/));
    const id = loc()!.split("/")[2];
    const got = (await (await realFetch(`${BASE}/api/posts/${id}`)).json()) as { title: string; content: string };
    expect([...got.title].length).toBe(100);
    expect([...got.content].length).toBe(5000);
    expect(await total()).toBe(before + 1);
  });

  test("AC-18: 서버 오류(500)는 폼 위 alert, 이동 없음, 입력 유지", async () => {
    await openForm();
    const real = jar.fetch;
    globalThis.fetch = (async (url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST" && String(url).includes("/api/posts")) {
        return new Response(
          JSON.stringify({ error: { code: "internal_error", message: "일시적인 오류가 발생했습니다." } }),
          { status: 500, headers: { "content-type": "application/json" } },
        );
      }
      return real(url, init);
    }) as typeof fetch;
    fill("제목", "내용");
    submit();
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("일시적인 오류가 발생했습니다.")).toBeTruthy();
    expect(loc()).toBe("/posts/new");
    expect((screen.getByLabelText("제목") as HTMLInputElement).value).toBe("제목");
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "저장" }) as HTMLButtonElement).disabled).toBe(false),
    );
  });
});
