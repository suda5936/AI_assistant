import { test, expect, type Page, type Browser, type BrowserContext } from "@playwright/test";

const BASE = "http://127.0.0.1:5174";
const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 100000).toString(36);
const shot = (page: Page, name: string) => page.screenshot({ path: `screenshots/${name}.png` });
const PW = "password8";
const LOGIN_MSG = "글을 쓰려면 로그인해 주세요.";

async function apiLogin(page: Page, name: string) {
  const r = await page.request.post("/api/auth/login", { data: { username: name, password: PW } });
  expect(r.status()).toBe(200);
}
async function apiUser(page: Page): Promise<string> {
  const name = uid();
  const r = await page.request.post("/api/users", { data: { username: name, password: PW } });
  expect(r.status()).toBe(201);
  await apiLogin(page, name);
  return name;
}
async function apiPost(page: Page, title: string, content: string): Promise<number> {
  const r = await page.request.post("/api/posts", { data: { title, content } });
  expect(r.status()).toBe(201);
  return (await r.json()).id;
}
async function ctxUser(browser: Browser): Promise<{ ctx: BrowserContext; page: Page; name: string }> {
  const ctx = await browser.newContext({ baseURL: BASE });
  const page = await ctx.newPage();
  const name = await apiUser(page);
  return { ctx, page, name };
}
const kst = (iso: string) => {
  const d = new Date(new Date(iso).getTime() + 9 * 3600 * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
};
const EMPTY = { items: [], total: 0, page: 1, size: 10 };

test("시나리오1 AC-11: 빈 목록 응답이면 '게시글이 없습니다', 페이지 이동 nav 없음", async ({ page }) => {
  await page.route(/\/api\/posts(\?.*)?$/, (route) => route.fulfill({ json: EMPTY }));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "게시판" })).toBeVisible();
  await expect(page.getByText("게시글이 없습니다")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "페이지 이동" })).toHaveCount(0);
  await shot(page, "m2-empty");
});

test("시나리오5 AC-13: total=10이면 페이지 이동 UI 없음", async ({ page }) => {
  const items = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1,
    title: `가짜${i}`,
    author: { id: 1, username: "fake" },
    created_at: "2026-10-03T01:02:03Z",
  }));
  await page.route(/\/api\/posts(\?.*)?$/, (route) => route.fulfill({ json: { items, total: 10, page: 1, size: 10 } }));
  await page.goto("/");
  await expect(page.getByRole("list", { name: "게시글 목록" }).getByRole("listitem")).toHaveCount(10);
  await expect(page.getByRole("navigation", { name: "페이지 이동" })).toHaveCount(0);
  await expect(page.getByText("2026-10-03 10:02").first()).toBeVisible();
});

test("시나리오2 AC-17: 비로그인 목록·/posts/new에서 로그인 안내", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "글쓰기" })).toHaveCount(0);
  await expect(page.getByText(LOGIN_MSG)).toBeVisible();
  await expect(page.getByRole("link", { name: "로그인하러 가기" })).toBeVisible();
  await page.goto("/posts/new");
  await expect(page.getByText(LOGIN_MSG)).toBeVisible();
  await expect(page.getByRole("link", { name: "로그인하러 가기" })).toBeVisible();
  await expect(page.getByLabel("제목")).toHaveCount(0);
  await expect(page).toHaveURL(/\/posts\/new$/);
  await shot(page, "m2-anon-new");
});

test("시나리오3·4 AC-15 AC-18 AC-19 AC-20: 가입·로그인 후 작성(검증 포함), 상세, 비로그인 상세", async ({ page }) => {
  const name = uid();
  await page.goto("/signup");
  await page.getByLabel("아이디").fill(name);
  await page.getByLabel("비밀번호").fill(PW);
  await page.getByRole("button", { name: "가입하기" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("아이디").fill(name);
  await page.getByLabel("비밀번호").fill(PW);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByTestId("current-username")).toHaveText(name);

  const before = (await (await page.request.get("/api/posts")).json()).total;
  await page.getByRole("link", { name: "글쓰기" }).click();
  await expect(page).toHaveURL(/\/posts\/new$/);

  // 빈 제목
  await page.getByLabel("내용").fill("내용만 있음");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("제목을 입력해 주세요.")).toBeVisible();
  await expect(page).toHaveURL(/\/posts\/new$/);
  // 101자 제목
  await page.getByLabel("제목").fill("가".repeat(101));
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("제목은 100자 이하여야 합니다.")).toBeVisible();
  await shot(page, "m2-new-invalid");
  expect((await (await page.request.get("/api/posts")).json()).total).toBe(before);

  // 100자 제목 + 여러 줄
  const title = "나".repeat(100);
  await page.getByLabel("제목").fill(title);
  await page.getByLabel("내용").fill("첫째 줄\n둘째 줄\n\n넷째 줄");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(/\/posts\/\d+$/);
  const id = Number(page.url().match(/\/posts\/(\d+)$/)![1]);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByTestId("post-author")).toHaveText(name);
  const content = page.getByTestId("post-content");
  await expect(content).toHaveText("첫째 줄\n둘째 줄\n\n넷째 줄");
  await expect(content).toHaveCSS("white-space", "pre-wrap");
  await shot(page, "m2-created");

  // 로그아웃 후 같은 URL
  const created = await (await page.request.get(`/api/posts/${id}`)).json();
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
  await page.goto(`/posts/${id}`);
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByTestId("post-author")).toHaveText(name);
  await expect(page.getByTestId("post-created-at")).toHaveText(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  await expect(page.getByTestId("post-created-at")).toHaveText(kst(created.created_at));
  await expect(page.getByRole("link", { name: "수정", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "삭제", exact: true })).toHaveCount(0);
  await shot(page, "m2-detail-anon");
});

