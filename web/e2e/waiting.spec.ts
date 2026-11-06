import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const PHOTO = fileURLToPath(new URL("./fixtures/photo.jpg", import.meta.url));
const LABEL = fileURLToPath(new URL("./fixtures/compound-label.jpg", import.meta.url));
const DELAY_MS = 1200;

async function registerAndStart(page: Page, upTo: "medications" | "supplements") {
  await page.goto("/");
  await page.getByRole("button", { name: "還沒有帳號？註冊" }).click();
  await page.getByLabel("Email").fill(`wait-${crypto.randomUUID()}@example.com`);
  await page.getByLabel(/密碼/).fill("correct-horse-battery");
  await page.getByLabel("出生年").fill("1950");
  await page.getByLabel("出生月").selectOption("6");
  await page.getByLabel("女", { exact: true }).check();
  await page.getByLabel("以上皆無").check();
  await page.getByRole("button", { name: "註冊" }).click();
  await page.getByRole("button", { name: "開始評估" }).click();
  await page.getByRole("button", { name: "資料正確，下一步" }).click();
  if (upTo === "supplements") await page.getByRole("button", { name: "我沒有用藥" }).click();
}

// 讓指定 API 慢 DELAY_MS，等待區塊才來得及被觀察；failFirst 時第一次回 500。
async function slowRoute(page: Page, pattern: string, opts: { failFirst?: boolean } = {}) {
  let calls = 0;
  await page.route(pattern, async (route) => {
    calls += 1;
    await new Promise((r) => setTimeout(r, DELAY_MS));
    if (opts.failFirst && calls === 1) {
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "伺服器暫時出錯" }) });
      return;
    }
    await route.continue();
  });
}

test("送出評估：等待區塊出現、按鈕停用，完成後消失並顯示報告", async ({ page }) => {
  await registerAndStart(page, "supplements");
  await page.getByRole("button", { name: "新增一項" }).click();
  await page.getByRole("button", { name: "手動輸入" }).click();
  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("含量").fill("500");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await page.getByRole("button", { name: "下一步" }).click();

  await slowRoute(page, "**/api/assessments/drafts/*/submit");
  await page.getByRole("button", { name: "送出評估" }).click();

  const waiting = page.getByTestId("waiting");
  await expect(waiting).toContainText("正在計算評估報告");
  await expect(waiting).toContainText("通常需要");
  await expect(waiting).not.toContainText("%");
  await expect(page.getByRole("button", { name: "送出評估" })).toBeDisabled();

  await expect(page.getByTestId("waiting")).toHaveCount(0);
  await expect(page.getByRole("table")).toBeVisible();
});

test("送出評估失敗：顯示錯誤與重試，重試後顯示報告", async ({ page }) => {
  await registerAndStart(page, "supplements");
  await page.getByRole("button", { name: "新增一項" }).click();
  await page.getByRole("button", { name: "手動輸入" }).click();
  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("含量").fill("500");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await page.getByRole("button", { name: "下一步" }).click();

  await slowRoute(page, "**/api/assessments/drafts/*/submit", { failFirst: true });
  await page.getByRole("button", { name: "送出評估" }).click();

  await expect(page.getByTestId("waiting-error")).toContainText("伺服器暫時出錯");
  await page.getByRole("button", { name: "重試" }).click();
  await expect(page.getByTestId("waiting")).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
});

test("保健食品照片辨識：等待區塊出現、按鈕停用，完成後進入校對頁", async ({ page }) => {
  await registerAndStart(page, "supplements");
  await page.getByRole("button", { name: "新增一項" }).click();
  await page.getByRole("button", { name: "用照片新增" }).click();
  await page.getByLabel("標示照片").setInputFiles(LABEL);

  await slowRoute(page, "**/api/assessments/drafts/*/photos");
  await page.getByRole("button", { name: "開始辨識" }).click();

  const waiting = page.getByTestId("waiting");
  await expect(waiting).toContainText("正在辨識標示照片");
  await expect(waiting).toContainText("通常需要");
  await expect(page.getByRole("button", { name: "開始辨識" })).toBeDisabled();

  await expect(page.getByRole("form", { name: "校對辨識結果" })).toBeVisible();
  await expect(page.getByTestId("waiting")).toHaveCount(0);
});

test("藥包照片讀取藥名：等待區塊出現、按鈕停用，失敗可重試", async ({ page }) => {
  await registerAndStart(page, "medications");
  await page.getByLabel("藥包照片").setInputFiles(PHOTO);

  await slowRoute(page, "**/api/assessments/drafts/*/medication-photos", { failFirst: true });
  await page.getByRole("button", { name: "讀取藥名" }).click();

  const waiting = page.getByTestId("waiting");
  await expect(waiting).toContainText("正在讀取藥名");
  await expect(page.getByRole("button", { name: "讀取藥名" })).toBeDisabled();

  await expect(page.getByTestId("waiting-error")).toContainText("伺服器暫時出錯");
  await page.getByRole("button", { name: "重試" }).click();
  await expect(page.getByTestId("waiting")).toBeVisible();
  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();
  await expect(page.getByTestId("waiting")).toHaveCount(0);
});
