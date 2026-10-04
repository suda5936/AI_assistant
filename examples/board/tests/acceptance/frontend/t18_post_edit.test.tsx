// T-18 인수 테스트: 글 수정 화면 PostEditPage (AC-21, AC-23, AC-24 화면 쪽). 실제 백엔드(8018)에 붙는다.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from "vitest";
import { login, signup } from "/src/api/auth";
import { AuthProvider } from "/src/components/AuthProvider";
import PostEditPage from "/src/pages/PostEditPage";

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
const uname = () => `qe_${Date.now().toString(36)}_${seq++}`.slice(0, 20);
const use = (j: Jar) => {
  jar = j;
  globalThis.fetch = j.fetch as typeof fetch;
};

beforeAll(async () => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "t18-"));
  const env = { PATH: process.env.PATH ?? "", DATABASE_URL: `sqlite:///${tmp}/t18.db` };
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
function renderEdit(idRaw: string | number) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[`/posts/${idRaw}/edit`]}>
        <Routes>
          <Route path="/posts/:id/edit" element={<PostEditPage />} />
          <Route path="*" element={<div>other</div>} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>
    </AuthProvider>,
  );
}
const loc = () => screen.getByTestId("loc").textContent;
async function newUserJar() {
  const j = new Jar();
  use(j);
  const u = uname();
  await signup(u, PW);
  await login(u, PW);
  return { jar: j, username: u };
}
interface PostJson {
  id: number;
  title: string;
  content: string;
  created_at: string;
  author: { id: number; username: string };
}
async function createVia(j: Jar, title: string, content: string): Promise<PostJson> {
  const res = await j.fetch(`${BASE}/api/posts`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title, content }),
  });
  expect(res.status).toBe(201);
  return (await res.json()) as PostJson;
}
const getPostApi = async (id: number) => (await realFetch(`${BASE}/api/posts/${id}`)).json() as Promise<PostJson>;
const fill = (title: string, content: string) => {
  fireEvent.change(screen.getByLabelText("제목"), { target: { value: title } });
  fireEvent.change(screen.getByLabelText("내용"), { target: { value: content } });
};
const submit = () => fireEvent.click(screen.getByRole("button", { name: "저장" }));
const postApiCalls = () => jar.calls.filter((c) => c.includes("/api/posts"));
async function ownerOpensEdit(title = "원래 제목", content = "원래 줄1\n원래 줄2") {
  const o = await newUserJar();
  const p = await createVia(o.jar, title, content);
  use(o.jar);
  renderEdit(p.id);
  await screen.findByRole("heading", { level: 1, name: "글 수정" });
  return { ...o, post: p };
}