test("시나리오5 AC-12 AC-13 AC-14: 11개 추가 후 최신순 10개, 다음, 비정상 page 보정", async ({ page }) => {
  await apiUser(page);
  const stamp = uid();
  let lastTitle = "";
  for (let i = 0; i < 11; i++) {
    lastTitle = `${stamp}-${i}`;
    await apiPost(page, lastTitle, "본문");
  }
  await page.request.post("/api/auth/logout", { data: {} });
  await page.goto("/");
  const items = page.getByRole("list", { name: "게시글 목록" }).getByRole("listitem");
  await expect(items).toHaveCount(10);
  await expect(items.first()).toContainText(lastTitle);
  const nav = page.getByRole("navigation", { name: "페이지 이동" });
  await expect(nav).toBeVisible();
  await expect(nav.getByRole("link", { name: "이전" })).toHaveCount(0);
  await expect(page.getByTestId("page-indicator")).toHaveText(/^1 \/ \d+$/);
  await shot(page, "m2-list-p1");
  await nav.getByRole("link", { name: "다음" }).click();
  await expect(page.getByTestId("page-indicator")).toHaveText(/^2 \/ \d+$/);
  await expect(nav.getByRole("link", { name: "이전" })).toBeVisible();
  await shot(page, "m2-list-p2");

  const total = (await (await page.request.get("/api/posts")).json()).total as number;
  const last = Math.ceil(total / 10);
  for (const p of ["0", "-1", "abc"]) {
    await page.goto(`/?page=${p}`);
    await expect(page.getByTestId("page-indicator")).toHaveText(`1 / ${last}`);
    await expect(page.getByRole("list", { name: "게시글 목록" }).getByRole("listitem").first()).toContainText(lastTitle);
  }
  await page.goto("/?page=99999");
  await expect(page.getByTestId("page-indicator")).toHaveText(`${last} / ${last}`);
  await expect(nav.getByRole("link", { name: "다음" })).toHaveCount(0);
});

test("시나리오6 AC-25: XSS 문자열은 실행되지 않고 글자 그대로 보인다", async ({ page }) => {
  let dialogs = 0;
  page.on("dialog", async (d) => {
    dialogs++;
    await d.dismiss();
  });
  await apiUser(page);
  const t = "<script>alert(1)</script>";
  const c = "<img src=x onerror=alert(1)>";
  await page.goto("/posts/new");
  await page.getByLabel("제목").fill(t);
  await page.getByLabel("내용").fill(c);
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(/\/posts\/\d+$/);
  await expect(page.getByRole("heading", { name: t })).toBeVisible();
  await expect(page.getByTestId("post-content")).toHaveText(c);
  await expect(page.locator("article img")).toHaveCount(0);
  await page.goto("/");
  await expect(page.getByRole("link", { name: t }).first()).toBeVisible();
  await shot(page, "m2-xss");
  expect(dialogs).toBe(0);
});

test("시나리오7 AC-21: 수정 폼 초기값, 저장 후 상세·목록 반영, 공백 내용 거부", async ({ page }) => {
  await apiUser(page);
  const t0 = `수정전-${uid()}`;
  const id = await apiPost(page, t0, "원래 내용");
  await page.goto(`/posts/${id}`);
  await page.getByRole("link", { name: "수정", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/posts/${id}/edit$`));
  await expect(page.getByLabel("제목")).toHaveValue(t0);
  await expect(page.getByLabel("내용")).toHaveValue("원래 내용");
  // 공백 내용
  await page.getByLabel("내용").fill("   ");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("내용을 입력해 주세요.")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/edit$`));
  // 정상 수정
  const t1 = `수정후-${uid()}`;
  await page.getByLabel("제목").fill(t1);
  await page.getByLabel("내용").fill("바뀐 내용\n두 줄");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(new RegExp(`/posts/${id}$`));
  await expect(page.getByRole("heading", { name: t1 })).toBeVisible();
  await expect(page.getByTestId("post-content")).toHaveText("바뀐 내용\n두 줄");
  await page.goto("/");
  await expect(page.getByRole("link", { name: t1 })).toBeVisible();
  await expect(page.getByRole("link", { name: t0 })).toHaveCount(0);
  await shot(page, "m2-edited");
});

