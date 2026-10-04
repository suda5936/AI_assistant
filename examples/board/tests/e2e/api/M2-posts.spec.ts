import { test, expect, request as pwRequest, type APIRequestContext } from "@playwright/test";
import net from "node:net";

const API = "http://127.0.0.1:8001";
const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 100000).toString(36);
const PW = "password8";

async function newUser(): Promise<{ api: APIRequestContext; name: string }> {
  const api = await pwRequest.newContext({ baseURL: API });
  const name = uid();
  expect((await api.post("/api/users", { data: { username: name, password: PW } })).status()).toBe(201);
  expect((await api.post("/api/auth/login", { data: { username: name, password: PW } })).status()).toBe(200);
  return { api, name };
}
async function total(): Promise<number> {
  const a = await pwRequest.newContext({ baseURL: API });
  const r = await a.get("/api/posts");
  const t = (await r.json()).total as number;
  await a.dispose();
  return t;
}
function errShape(body: any, code: string) {
  expect(Object.keys(body)).toEqual(["error"]);
  expect(body.error.code).toBe(code);
  expect(typeof body.error.message).toBe("string");
}

// 원문 HTTP를 소켓으로 보내 상태 코드를 돌려준다
function rawHttp(path: string, headers: string[], body: string | Buffer): Promise<number> {
  return new Promise((resolve, reject) => {
    const sock = net.connect(8001, "127.0.0.1");
    let buf = "";
    let done = false;
    const finish = (v: number | Error) => {
      if (done) return;
      done = true;
      sock.destroy();
      typeof v === "number" ? resolve(v) : reject(v);
    };
    sock.on("data", (d) => {
      buf += d.toString("latin1");
      const m = buf.match(/^HTTP\/1\.[01] (\d{3})/);
      if (m) finish(Number(m[1]));
    });
    sock.on("error", () => {
      const m = buf.match(/^HTTP\/1\.[01] (\d{3})/);
      m ? finish(Number(m[1])) : finish(new Error("no response"));
    });
    sock.on("close", () => {
      const m = buf.match(/^HTTP\/1\.[01] (\d{3})/);
      m ? finish(Number(m[1])) : finish(new Error("closed without response"));
    });
    sock.write(`POST ${path} HTTP/1.1\r\nHost: 127.0.0.1:8001\r\n${headers.join("\r\n")}\r\nConnection: close\r\n\r\n`);
    sock.write(body, () => {});
    sock.on("connect", () => {});
  });
}

test("시나리오2 AC-17: 쿠키 없이 POST /api/posts는 401, total 불변", async () => {
  const before = await total();
  const anon = await pwRequest.newContext({ baseURL: API });
  const r = await anon.post("/api/posts", { data: { title: "t", content: "c" } });
  expect(r.status()).toBe(401);
  errShape(await r.json(), "unauthenticated");
  expect(await total()).toBe(before);
});

test("시나리오9 AC-24: B가 A의 글을 PUT/DELETE하면 403, 비로그인은 401, 내용 불변", async () => {
  const a = await newUser();
  const b = await newUser();
  const created = await a.api.post("/api/posts", { data: { title: "A의 글", content: "원래 내용" } });
  expect(created.status()).toBe(201);
  const id = (await created.json()).id;

  const put = await b.api.put(`/api/posts/${id}`, { data: { title: "해킹", content: "해킹" } });
  expect(put.status()).toBe(403);
  errShape(await put.json(), "forbidden");
  const putEmpty = await b.api.put(`/api/posts/${id}`, { data: { title: "", content: "" } });
  expect(putEmpty.status()).toBe(403);
  const del = await b.api.delete(`/api/posts/${id}`, { data: {} });
  expect(del.status()).toBe(403);
  errShape(await del.json(), "forbidden");

  const anon = await pwRequest.newContext({ baseURL: API });
  const p2 = await anon.put(`/api/posts/${id}`, { data: { title: "x", content: "y" } });
  expect(p2.status()).toBe(401);
  errShape(await p2.json(), "unauthenticated");
  expect((await anon.delete(`/api/posts/${id}`, { data: {} })).status()).toBe(401);

  const got = await anon.get(`/api/posts/${id}`);
  expect(got.status()).toBe(200);
  const j = await got.json();
  expect(j.title).toBe("A의 글");
  expect(j.content).toBe("원래 내용");
  expect(j.author.username).toBe(a.name);
});

test("AC-16 AC-22: 삭제 후 GET은 404, 잘못된 ID도 404(500 아님)", async () => {
  const a = await newUser();
  const id = (await (await a.api.post("/api/posts", { data: { title: "삭제될 글", content: "x" } })).json()).id;
  expect((await a.api.delete(`/api/posts/${id}`, { data: {} })).status()).toBe(204);
  const r = await a.api.get(`/api/posts/${id}`);
  expect(r.status()).toBe(404);
  errShape(await r.json(), "post_not_found");
  for (const bad of ["abc", "0", "-1", "99999999999999999999999", "01"]) {
    const x = await a.api.get(`/api/posts/${bad}`);
    expect(x.status(), bad).toBe(404);
  }
  // 이미 삭제된 글 재삭제, 없는 글 수정
  expect((await a.api.delete(`/api/posts/${id}`, { data: {} })).status()).toBe(404);
  expect((await a.api.put(`/api/posts/${id}`, { data: { title: "a", content: "b" } })).status()).toBe(404);
});

