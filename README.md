# nutrition-agent

上傳保健食品標示與用藥，判斷多罐加總是否接近上限、是否與用藥有交互作用，並產出附引用來源的報告。

```
標示照片 ─VLM─► 成分＋劑量 ─┐
                            ├─► assessment（確定性判定）
用藥／個人資料 ─────────────┘          │
                                       ▼
                      retrieval（RAG 檢索仿單、DRIs、NIH ODS）
                                       │
                                       ▼
                      reporting（LLM 只解釋判定，每句附引用）
```

## 目錄

| 目錄 | 用途 |
|---|---|
| `src/nutrition_agent/` | `extraction`（VLM）、`assessment`、`retrieval`、`reporting`、`api` |
| `knowledge/` | RAG 語料，見 `knowledge/README.md` |
| `evals/` | VLM 與 RAG 的評估資料 |
| `web/` | 前端（React＋Vite＋TypeScript，手機優先） |
| `docs/adr/` | 決策紀錄 |
| `docs/research/` | 研究筆記 |
| `docs/legacy/` | 舊組內專案的文件，只供參考 |

## 開發

```
cp .env.example .env        # 填入 OpenRouter 金鑰與模型 ID（不填也能跑骨架）
docker compose up --build   # db（pgvector）+ seaweedfs（S3 :8333）+ api :8000 + web :5173，開 http://127.0.0.1:5173
```

照片存在 SeaweedFS 的 bucket `photos`（API 啟動時自動建立），開 http://127.0.0.1:8888/buckets/photos/ 可以看到物件。

只跑資料庫與物件儲存、其餘在本機：

```
docker compose up -d db seaweedfs
uv sync
uv run alembic upgrade head                      # 套用 migration
uv run uvicorn nutrition_agent.api.app:app --reload
cd web && npm install && npm run dev
```

測試與檢查（測試需要 `docker compose up -d db`，會自動重建 `nutrition_test` 資料庫，不碰開發資料）：

```
uv run pytest
uv run ruff check
cd web && npm run build    # 前端型別檢查＋打包
```

新增 migration：在 `migrations/versions/` 加一個檔案（revision 依序編號）。

## 資料來源與致謝

本 repo 延伸自 AIPE04 期末專題組內專案「補對了嗎？」。VLM 標註資料、TFDA 仿單整理、NIH ODS 資料由組員共同整理。