test("보완 AC-21: 아무것도 바꾸지 않고 저장하면 상세로 이동하고 내용·작성 시각 불변", async ({ page }) => {
  await apiUser(page);
  const t = `무변경-${uid()}`;
  const id = await apiPost(page, t, "그대로\n두 줄");
  const before = await (await page.request.get(`/api/posts/${id}`)).json();
  await page.goto(`/posts/${id}/edit`);
  await expect(page.getByLabel("제목")).toHaveValue(t);
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page).toHaveURL(new RegExp(`/posts/${id}$`));
  await expect(page.getByRole("heading", { name: t })).toBeVisible();
  await expect(page.getByTestId("post-content")).toHaveText("그대로\n두 줄");
  const after = await (await page.request.get(`/api/posts/${id}`)).json();
  expect(after).toEqual(before);
  await page.goto("/");
  await expect(page.getByRole("link", { name: t })).toBeVisible();
  await shot(page, "m2-edit-nochange");
});

test("시나리오8 AC-23: B와 비로그인에게 수정·삭제 버튼 없음, B의 edit 직접 진입은 안내만", async ({ browser, page }) => {
  await apiUser(page); // A
  const t = `A글-${uid()}`;
  const id = await apiPost(page, t, "A의 내용");
  // A: 목록에는 수정·삭제 버튼 없음, 상세에는 있음
  await page.goto("/");
  await expect(page.getByRole("link", { name: t })).toBeVisible();
  await expect(page.getByRole("link", { name: "수정", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "삭제", exact: true })).toHaveCount(0);
  await page.goto(`/posts/${id}`);
  await expect(page.getByRole("link", { name: "수정", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "삭제", exact: true })).toBeVisible();

  const b = await ctxUser(browser);
  await b.page.goto(`/posts/${id}`);
  await expect(b.page.getByRole("heading", { name: t })).toBeVisible();
  await expect(b.page.getByRole("link", { name: "수정", exact: true })).toHaveCount(0);
  await expect(b.page.getByRole("button", { name: "삭제", exact: true })).toHaveCount(0);
  await b.page.goto(`/posts/${id}/edit`);
  await expect(b.page.getByText("본인이 작성한 글만 수정할 수 있습니다.")).toBeVisible();
  await expect(b.page.getByLabel("제목")).toHaveCount(0);
  await shot(b.page, "m2-b-edit-blocked");
  await b.ctx.close();

  const anon = await browser.newContext({ baseURL: BASE });
  const ap = await anon.newPage();
  await ap.goto(`/posts/${id}`);
  await expect(ap.getByRole("heading", { name: t })).toBeVisible();
  await expect(ap.getByRole("link", { name: "수정", exact: true })).toHaveCount(0);
  await expect(ap.getByRole("button", { name: "삭제", exact: true })).toHaveCount(0);
  await ap.goto(`/posts/${id}/edit`);
  await expect(ap.getByText("글을 수정하려면 로그인해 주세요.")).toBeVisible();
  await anon.close();
});

test("보완 AC-24: 수정 폼을 연 뒤 세션이 B로 바뀐 상태에서 저장하면 403 안내, 글 불변", async ({ page }) => {
  const aName = await apiUser(page);
  const t = `403글-${uid()}`;
  const id = await apiPost(page, t, "원래");
  // B 계정 준비 (A 쿠키는 유지되도록 별도 컨텍스트로 가입만)
  const bName = uid();
  expect((await page.request.post("/api/users", { data: { username: bName, password: PW } })).status()).toBe(201);
  await apiLogin(page, aName);

  await page.goto(`/posts/${id}/edit`);
  await expect(page.getByLabel("제목")).toHaveValue(t);
  await expect(page.getByTestId("current-username")).toHaveText(aName);
  // 화면은 A 상태 그대로, 쿠키만 B로 바꿈
  await apiLogin(page, bName);
  await page.getByLabel("제목").fill("B가 바꾼 제목");
  await page.getByLabel("내용").fill("B가 바꾼 내용");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "본인이 작성한 글만 수정하거나 삭제할 수 있습니다." })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/edit$`));
  await expect(page.getByRole("button", { name: "저장" })).toBeEnabled();
  await shot(page, "m2-save-403");
  const got = await (await page.request.get(`/api/posts/${id}`)).json();
  expect(got.title).toBe(t);
  expect(got.content).toBe("원래");
});