describe("T-18 글 수정 화면", () => {
  test("AC-21: 본인 글이면 초기값이 채워지고, 저장하면 /posts/{id}로 이동하며 상세·목록에 반영된다", async () => {
    const { post } = await ownerOpensEdit();
    expect((screen.getByLabelText("제목") as HTMLInputElement).value).toBe("원래 제목");
    expect((screen.getByLabelText("내용") as HTMLTextAreaElement).value).toBe("원래 줄1\n원래 줄2");
    expect(screen.getByText("100자 이하")).toBeTruthy();
    fill("바뀐 제목", "바뀐 줄1\n\n바뀐 줄3");
    submit();
    await waitFor(() => expect(loc()).toBe(`/posts/${post.id}`));
    const got = await getPostApi(post.id);
    expect(got.title).toBe("바뀐 제목");
    expect(got.content).toBe("바뀐 줄1\n\n바뀐 줄3");
    expect(got.created_at).toBe(post.created_at);
    expect(got.author).toEqual(post.author);
    const list = (await (await realFetch(`${BASE}/api/posts`)).json()) as {
      items: { id: number; title: string }[];
    };
    expect(list.items.find((i) => i.id === post.id)?.title).toBe("바뀐 제목");
  });

  test("AC-21: 빈 제목·공백 내용은 거부되고 글은 변하지 않으며 입력값 유지", async () => {
    const { post } = await ownerOpensEdit("원본", "원본내용");
    fill("", "새 내용");
    submit();
    expect(await screen.findByText("제목을 입력해 주세요.")).toBeTruthy();
    expect(loc()).toBe(`/posts/${post.id}/edit`);
    expect((screen.getByLabelText("내용") as HTMLTextAreaElement).value).toBe("새 내용");
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "저장" }) as HTMLButtonElement).disabled).toBe(false),
    );
    fill("새 제목", " \n\t　 ");
    submit();
    expect(await screen.findByText("내용을 입력해 주세요.")).toBeTruthy();
    expect(screen.queryByText("제목을 입력해 주세요.")).toBeNull();
    const got = await getPostApi(post.id);
    expect([got.title, got.content]).toEqual(["원본", "원본내용"]);
  });

  test("AC-21: 길이 경계 - 제목 101자·내용 5001자 거부, 100자·5000자 저장", async () => {
    const { post } = await ownerOpensEdit("원본", "원본내용");
    fill("가".repeat(101), "내용");
    submit();
    expect(await screen.findByText("제목은 100자 이하여야 합니다.")).toBeTruthy();
    fill("제목", "나".repeat(5001));
    submit();
    expect(await screen.findByText("내용은 5000자 이하여야 합니다.")).toBeTruthy();
    expect((await getPostApi(post.id)).title).toBe("원본");
    fill("가".repeat(100), "나".repeat(5000));
    submit();
    await waitFor(() => expect(loc()).toBe(`/posts/${post.id}`));
    const got = await getPostApi(post.id);
    expect(got.title.length).toBe(100);
    expect(got.content.length).toBe(5000);
  });

  test("AC-21: 수정 중 글이 삭제되면(404) 폼 위 alert, 이동 없음", async () => {
    const { jar: j, post } = await ownerOpensEdit();
    const del = await j.fetch(`${BASE}/api/posts/${post.id}`, {
      method: "DELETE",
      headers: { "content-type": "application/json" },
      body: "{}",
    });
    expect(del.status).toBe(204);
    fill("새 제목", "새 내용");
    submit();
    expect((await screen.findByRole("alert")).textContent).toContain("게시글을 찾을 수 없습니다");
    expect(loc()).toBe(`/posts/${post.id}/edit`);
  });

  test("AC-21: 서버 500은 폼 위 alert, 입력 유지, 버튼 재활성화", async () => {
    const { post } = await ownerOpensEdit();
    const real = jar.fetch;
    globalThis.fetch = (async (url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return new Response(
          JSON.stringify({ error: { code: "internal_error", message: "일시적인 오류가 발생했습니다." } }),
          { status: 500, headers: { "content-type": "application/json" } },
        );
      }
      return real(url, init);
    }) as typeof fetch;
    fill("시도 제목", "시도 내용");
    submit();
    expect((await screen.findByRole("alert")).textContent).toContain("일시적인 오류가 발생했습니다.");
    expect(loc()).toBe(`/posts/${post.id}/edit`);
    expect((screen.getByLabelText("제목") as HTMLInputElement).value).toBe("시도 제목");
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "저장" }) as HTMLButtonElement).disabled).toBe(false),
    );
  });

  test("AC-23: 남의 글 수정 화면은 폼 없이 안내만, 글은 변하지 않음", async () => {
    const a = await newUserJar();
    const post = await createVia(a.jar, "A의 글", "A의 내용");
    await newUserJar();
    renderEdit(post.id);
    expect(screen.queryByLabelText("제목")).toBeNull(); // 로그인 확인 중에도 폼이 깜빡이지 않는다
    const msg = await screen.findByText("본인이 작성한 글만 수정할 수 있습니다.");
    expect(msg.getAttribute("role")).toBe("alert");
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(screen.queryByLabelText("내용")).toBeNull();
    expect(screen.queryByRole("button", { name: "저장" })).toBeNull();
    expect(loc()).toBe(`/posts/${post.id}/edit`);
    expect(postApiCalls().some((c) => c.startsWith("PUT"))).toBe(false);
    const got = await getPostApi(post.id);
    expect([got.title, got.content]).toEqual(["A의 글", "A의 내용"]);
  });

  test("AC-23: 비로그인은 폼 없이 로그인 안내와 /login 링크", async () => {
    const a = await newUserJar();
    const post = await createVia(a.jar, "A의 글", "내용");
    use(new Jar());
    renderEdit(post.id);
    expect(await screen.findByText("글을 수정하려면 로그인해 주세요.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "로그인하러 가기" }).getAttribute("href")).toBe("/login");
    expect(screen.queryByLabelText("제목")).toBeNull();
    expect(screen.queryByRole("button", { name: "저장" })).toBeNull();
    expect(loc()).toBe(`/posts/${post.id}/edit`);
  });

  test("AC-16/23: 없는 글·잘못된 ID는 '게시글을 찾을 수 없습니다.' 안내, 폼 없음, 잘못된 ID는 API 미호출", async () => {
    await newUserJar();
    renderEdit(999999);
    expect(await screen.findByRole("heading", { name: "게시글을 찾을 수 없습니다." })).toBeTruthy();
    expect(screen.queryByLabelText("제목")).toBeNull();
    cleanup();
    for (const bad of ["abc", "0", "01", "-1", "99999999999999999999"]) {
      jar.calls.length = 0;
      renderEdit(bad);
      expect(await screen.findByRole("heading", { name: "게시글을 찾을 수 없습니다." })).toBeTruthy();
      expect(postApiCalls()).toEqual([]);
      cleanup();
    }
  });

  test("AC-24: 남의 글에 API로 PUT·DELETE는 403(빈 제목 PUT도 403), 비로그인 401, 글 불변", async () => {
    const a = await newUserJar();
    const post = await createVia(a.jar, "A의 글", "A의 내용");
    const b = await newUserJar();
    const send = (j: Jar | null, method: string, body: unknown) =>
      (j ? j.fetch : realFetch)(`${BASE}/api/posts/${post.id}`, {
        method,
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    for (const [method, body] of [
      ["PUT", { title: "해킹", content: "해킹" }],
      ["PUT", { title: "", content: "" }],
      ["DELETE", {}],
    ] as const) {
      const res = await send(b.jar, method, body);
      expect(res.status).toBe(403);
      expect(((await res.json()) as { error: { code: string } }).error.code).toBe("forbidden");
      expect((await send(null, method, body)).status).toBe(401);
    }
    const got = await getPostApi(post.id);
    expect([got.title, got.content]).toEqual(["A의 글", "A의 내용"]);
  });
});
