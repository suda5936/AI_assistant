import { test, expect, type Page } from "@playwright/test";

const uid = () => "u" + Date.now().toString(36) + Math.floor(Math.random() * 100000).toString(36);
const shot = (page: Page, name: string) => page.screenshot({ path: `screenshots/${name}.png` });
const PW = "password8";

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

test("보완 AC-24: 상세를 연 뒤 세션이 B로 바뀐 상태에서 삭제하면 403 안내, 글 유지", async ({ page }) => {
  const aName = await apiUser(page);
  const t = `403삭제-${uid()}`;
  const id = await apiPost(page, t, "원래");
  const bName = uid();
  expect((await page.request.post("/api/users", { data: { username: bName, password: PW } })).status()).toBe(201);
  await apiLogin(page, aName);
  await page.goto(`/posts/${id}`);
  await expect(page.getByRole("button", { name: "삭제", exact: true })).toBeVisible();
  await apiLogin(page, bName);
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("본인이 작성한 글만 수정하거나 삭제할 수 있습니다.");
  await expect(page).toHaveURL(new RegExp(`/posts/${id}$`));
  await expect(page.getByRole("button", { name: "삭제", exact: true })).toBeEnabled();
  expect((await page.request.get(`/api/posts/${id}`)).status()).toBe(200);
  await shot(page, "m2-delete-403");
});

test("시나리오10 AC-22 AC-16: 삭제 확인 창 취소는 유지, 수락은 목록으로 이동·글 사라짐·404 안내", async ({ page }) => {
  await apiUser(page);
  const t = `삭제-${uid()}`;
  const id = await apiPost(page, t, "지울 글");
  await page.goto(`/posts/${id}`);
  page.once("dialog", (d) => d.dismiss());
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/posts/${id}$`));
  await expect(page.getByRole("heading", { name: t })).toBeVisible();
  expect((await page.request.get(`/api/posts/${id}`)).status()).toBe(200);

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "게시판" })).toBeVisible();
  await expect(page.getByRole("link", { name: t })).toHaveCount(0);
  await page.goto(`/posts/${id}`);
  await expect(page.getByRole("heading", { name: "게시글을 찾을 수 없습니다." })).toBeVisible();
  expect((await page.request.get(`/api/posts/${id}`)).status()).toBe(404);
  await shot(page, "m2-deleted-404");
  for (const bad of ["abc", "0", "99999999"]) {
    await page.goto(`/posts/${bad}`);
    await expect(page.getByRole("heading", { name: "게시글을 찾을 수 없습니다." })).toBeVisible();
  }
});