test("AC-14: 비정상 page 값은 200으로 보정", async () => {
  const a = await newUser();
  for (const p of ["0", "-1", "abc", "1.5", "", "99999999999999999999", "1e3", "0000000001"]) {
    const r = await a.api.get(`/api/posts?page=${p}`);
    expect(r.status(), p).toBe(200);
    const j = await r.json();
    expect(j.size).toBe(10);
    expect(j.page).toBeGreaterThanOrEqual(1);
    expect(j.items.length).toBeLessThanOrEqual(10);
  }
});

test("AC-19 AC-20: 경계값 (제목 100/101, 내용 5000/5001, 공백뿐)", async () => {
  const a = await newUser();
  const before = await total();
  const ok = await a.api.post("/api/posts", { data: { title: "가".repeat(100), content: "나".repeat(5000) } });
  expect(ok.status()).toBe(201);
  const t101 = await a.api.post("/api/posts", { data: { title: "가".repeat(101), content: "x" } });
  expect(t101.status()).toBe(422);
  const c5001 = await a.api.post("/api/posts", { data: { title: "x", content: "나".repeat(5001) } });
  expect(c5001.status()).toBe(422);
  const blank = await a.api.post("/api/posts", { data: { title: "   ", content: "\n\t" } });
  expect(blank.status()).toBe(422);
  const bj = await blank.json();
  expect(bj.error.code).toBe("validation_error");
  expect(bj.error.details.map((d: any) => d.field)).toEqual(["title", "content"]);
  expect(await total()).toBe(before + 1);
});

test("시나리오11 보안: 본문 65537바이트 이상은 413", async () => {
  const a = await newUser();
  const before = await total();
  const big = JSON.stringify({ title: "x", content: "y".repeat(65537) });
  const r = await a.api.post("/api/posts", { data: big, headers: { "content-type": "application/json" } });
  expect(r.status()).toBe(413);
  errShape(await r.json(), "payload_too_large");
  expect(await total()).toBe(before);
});

test("시나리오11 보안: Content-Length + Transfer-Encoding: chunked 2MB 가입은 411, 사용자 미생성", async () => {
  const name = uid();
  const payload = JSON.stringify({ username: name, password: "a".repeat(2 * 1024 * 1024) });
  const buf = Buffer.from(payload);
  const chunked = Buffer.concat([Buffer.from(buf.length.toString(16) + "\r\n"), buf, Buffer.from("\r\n0\r\n\r\n")]);
  const status = await rawHttp(
    "/api/users",
    ["Content-Type: application/json", "Content-Length: 10", "Transfer-Encoding: chunked"],
    chunked,
  );
  expect(status).toBe(411);
  const api = await pwRequest.newContext({ baseURL: API });
  const l = await api.post("/api/auth/login", { data: { username: name, password: "a".repeat(72) } });
  expect(l.status()).toBe(401);
});

test("시나리오11 보안: 비정상 길이 헤더는 400/411/413, 500·2xx 아님, 사용자 미생성", async () => {
  const cases: [string, string[], string][] = [
    ["TE identity", ["Content-Length: 10", "Transfer-Encoding: identity"], "0123456789"],
    ["CL 숫자 아님", ["Content-Length: abc"], "0123456789"],
    ["CL 거대", [`Content-Length: ${"9".repeat(5000)}`], "0123456789"],
    ["CL 중복(다른 값)", ["Content-Length: 10", "Content-Length: 20"], "0123456789"],
  ];
  for (const [label, hdrs, body] of cases) {
    const st = await rawHttp("/api/users", ["Content-Type: application/json", ...hdrs], body);
    expect([400, 411, 413], label).toContain(st);
  }
});

test("시나리오11 보안: 보안 헤더, /docs·/openapi.json 404, DELETE text/plain 415, CORS 미개방", async () => {
  const a = await newUser();
  const id = (await (await a.api.post("/api/posts", { data: { title: "h", content: "h" } })).json()).id;
  for (const path of ["/api/posts", `/api/posts/${id}`, "/api/posts/abc", "/api/auth/me"]) {
    const r = await a.api.get(path);
    const h = r.headers();
    expect(h["x-content-type-options"], path).toBe("nosniff");
    expect(h["x-frame-options"], path).toBe("DENY");
    expect(h["content-security-policy"], path).toBeTruthy();
    expect(h["access-control-allow-origin"], path).toBeUndefined();
  }
  expect((await a.api.get("/docs")).status()).toBe(404);
  expect((await a.api.get("/openapi.json")).status()).toBe(404);
  const t = await a.api.delete(`/api/posts/${id}`, { data: "x", headers: { "content-type": "text/plain" } });
  expect(t.status()).toBe(415);
  const o = await a.api.fetch("/api/posts", {
    method: "OPTIONS",
    headers: { Origin: "https://evil.example", "Access-Control-Request-Method": "POST" },
  });
  expect(o.headers()["access-control-allow-origin"]).toBeUndefined();
  // 글은 415로 지워지지 않았다
  expect((await a.api.get(`/api/posts/${id}`)).status()).toBe(200);
});

test("AC-25: 서버는 HTML을 그대로 저장·응답한다", async () => {
  const a = await newUser();
  const t = "<script>alert(1)</script>";
  const c = "<img src=x onerror=alert(1)>";
  const r = await a.api.post("/api/posts", { data: { title: t, content: c } });
  expect(r.status()).toBe(201);
  const j = await r.json();
  expect(j.title).toBe(t);
  expect(j.content).toBe(c);
});
