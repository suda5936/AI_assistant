import { test, expect, request as pwRequest } from "@playwright/test";

const API = "http://127.0.0.1:8001";
const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 1000).toString(36);
const PW = "password8";

function expectErrorShape(body: any) {
  expect(Object.keys(body)).toEqual(["error"]);
  expect(typeof body.error.code).toBe("string");
  expect(typeof body.error.message).toBe("string");
}
function noSecrets(text: string) {
  expect(text).not.toMatch(/"password"/);
  expect(text).not.toMatch(/password_hash/);
  expect(text).not.toContain("scrypt$");
}

test("시나리오9 AC-1, AC-10: 가입·로그인·me 응답에 비밀번호/해시가 없다", async () => {
  const api = await pwRequest.newContext({ baseURL: API });
  const name = uid();
  const s = await api.post("/api/users", { data: { username: name, password: PW } });
  expect(s.status()).toBe(201);
  noSecrets(await s.text());
  expect((await s.json()).username).toBe(name);

  const l = await api.post("/api/auth/login", { data: { username: name, password: PW } });
  expect(l.status()).toBe(200);
  noSecrets(await l.text());
  const setCookie = l.headers()["set-cookie"] ?? "";
  expect(setCookie).toContain("board_session=");
  expect(setCookie.toLowerCase()).toContain("httponly");
  expect(setCookie.toLowerCase()).toContain("samesite=lax");

  const m = await api.get("/api/auth/me");
  expect(m.status()).toBe(200);
  noSecrets(await m.text());
  expect((await m.json()).username).toBe(name);

  const out = await api.post("/api/auth/logout", { data: {} });
  expect(out.status()).toBe(204);
  expect((await api.get("/api/auth/me")).status()).toBe(401);
  await api.dispose();
});

test("시나리오9: Content-Type text/plain 로그인은 415, 오류 형식 {error:{code,message}}", async () => {
  const api = await pwRequest.newContext({ baseURL: API });
  const r = await api.post("/api/auth/login", {
    headers: { "Content-Type": "text/plain" },
    data: JSON.stringify({ username: "abcd", password: PW }),
  });
  expect(r.status()).toBe(415);
  const b = await r.json();
  expectErrorShape(b);
  expect(b.error.code).toBe("unsupported_media_type");
  await api.dispose();
});

test("시나리오9 AC-2, AC-3, AC-4, AC-7: 오류 응답은 모두 오류 형식을 따른다", async () => {
  const api = await pwRequest.newContext({ baseURL: API });
  const name = uid();
  expect((await api.post("/api/users", { data: { username: name, password: PW } })).status()).toBe(201);

  const dup = await api.post("/api/users", { data: { username: name.toUpperCase(), password: PW } });
  expect(dup.status()).toBe(409);
  const dupBody = await dup.json();
  expectErrorShape(dupBody);
  expect(dupBody.error.code).toBe("username_taken");

  for (const data of [
    { username: "ab", password: PW },
    { username: "   ", password: PW },
    { username: uid(), password: "1234567" },
    { username: uid(), password: "x".repeat(73) },
    { username: uid() },
    { username: 123, password: PW },
  ]) {
    const r = await api.post("/api/users", { data });
    expect(r.status(), JSON.stringify(data)).toBe(422);
    const b = await r.json();
    expectErrorShape(b);
    expect(b.error.code).toBe("validation_error");
    expect(Array.isArray(b.error.details)).toBe(true);
  }
  const pw8 = "1".repeat(8);
  const pw72 = "y".repeat(72);
  const wrong = ["wrong", "pass1"].join("");
  const pw73 = "z".repeat(73);
  expect((await api.post("/api/users", { data: { username: uid(), password: pw8 } })).status()).toBe(201);
  expect((await api.post("/api/users", { data: { username: uid(), password: pw72 } })).status()).toBe(201);

  const bad = await api.post("/api/auth/login", { data: { username: name, password: wrong } });
  const none = await api.post("/api/auth/login", { data: { username: "nouser" + uid(), password: wrong } });
  const long = await api.post("/api/auth/login", { data: { username: name, password: pw73 } });
  for (const r of [bad, none, long]) expect(r.status()).toBe(401);
  const bb = await bad.json();
  expectErrorShape(bb);
  expect(await none.json()).toEqual(bb);
  expect(await long.json()).toEqual(bb);
  expect(bb.error.code).toBe("invalid_credentials");
  for (const r of [bad, none, long]) expect(r.headers()["set-cookie"]).toBeUndefined();

  const me = await api.get("/api/auth/me");
  expect(me.status()).toBe(401);
  const mb = await me.json();
  expectErrorShape(mb);
  expect(mb.error.code).toBe("unauthenticated");

  const nf = await api.get("/api/no-such");
  expect(nf.status()).toBe(404);
  expectErrorShape(await nf.json());
  const bj = await api.post("/api/auth/login", {
    headers: { "Content-Type": "application/json" },
    data: "{not json",
  });
  expect(bj.status()).toBe(422);
  expectErrorShape(await bj.json());
  await api.dispose();
});

test("시나리오9 AC-9: 두 번 로그인한 세션은 독립이고 로그아웃한 쿠키만 무효", async () => {
  const name = uid();
  const a = await pwRequest.newContext({ baseURL: API });
  const b = await pwRequest.newContext({ baseURL: API });
  await a.post("/api/users", { data: { username: name, password: PW } });
  await a.post("/api/auth/login", { data: { username: name, password: PW } });
  await b.post("/api/auth/login", { data: { username: name.toUpperCase(), password: PW } });
  expect((await a.get("/api/auth/me")).status()).toBe(200);
  expect((await b.get("/api/auth/me")).status()).toBe(200);
  await a.post("/api/auth/logout", { data: {} });
  expect((await a.get("/api/auth/me")).status()).toBe(401);
  expect((await b.get("/api/auth/me")).status()).toBe(200);
  expect((await a.post("/api/auth/logout", { data: {} })).status()).toBe(204);
  await a.dispose();
  await b.dispose();
});
