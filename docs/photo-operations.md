# 照片維運

保健食品標示與藥包照片都存在 S3 相容的物件儲存（本機是 SeaweedFS），資料庫只記 object key、歸屬與辨識結果。設計理由見 [ADR-0006](adr/0006-object-storage-seaweedfs.md) 與 [ADR-0007](adr/0007-photo-normalization.md)。

## 流程

```
上傳 POST .../photos、.../medication-photos
   │  API 驗格式 → 正規化（轉正、縮圖、去中繼資料）→ put_object（key：product/… 或 medication/…）
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

照片存在 bucket `photos`（API 啟動時自動建立）。SeaweedFS Filer web UI：http://127.0.0.1:8888/buckets/photos/ ，可以看 `product/`、`medication/` 底下的物件（S3 API 在 :8333）。

## 清理指令

保存天數預設取 `PHOTO_RETENTION_DAYS`（30 天）：

```
uv run python -m nutrition_agent.photo_cleanup --dry-run   # 只印出會刪幾個物件、標記幾列
uv run python -m nutrition_agent.photo_cleanup             # 實際刪除並標記
uv run python -m nutrition_agent.photo_cleanup --days 7    # 自訂保存天數
```

只刪物件，資料列與辨識結果保留；重複執行不會重複處理，物件已不存在也算成功。

用 compose 跑 API 時，也可以在容器裡執行：`docker compose exec api python -m nutrition_agent.photo_cleanup`。

## 排程範例（每天 03:00）

```
# cron（crontab -e）
0 3 * * * cd /path/to/nutrition-agent && uv run python -m nutrition_agent.photo_cleanup >> photo_cleanup.log 2>&1
```

```
:: Windows 工作排程器（cmd）
schtasks /Create /TN "nutrition-agent 照片清理" /SC DAILY /ST 03:00 ^
  /TR "cmd /c cd /d C:\path\to\nutrition-agent && uv run python -m nutrition_agent.photo_cleanup >> photo_cleanup.log 2>&1"
```

沒有排程，照片就不會過期。
