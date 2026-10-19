# nutrition-agent

保健食品＋慢性病用藥的補充評估。流程：VLM 讀標示 → 確定性規則判定 → RAG 檢索證據 → LLM 組報告。

- 詞彙以 `GLOSSARY.md` 為準；決策紀錄在 `docs/adr/`。
- `docs/legacy/` 是舊組內專案的文件，只當參考：引用前先確認新 repo 有沒有對應的 ADR。
- 判定（超標、命中規則、嚴重度）由 `assessment/` 的確定性程式產生；`reporting/` 的 LLM 只解釋已產生的判定，每句附引用來源。
- `tests/` 不打外部 API；打真模型的評估放 `evals/`。
- 語料處理見 `knowledge/README.md`。

指令：`uv run pytest`、`uv run ruff check`。

## Agent skills

### Issue tracker

Issue 放在 GitHub Issues（polun1210/nutrition-agent），用 `gh` CLI 操作。See `docs/agents/issue-tracker.md`.

### Triage labels

沿用預設五個角色名稱：needs-triage、needs-info、ready-for-agent、ready-for-human、wontfix。See `docs/agents/triage-labels.md`.

### Domain docs

單一脈絡（single-context）：根目錄 `GLOSSARY.md` ＋ `docs/adr/`。See `docs/agents/domain.md`.
