import { test, expect, type Page } from "@playwright/test";

const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 1000).toString(36);
const shot = (page: Page, name: string) => page.screenshot({ path: `screenshots/${name}.png` });

async function fillSignup(page: Page, username: string, password: string) {
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill(password);
  await page.getByRole("button", { name: "가입하기" }).click();
}
async function fillLogin(page: Page, username: string, password: string) {
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill(password);
  await page.getByRole("button", { name: "로그인" }).click();
}

test("BOOT: 첫 화면(/, /signup, /login)이 크래시 없이 뜬다", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => {
    // 비로그인 /api/auth/me 의 401은 설계된 정상 응답이므로 브라우저의 리소스 로드 로그는 제외한다.
    if (m.type() === "error" && !/status of 401/.test(m.text())) errors.push(m.text());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "게시판" })).toBeVisible();
  await shot(page, "boot-home");
  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: "회원가입" })).toBeVisible();
  await shot(page, "boot-signup");
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "로그인" })).toBeVisible();
  await shot(page, "boot-login");
  expect(errors).toEqual([]);
});

test("AC-4: 아이디 형식 위반(ab)과 공백뿐인 아이디는 사유가 표시된다", async ({ page }) => {
  await page.goto("/signup");
  await fillSignup(page, "ab", "password1");
  await expect(
    page.getByRole("alert").filter({ hasText: "아이디는 영문 소문자, 숫자, 밑줄(_)로 4~20자여야 합니다." }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/signup$/);
  await shot(page, "ac4-format");

  await page.goto("/signup");
  await fillSignup(page, "     ", "password1");
  await expect(page.getByRole("alert").filter({ hasText: "아이디를 입력해 주세요." })).toBeVisible();

  await page.goto("/signup");
  await fillSignup(page, "", "password1");
  await expect(page.getByRole("alert").filter({ hasText: "아이디를 입력해 주세요." })).toBeVisible();

  await page.goto("/signup");
  await fillSignup(page, "a".repeat(21), "password1");
  await expect(page.getByRole("alert").filter({ hasText: "4~20자여야 합니다" })).toBeVisible();

  await page.goto("/signup");
  await fillSignup(page, "bad-name!", "password1");
  await expect(page.getByRole("alert").filter({ hasText: "4~20자여야 합니다" })).toBeVisible();
});

test("AC-3: 비밀번호 7자는 거부되고 사유가 표시된다, 8자는 허용", async ({ page }) => {
  await page.goto("/signup");
  await fillSignup(page, uid(), "1234567");
  await expect(page.getByRole("alert").filter({ hasText: "비밀번호는 8자 이상이어야 합니다." })).toBeVisible();
  await expect(page).toHaveURL(/\/signup$/);
  await shot(page, "ac3-short");

  await page.goto("/signup");
  await fillSignup(page, uid(), "");
  await expect(page.getByRole("alert").filter({ hasText: "비밀번호는 8자 이상이어야 합니다." })).toBeVisible();

  await page.goto("/signup");
  await fillSignup(page, uid(), "x".repeat(73));
  await expect(page.getByRole("alert").filter({ hasText: "비밀번호는 72자 이하여야 합니다." })).toBeVisible();

  await page.goto("/signup");
  await fillSignup(page, uid(), "12345678");
  await expect(page).toHaveURL(/\/login$/);
});

test("AC-3/AC-4: 아이디·비밀번호 둘 다 틀리면 두 사유가 함께 보인다", async ({ page }) => {
  await page.goto("/signup");
  await fillSignup(page, "ab", "123");
  await expect(page.getByRole("alert").filter({ hasText: "4~20자여야 합니다" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "비밀번호는 8자 이상이어야 합니다." })).toBeVisible();
});

test("AC-1, AC-2, AC-6, AC-7: 가입 → 로그인 화면 → 대문자 중복 → 로그인 실패/성공", async ({ page }) => {
  const name = uid();
  const pw = "password8";
  await page.goto("/signup");
  await fillSignup(page, name, pw);
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("status")).toHaveText("가입이 완료되었습니다. 로그인해 주세요.");
  await shot(page, "ac1-signed-up");

  await page.goto("/signup");
  await fillSignup(page, name.toUpperCase(), pw);
  await expect(page.getByRole("alert").filter({ hasText: "이미 사용 중인 아이디입니다." })).toBeVisible();
  await expect(page).toHaveURL(/\/signup$/);
  await shot(page, "ac2-duplicate");

  await page.goto("/signup");
  await fillSignup(page, name, pw);
  await expect(page.getByRole("alert").filter({ hasText: "이미 사용 중인 아이디입니다." })).toBeVisible();

  const msg = "아이디 또는 비밀번호가 올바르지 않습니다.";
  await page.goto("/login");
  await fillLogin(page, name, "wrongpass1");
  await expect(page.getByRole("alert")).toHaveText(msg);
  await expect(page).toHaveURL(/\/login$/);
  await shot(page, "ac7-wrong-pw");
  expect((await page.context().cookies()).find((c) => c.name === "board_session")).toBeUndefined();

  await page.goto("/login");
  await fillLogin(page, "nouser" + uid(), "wrongpass1");
  await expect(page.getByRole("alert")).toHaveText(msg);
  expect((await page.context().cookies()).find((c) => c.name === "board_session")).toBeUndefined();

  await page.goto("/login");
  await fillLogin(page, "  ", "wrongpass1");
  await expect(page.getByRole("alert")).toHaveText(msg);

  await page.goto("/login");
  await fillLogin(page, name, pw);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "게시판" })).toBeVisible();
  await shot(page, "ac6-logged-in");
  const cookie = (await page.context().cookies()).find((c) => c.name === "board_session");
  expect(cookie?.httpOnly).toBe(true);
  expect(await page.evaluate(() => document.cookie)).not.toContain("board_session");
});

test("AC-1: 가입 중 서버 오류(500)도 화면에 오류가 보인다", async ({ page }) => {
  await page.route("**/api/users", (r) =>
    r.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ error: { code: "internal_error", message: "일시적인 오류가 발생했습니다." } }),
    }),
  );
  await page.goto("/signup");
  await fillSignup(page, uid(), "password8");
  await expect(page.getByRole("alert").filter({ hasText: "일시적인 오류가 발생했습니다." })).toBeVisible();
});
