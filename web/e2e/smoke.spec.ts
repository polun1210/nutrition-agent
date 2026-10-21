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

/** 保健食品清單頁 → 新增一項 → 手動輸入。 */
async function addManually(page: Page) {
  await page.getByRole("button", { name: "新增一項" }).click();
  await page.getByRole("button", { name: "手動輸入" }).click();
}

test("註冊後新增兩項保健食品並看到上限比對", async ({ page }) => {
  await registerAndOpenMedications(page);

  const search = page.getByRole("form", { name: "搜尋藥名" });
  await search.getByLabel("藥名").fill("amlo");
  await search.getByRole("button", { name: "搜尋" }).click();
  await page.getByRole("button", { name: "加入 Amlodipine" }).click();
  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();

  await page.getByRole("button", { name: "下一步" }).click();

  // 保健食品清單頁：可回上一步（用藥），新增要按「新增一項」進入單獨一頁
  await page.getByRole("button", { name: "上一步" }).click();
  await expect(page.getByRole("heading", { name: "用藥", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "下一步" }).click();

  await addManually(page);
  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("家裡的鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("含量").fill("500");
  await form.getByRole("button", { name: "加入這項保健食品" }).click();
  await expect(page.getByRole("button", { name: "刪除 家裡的鈣片" })).toBeVisible();

  // 第二項：每兩天服用的鈣片，檢查跨產品加總與「服用當日」措辭
  await addManually(page);
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

  // 沿用上次的藥和保健食品：用藥與兩項保健食品帶進新草稿，刪掉一項後送出
  await page.getByRole("button", { name: "沿用上次的藥和保健食品" }).click();
  await page.getByRole("button", { name: "資料正確，下一步" }).click();
  await expect(page.getByRole("button", { name: "刪除 Amlodipine" })).toBeVisible();
  // 複製來的用藥重新載入後仍顯示範圍狀態（由後端附上，不靠前端暫存）
  await expect(page.getByRole("listitem").filter({ hasText: "Amlodipine" })).toContainText("在評估範圍內");
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

  // 瀏覽器上一頁：報告 → 歷史列表 → 首頁，不會離開 app（#21）
  await page.goBack();
  await expect(page.getByRole("heading", { name: "歷史報告" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "補對了嗎？" })).toBeVisible();
});

test("評估中按瀏覽器上一頁回到前一個步驟，每一步都有返回按鈕", async ({ page }) => {
  await registerAndOpenMedications(page);
  await expect(page.getByRole("heading", { name: "用藥", exact: true })).toBeVisible();

  await page.goBack();
  await expect(page.getByRole("heading", { name: "確認個人資料" })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { name: "用藥", exact: true })).toBeVisible();

  // 用藥步驟有「上一步」，個人資料步驟有「回首頁」
  await page.getByRole("button", { name: "上一步" }).click();
  await expect(page.getByRole("heading", { name: "確認個人資料" })).toBeVisible();
  await page.getByRole("button", { name: "回首頁" }).click();
  await expect(page.getByRole("heading", { name: "補對了嗎？" })).toBeVisible();

  // 首頁再按上一頁仍留在 app 內
  await page.goBack();
  await expect(page.getByRole("heading", { name: "確認個人資料" })).toBeVisible();
});

// 後端以錄製的 VLM 回應（evals/vlm/recorded/vlm/p01-img01.json）取代真模型，照片內容不影響結果。
// 照片取圖改回 410（已超過保存期限）：縮圖換成替代文字，清單與報告照常顯示。
test("用一張照片新增保健食品：辨識 → 整瓶確認一次 → 送出", async ({ page }) => {
  await page.route("**/api/photos/*", (route) => route.fulfill({ status: 410 }));
  await registerAndOpenMedications(page);
  await page.getByRole("button", { name: "我沒有用藥" }).click(); // 直接進保健食品
  await page.getByRole("button", { name: "新增一項" }).click();
  await page.getByRole("button", { name: "用照片新增" }).click();

  await page.getByLabel("標示照片").setInputFiles({
    name: "label.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0]),
  });
  await page.getByRole("button", { name: "開始辨識" }).click();

  const review = page.getByRole("form", { name: "校對辨識結果" });
  await expect(review.getByLabel("產品名稱")).toHaveValue("挺立 葡萄糖胺強力錠");

  // 範圍外成分（維生素B1）不在校對頁出現；無法確定的列保留讓使用者改（#22）
  await expect(review.getByText("包裝上寫：維生素B1", { exact: true })).toHaveCount(0);
  await expect(review.getByText("包裝上寫：豬軟骨素硫酸鈉")).toBeVisible();
  // 不用逐列確認，每一列仍可修改
  await expect(review.getByRole("button", { name: "確認這一列" })).toHaveCount(0);
  await expect(review.getByLabel("含量").first()).toBeEditable();
  // 服用量跟著劑型
  await expect(review.getByLabel("每次幾錠")).toBeVisible();

  await review.getByRole("button", { name: "內容都核對過了，加入這項保健食品" }).click();

  await expect(page.getByRole("button", { name: "刪除 挺立 葡萄糖胺強力錠" })).toBeVisible();
  const thumb = page.getByRole("img", { name: /挺立 葡萄糖胺強力錠 的標示照片/ });
  await expect(thumb).toHaveText("照片已超過保存期限");

  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();

  await expect(page.getByRole("heading", { name: "上限比對" })).toBeVisible();
  await expect(page.getByText(/鈣：.*4.8%/)).toBeVisible(); // 每份（3 錠）含鈣 360 mg，每次 1 錠 = 120 mg
  await expect(thumb).toHaveText("照片已超過保存期限");
  // 校對頁隱藏的範圍外成分仍保存，報告照實揭露
  await expect(page.getByText(/維生素 ?B1」：不在本系統評估範圍/)).toBeVisible();
});

// 後端以假回應：規則用夾具的審定規則（metformin × 維生素 B12），解釋引用一筆種進資料庫的證據段落。
test("交互作用的白話解釋附腳註，點開看到原文與來源", async ({ page }) => {
  await registerAndOpenMedications(page);

  const search = page.getByRole("form", { name: "搜尋藥名" });
  await search.getByLabel("藥名").fill("Metformin");
  await search.getByRole("button", { name: "搜尋" }).click();
  await page.getByRole("button", { name: /^加入 Metformin/ }).first().click();
  await page.getByRole("button", { name: "下一步" }).click();

  await addManually(page);
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
