import { expect, test, type Page } from "@playwright/test";

// 煙霧測試：註冊 → 搜尋並加入一個藥 → 新增保健食品 → 送出 → 看到上限 %。之後有 UI 的票在這裡延伸。

/** 註冊並走到「用藥」步驟。 */
async function registerAndOpenMedications(page: Page) {
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
}

test("註冊後新增兩項保健食品並看到上限比對", async ({ page }) => {
  await registerAndOpenMedications(page);

  const search = page.getByRole("form", { name: "搜尋藥名" });
  await search.getByLabel("藥名").fill("amlo");
  await search.getByRole("button", { name: "搜尋" }).click();
  await page.getByRole("button", { name: "加入 Amlodipine" }).click();
  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();

  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("家裡的鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("含量").fill("500");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await expect(page.getByRole("button", { name: "刪除 家裡的鈣片" })).toBeVisible();

  // 第二項：每兩天服用的鈣片，檢查跨產品加總與「服用當日」措辭
  await form.getByLabel("產品名稱").fill("隔天吃的鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("含量").fill("500");
  await form.getByLabel("服用頻率").selectOption("every_other_day");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await expect(page.getByRole("button", { name: "刪除 隔天吃的鈣片" })).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();

  await expect(page.getByRole("heading", { name: "上限比對" })).toBeVisible();
  // 兩罐峰值加總 1000 mg → 上限 2500 mg 的 40%
  await expect(page.getByText(/你服用當日來自補充劑的攝取量已達上限的 40%/)).toBeVisible();
  await expect(page.getByText("已超過上限")).toHaveCount(0);
  await expect(page.getByText(/用藥 Amlodipine：在評估範圍內.*氨氯地平/)).toBeVisible();
});

// 後端以錄製的 VLM 回應（evals/vlm/recorded/vlm/p01-img01.json）取代真模型，照片內容不影響結果。
test("用一張照片新增保健食品：辨識 → 逐列確認 → 送出", async ({ page }) => {
  await registerAndOpenMedications(page);
  await page.getByRole("button", { name: "我沒有用藥" }).click(); // 直接進保健食品

  await page.getByLabel("標示照片").setInputFiles({
    name: "label.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0]),
  });
  await page.getByRole("button", { name: "開始辨識" }).click();

  const review = page.getByRole("form", { name: "校對辨識結果" });
  await expect(review.getByLabel("產品名稱")).toHaveValue("挺立 葡萄糖胺強力錠");

  // 沒有逐列確認不能加入
  await review.getByRole("button", { name: "加入這項保健食品（照片）" }).click();
  await expect(page.getByRole("alert")).toContainText("每一列都要按「確認」");

  const confirm = review.getByRole("button", { name: "確認這一列" });
  while ((await confirm.count()) > 0) await confirm.first().click();
  await review.getByRole("button", { name: "加入這項保健食品（照片）" }).click();

  await expect(page.getByRole("button", { name: "刪除 挺立 葡萄糖胺強力錠" })).toBeVisible();
  await expect(page.getByAltText(/挺立 葡萄糖胺強力錠 的標示照片/)).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();

  await expect(page.getByRole("heading", { name: "上限比對" })).toBeVisible();
  await expect(page.getByText(/鈣：.*4.8%/)).toBeVisible(); // 每份（3 錠）含鈣 360 mg，每次 1 錠 = 120 mg
  await expect(page.getByAltText(/挺立 葡萄糖胺強力錠 的標示照片/)).toBeVisible();
});
