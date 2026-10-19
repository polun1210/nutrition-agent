import { expect, test } from "@playwright/test";

// 煙霧測試：註冊 → 新增一項保健食品 → 搜尋並加入一個藥 → 送出 → 看到上限 %。之後有 UI 的票在這裡延伸。
test("註冊後新增一項保健食品並看到上限比對", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "還沒有帳號？註冊" }).click();
  await page.getByLabel("Email").fill(`smoke-${Date.now()}@example.com`);
  await page.getByLabel(/密碼/).fill("correct-horse-battery");
  await page.getByLabel("出生年").fill("1950");
  await page.getByLabel("出生月").selectOption("6");
  await page.getByLabel("女", { exact: true }).check();
  await page.getByLabel("以上皆無").check();
  await page.getByRole("button", { name: "註冊" }).click();

  await page.getByRole("button", { name: "開始評估" }).click();
  await page.getByRole("button", { name: "資料正確，下一步" }).click();

  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("家裡的鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("含量").fill("500");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await expect(page.getByRole("button", { name: "刪除 家裡的鈣片" })).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();

  const search = page.getByRole("form", { name: "搜尋藥名" });
  await search.getByLabel("藥名").fill("amlo");
  await search.getByRole("button", { name: "搜尋" }).click();
  await page.getByRole("button", { name: "加入 Amlodipine" }).click();
  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();

  await expect(page.getByRole("heading", { name: "上限比對" })).toBeVisible();
  await expect(page.getByText(/鈣.*20%/)).toBeVisible();
  await expect(page.getByText("已超過上限")).toHaveCount(0);
  await expect(page.getByText(/用藥 Amlodipine：在評估範圍內.*氨氯地平/)).toBeVisible();
});
