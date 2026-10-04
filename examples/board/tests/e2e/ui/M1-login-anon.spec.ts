import { test, expect } from "@playwright/test";

const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 1000).toString(36);

test("시나리오5 AC-7: 로그인 실패 후 헤더는 비로그인, 두 경우 같은 메시지", async ({ page }) => {
  const name = uid();
  await page.goto("/signup");
  await page.getByLabel("아이디").fill(name);
  await page.getByLabel("비밀번호").fill("password8");
  await page.getByRole("button", { name: "가입하기" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const msg = "아이디 또는 비밀번호가 올바르지 않습니다.";
  const header = page.getByRole("banner");
  for (const u of [name, "nouser" + uid()]) {
    await page.getByLabel("아이디").fill(u);
    await page.getByLabel("비밀번호").fill("wrongpass1");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page.getByRole("alert")).toHaveText(msg);
    await expect(header.getByRole("link", { name: "회원가입" })).toBeVisible();
    await expect(page.getByTestId("current-username")).toHaveCount(0);
    await page.screenshot({ path: `screenshots/s5-fail-${u === name ? "wrongpw" : "nouser"}.png` });
  }
});

test("시나리오2: 공백만 아이디와 7자 비밀번호 사유가 함께 보이고 비로그인 유지", async ({ page }) => {
  await page.goto("/signup");
  await page.getByLabel("아이디").fill("   ");
  await page.getByLabel("비밀번호").fill("1234567");
  await page.getByRole("button", { name: "가입하기" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "아이디를 입력해 주세요." })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "비밀번호는 8자 이상이어야 합니다." })).toBeVisible();
  await expect(page.getByTestId("current-username")).toHaveCount(0);
});
