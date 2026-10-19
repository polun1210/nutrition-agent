import { expect, test } from "@playwright/test";

// 只標化合物重量：校對頁出現「推估」底色欄位，可覆寫；報告註明推估值。
test("化合物重量推估元素量，可覆寫，報告註明系統推估", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "還沒有帳號？註冊" }).click();
  await page.getByLabel("Email").fill(`est-${Date.now()}@example.com`);
  await page.getByLabel(/密碼/).fill("correct-horse-battery");
  await page.getByLabel("出生年").fill("1950");
  await page.getByLabel("出生月").selectOption("6");
  await page.getByLabel("女", { exact: true }).check();
  await page.getByLabel("以上皆無").check();
  await page.getByRole("button", { name: "註冊" }).click();
  await page.getByRole("button", { name: "開始評估" }).click();
  await page.getByRole("button", { name: "資料正確，下一步" }).click();
  await page.getByRole("button", { name: "我沒有用藥" }).click();

  await page.getByRole("button", { name: "新增一項" }).click();
  await page.getByRole("button", { name: "手動輸入" }).click();
  const form = page.getByRole("form", { name: "新增保健食品" });
  await form.getByLabel("產品名稱").fill("檸檬酸鈣片");
  await form.getByLabel("成分", { exact: true }).selectOption({ label: "鈣" });
  await form.getByLabel("標示方式").selectOption("compound");
  await form.getByLabel("化合物", { exact: true }).selectOption({ label: "檸檬酸鈣" });
  await form.getByLabel("化合物重量").fill("1000");

  const estimate = form.getByLabel("元素量");
  await expect(estimate).toHaveValue("210.8");
  await expect(form.getByText("：推估")).toBeVisible();

  await estimate.fill("200");
  await expect(form.getByText("：使用者提供")).toBeVisible();

  await form.getByRole("button", { name: "加入這項保健食品" }).click();

  // 覆寫後重新編輯：覆寫標記、化合物與化合物重量都還在，且仍可還原系統推估
  await page.getByRole("button", { name: "修改 檸檬酸鈣片" }).click();
  const edit = page.getByRole("form", { name: "新增保健食品" });
  await expect(edit.getByLabel("化合物", { exact: true })).toHaveValue("calcium_citrate_tetrahydrate");
  await expect(edit.getByLabel("化合物重量")).toHaveValue("1000");
  await expect(edit.getByLabel("元素量")).toHaveValue("200");
  await expect(edit.getByText("：使用者提供")).toBeVisible();
  await edit.getByRole("button", { name: "還原系統推估" }).click();
  await expect(edit.getByLabel("元素量")).toHaveValue("210.8");
  await edit.getByRole("button", { name: "儲存修改" }).click();

  await page.getByRole("button", { name: "下一步" }).click();
  await page.getByRole("button", { name: "送出評估" }).click();

  await expect(page.getByText(/鈣.*210\.8.*此數值為系統推估，非標示值/)).toBeVisible();
});
