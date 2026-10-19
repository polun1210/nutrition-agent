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
  // 4 段固定順序；沒有審定規則時交互作用段落不寫成「沒有交互作用」；完整揭露
  await expect(page.locator("section[data-section] h2")).toHaveText([
    "你的資料",
    "交互作用",
    "上限比對",
    "評估範圍與揭露",
  ]);
  await expect(page.getByText("沒有交互作用")).toHaveCount(0);
  await expect(page.getByText(/未命中已審定的規則/)).toBeVisible();
  await expect(page.getByText(/DPP-4 抑制劑/)).toBeVisible();
  await expect(page.getByText(/同一天服用/)).toBeVisible();
  await expect(page.getByRole("button", { name: "列印報告" })).toBeVisible();
  await expect(page.getByText(/用藥 Amlodipine：在評估範圍內.*氨氯地平/)).toBeVisible();
  await page.getByRole("button", { name: "回首頁" }).click();

  // 從上一次評估複製：用藥與兩項保健食品帶進新草稿，刪掉一項後送出
  await page.getByRole("button", { name: "從上一次評估複製" }).click();
  await page.getByRole("button", { name: "資料正確，下一步" }).click();
  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();
  await page.getByRole("button", { name: "下一步" }).click();
  await expect(page.getByRole("button", { name: "刪除 家裡的鈣片" })).toBeVisible();
  await page.getByRole("button", { name: "刪除 隔天吃的鈣片" }).click();
  await expect(page.getByRole("button", { name: "刪除 隔天吃的鈣片" })).toHaveCount(0);
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();
  await expect(page.getByText(/佔上限 2500 mg 的 20%/)).toBeVisible();
  await page.getByRole("button", { name: "回首頁" }).click();

  // 歷史報告：兩筆，點開舊的那筆仍是 40%，且顯示參考資料版本
  await page.getByRole("button", { name: "歷史報告" }).click();
  await expect(page.getByRole("button", { name: /的評估（/ })).toHaveCount(2);
  await page.getByRole("button", { name: /的評估（2 項保健食品/ }).click();
  await expect(page.getByText(/已達上限的 40%/)).toBeVisible();
  await expect(page.getByTestId("reference-versions")).toContainText("dris");
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

// 後端以假回應：規則用夾具的審定規則（metformin × 維生素 B12），解釋引用一筆種進資料庫的證據段落。
test("交互作用的白話解釋附腳註，點開看到原文與來源", async ({ page }) => {
  await registerAndOpenMedications(page);

  const search = page.getByRole("form", { name: "搜尋藥名" });
  await search.getByLabel("藥名").fill("Metformin");
  await search.getByRole("button", { name: "搜尋" }).click();
  await page.getByRole("button", { name: /^加入 Metformin/ }).first().click();
  await page.getByRole("button", { name: "下一步" }).click();

  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("B12 錠");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "維生素 B12" });
  await form.getByLabel("含量").fill("100");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await expect(page.getByRole("button", { name: "刪除 B12 錠" })).toBeVisible();
  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();

  const explanations = page.getByTestId("explanations");
  await expect(explanations).toContainText("這個藥可能影響維生素 B12 的吸收。");
  await expect(page.getByTestId("footnote-detail")).toHaveCount(0);
  await explanations.getByRole("button", { name: "腳註 1" }).click();
  const detail = page.getByTestId("footnote-detail");
  await expect(detail).toContainText("NIH ODS");
  await expect(detail).toContainText("Metformin might reduce the absorption of vitamin B12");
});

// 後端的假 VLM 對藥包照片固定回 Amlodipine、Zantac。
test("拍一張藥包加入藥：辨識 → 顯示範圍狀態 → 用搜尋修改", async ({ page }) => {
  await registerAndOpenMedications(page);

  await page.getByLabel("藥包照片").setInputFiles({
    name: "pack.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0]),
  });
  await page.getByRole("button", { name: "讀取藥名" }).click();

  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Amlodipine" })).toContainText("在評估範圍內");
  await expect(page.getByRole("listitem").filter({ hasText: "Zantac" })).toContainText("不在本系統評估範圍");

  // 讀錯的藥名用搜尋修改，另一個直接刪除
  await page.getByRole("button", { name: "刪除 Zantac" }).click();
  await page.getByRole("button", { name: "修改 Amlodipine" }).click();
  const search = page.getByRole("form", { name: "搜尋藥名" });
  await search.getByLabel("藥名").fill("atorva");
  await search.getByRole("button", { name: "搜尋" }).click();
  await page.getByRole("button", { name: /^加入 Atorva/ }).first().click();

  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^刪除 Atorva/ })).toBeVisible();
});
