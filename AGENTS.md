# AGENTS.md

動手前先讀 `CLAUDE.md`：裡面有專案流程、詞彙表與 ADR 的位置、測試邊界和常用指令，這些規範同樣適用於本檔。

## 語言

回覆、commit message、PR 說明、程式碼註解一律用繁體中文。專有名詞第一次出現時，在中文後面用括號附上英文原文，例如「多階段建置（multi-stage build）」。程式碼識別字、套件名稱、API 名稱維持英文。

## 分支與 commit

- 從 `main` 切功能分支，完成後開 PR 合回 `main`。
- 一個 commit 只做一件事。
- Commit 標題格式：`<類型>: <做了什麼>`，不超過 25 個中文字，不加句號，用現在式。標題描述「做了什麼」，不要寫「改了哪些檔」。
  - 類型限用：`feat`（新功能）、`fix`（修錯）、`docs`（文件、註解）、`refactor`（重構，行為不變）、`chore`（環境、套件、雜項）。拿不準時用 `chore`。
  - 範例：`feat: 新增 API 健康檢查端點`
- 通常只寫標題行就夠了。issue 要求說明理由時，才寫內文。

## 完成前的驗證

- 必跑：`uv run ruff check`、`uv run pytest`。pytest 需要先 `docker compose up -d db`。
- 新行為先寫測試、確認測試失敗，再實作讓它通過。
- 驗收條件只能標兩種狀態：**實際跑過且通過**，或**未驗證**。因為環境限制（例如沒有 Docker daemon）跑不了的項目，要在 PR 的「未驗證」段落逐項列出並附上原因，留給人工驗收。

## Issue

Issue 放在 GitHub Issues，用 `gh` 操作。慣例見 `docs/agents/issue-tracker.md`，標籤見 `docs/agents/triage-labels.md`。PR 說明裡用 `Closes #<n>` 連結 issue。
