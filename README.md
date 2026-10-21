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

## 照片流程

保健食品標示與藥包照片都存在 S3 相容的物件儲存（本機是 SeaweedFS），資料庫只記 object key、歸屬與辨識結果。設計說明見 `docs/adr/0006-object-storage-seaweedfs.md`。

```
上傳 POST .../photos、.../medication-photos
   │  API 驗格式 → put_object（key：product/… 或 medication/…）
   ▼
物件儲存 bucket photos ◄──────────────┐        資料庫 product_photos / medication_photos
   │                                   │          （stored_name = object key、辨識結果、expired_at）
   │                                   │
瀏覽器 <img src="/api/photos/{id}">    │
   │  API 確認是本人的照片              │
   ▼                                   │
302 導向 presigned URL（預設 900 秒）──┘ 瀏覽器直接向物件儲存取圖

過期清理（每天排程一次）
   key 最早一筆建立時間滿 30 天 → delete_object → 共用該 key 的列標記 expired_at
   之後保健食品照片的 GET /api/photos/{id} 回 410，評估與報告照常顯示
```

- SeaweedFS Filer web UI：http://127.0.0.1:8888/buckets/photos/ ，可以看 `product/`、`medication/` 底下的物件（S3 API 在 :8333）。
- 清理指令（保存天數預設取 `PHOTO_RETENTION_DAYS`，30 天）：

  ```
  uv run python -m nutrition_agent.photo_cleanup --dry-run   # 只印出會刪幾個物件、標記幾列
  uv run python -m nutrition_agent.photo_cleanup             # 實際刪除並標記
  uv run python -m nutrition_agent.photo_cleanup --days 7    # 自訂保存天數
  ```

  只刪物件，資料列與辨識結果保留；重複執行不會重複處理，物件已不存在也算成功。

排程範例（每天 03:00）：

```
# cron（crontab -e）
0 3 * * * cd /path/to/nutrition-agent && uv run python -m nutrition_agent.photo_cleanup >> photo_cleanup.log 2>&1
```

```
:: Windows 工作排程器（cmd）
schtasks /Create /TN "nutrition-agent 照片清理" /SC DAILY /ST 03:00 ^
  /TR "cmd /c cd /d C:\path\to\nutrition-agent && uv run python -m nutrition_agent.photo_cleanup >> photo_cleanup.log 2>&1"
```

用 compose 跑 API 時，也可以在容器裡執行：`docker compose exec api python -m nutrition_agent.photo_cleanup`。

## 資料來源與致謝

本 repo 延伸自 AIPE04 期末專題組內專案「補對了嗎？」。VLM 標註資料、TFDA 仿單整理、NIH ODS 資料由組員共同整理。
