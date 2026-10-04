import { test, expect, request as pwRequest, type Page } from "@playwright/test";

const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 1000).toString(36);
const shot = (page: Page, name: string) => page.screenshot({ path: `screenshots/${name}.png` });
const PW = "password8";
const FAIL_MSG = "로그아웃하지 못했습니다. 다시 시도해 주세요.";

async function signupAndLogin(page: Page): Promise<string> {
  const name = uid();
  await page.goto("/signup");
  await page.getByLabel("아이디").fill(name);
  await page.getByLabel("비밀번호").fill(PW);
  await page.getByRole("button", { name: "가입하기" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("아이디").fill(name);
  await page.getByLabel("비밀번호").fill(PW);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("current-username")).toHaveText(name);
  return name;
}

test("시나리오1 AC-6: 비로그인 / 헤더에 로그인·회원가입 링크, 아이디 없음", async ({ page }) => {
  await page.goto("/");
  const header = page.getByRole("banner");
  await expect(header.getByRole("link", { name: "게시판" })).toBeVisible();
  await expect(header.getByRole("link", { name: "로그인" })).toHaveAttribute("href", "/login");
  await expect(header.getByRole("link", { name: "회원가입" })).toHaveAttribute("href", "/signup");
  await expect(page.getByTestId("current-username")).toHaveCount(0);
  await expect(header.getByRole("button", { name: "로그아웃" })).toHaveCount(0);
  await shot(page, "hdr-anon");
});

test("시나리오6 AC-6, AC-8: 로그인 후 헤더에 아이디, 새로고침·재방문 후에도 유지", async ({ page }) => {
  const name = await signupAndLogin(page);
  const header = page.getByRole("banner");
  await expect(header.getByRole("button", { name: "로그아웃" })).toBeVisible();
  await expect(header.getByRole("link", { name: "로그인" })).toHaveCount(0);
  await expect(header.getByRole("link", { name: "회원가입" })).toHaveCount(0);
  await shot(page, "hdr-logged-in");

  await page.reload();
  await expect(page.getByTestId("current-username")).toHaveText(name);
  await expect(header.getByRole("button", { name: "로그아웃" })).toBeVisible();
  await shot(page, "hdr-after-reload");

  // 다른 경로로 직접 진입(전체 로드)해도 유지, 없는 페이지에서도 헤더 유지
  await page.goto("/no-such-page");
  await expect(page.getByRole("heading", { name: "페이지를 찾을 수 없습니다." })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveText(name);

  // 로그인 상태에서 /로 이동해도 유지
  await page.goto("/");
  await expect(page.getByTestId("current-username")).toHaveText(name);
  // 아이디는 localStorage에 저장하지 않는다
  const ls = await page.evaluate(() => JSON.stringify({ ...localStorage }));
  expect(ls).not.toContain(name);
});

test("시나리오8 AC-9: 로그아웃하면 비로그인 헤더, 이전 쿠키로 /me는 401, 새로고침해도 비로그인", async ({
  page,
  baseURL,
}) => {
  const name = await signupAndLogin(page);
  const saved = (await page.context().cookies()).find((c) => c.name === "board_session");
  expect(saved).toBeDefined();

  await page.getByRole("button", { name: "로그아웃" }).click();
  const header = page.getByRole("banner");
  await expect(header.getByRole("link", { name: "로그인" })).toBeVisible();
  await expect(header.getByRole("link", { name: "회원가입" })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await shot(page, "hdr-logged-out");

  await page.reload();
  await expect(header.getByRole("link", { name: "로그인" })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveCount(0);

  const api = await pwRequest.newContext({
    baseURL,
    extraHTTPHeaders: { Cookie: `board_session=${saved!.value}` },
  });
  const res = await api.get("/api/auth/me");
  expect(res.status()).toBe(401);
  const body = await res.json();
  expect(body.error.code).toBe("unauthenticated");
  await api.dispose();

  // 로그아웃 후 다시 로그인 가능(반복 실행)
  await header.getByRole("link", { name: "로그인" }).click();
  await page.getByLabel("아이디").fill(name);
  await page.getByLabel("비밀번호").fill(PW);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page.getByTestId("current-username")).toHaveText(name);
});

test("시나리오8-1 AC-9: 로그아웃 500이면 로그인 유지 + 안내, route 해제 후 재시도하면 비로그인", async ({
  page,
}) => {
  const name = await signupAndLogin(page);
  let calls = 0;
  await page.route("**/api/auth/logout", (r) => {
    calls += 1;
    return r.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "internal_error", message: "서버 내부 오류" } }),
    });
  });

  await page.getByRole("button", { name: "로그아웃" }).click();
  const alert = page.getByRole("alert");
  await expect(alert).toHaveText(FAIL_MSG);
  await expect(page.getByTestId("current-username")).toHaveText(name);
  await expect(page.getByRole("button", { name: "로그아웃" })).toBeVisible();
  await expect(page.getByRole("button", { name: "로그아웃" })).toBeEnabled();
  await expect(page.getByRole("banner").getByRole("link", { name: "로그인" })).toHaveCount(0);
  expect(calls).toBe(1);
  await shot(page, "hdr-logout-failed");

  // 실패해도 서버 세션은 살아 있다: 새로고침하면 여전히 로그인 상태
  await page.reload();
  await expect(page.getByTestId("current-username")).toHaveText(name);

  // 두 번째 실패: 안내는 계속 하나만 보인다
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("alert")).toHaveCount(1);
  await expect(page.getByRole("alert")).toHaveText(FAIL_MSG);

  await page.unroute("**/api/auth/logout");
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: "로그인" })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page).toHaveURL(/\/$/);
  await shot(page, "hdr-logout-retry-ok");
});

test("시나리오8-1 AC-9: 네트워크 오류로 로그아웃이 실패해도 로그인 유지 + 안내", async ({ page }) => {
  const name = await signupAndLogin(page);
  await page.route("**/api/auth/logout", (r) => r.abort("failed"));
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("alert")).toHaveText(FAIL_MSG);
  await expect(page.getByTestId("current-username")).toHaveText(name);
  await page.unroute("**/api/auth/logout");
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
});

test("AC-9: 로그아웃 요청 중 버튼은 비활성화되고 연타해도 요청은 1회", async ({ page }) => {
  await signupAndLogin(page);
  let calls = 0;
  let release: () => void = () => {};
  const gate = new Promise<void>((res) => (release = res));
  await page.route("**/api/auth/logout", async (r) => {
    calls += 1;
    await gate;
    await r.continue();
  });
  const btn = page.getByRole("button", { name: "로그아웃" });
  await btn.click();
  await expect(btn).toBeDisabled();
  await btn.click({ force: true }).catch(() => {});
  release();
  await expect(page.getByRole("banner").getByRole("link", { name: "로그인" })).toBeVisible();
  expect(calls).toBe(1);
});

test("AC-9: 로그아웃 요청이 401로 오면 비로그인 상태가 된다", async ({ page }) => {
  await signupAndLogin(page);
  await page.route("**/api/auth/logout", (r) =>
    r.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "unauthenticated", message: "로그인이 필요합니다." } }),
    }),
  );
  await page.getByRole("button", { name: "로그아웃" }).click();
  await expect(page.getByRole("banner").getByRole("link", { name: "로그인" })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("AC-8: 세션 쿠키를 지우고 새로고침하면 비로그인 헤더", async ({ page }) => {
  await signupAndLogin(page);
  await page.context().clearCookies();
  await page.reload();
  await expect(page.getByRole("banner").getByRole("link", { name: "로그인" })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
});
