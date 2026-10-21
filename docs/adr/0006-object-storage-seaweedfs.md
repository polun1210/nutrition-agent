# 照片物件儲存本機用 SeaweedFS，不用 MinIO

照片從 API 容器的磁碟改存 S3 相容的物件儲存，程式只透過 boto3 走 S3 API 的基本操作（put、get、delete、head、create bucket），換成 AWS S3 或 R2 只改設定。本機開發需要一個能放進 docker compose 的 S3 相容服務。

最常見的選擇是 MinIO，但 MinIO 社群版 2025-10 起不再發佈 Docker 映像與執行檔，repo 在 2026-04 封存，之後不會有安全修補。新專案不該從一個已停止維護的映像開始。

改用 SeaweedFS（Apache-2.0，持續發版）：官方映像 `chrislusf/seaweedfs`，`server -s3` 一個容器就帶起 master、volume、filer 與 S3 gateway。2026-10-21 用 4.48 實測：boto3 的 path-style＋SigV4 put／get／head／delete／create bucket 都可用，設了金鑰後無簽章請求回 403、錯誤金鑰回 SignatureDoesNotMatch，filer 的 web UI 可以瀏覽 `/buckets/photos/` 看物件，展示時好說明 bucket 與 object key 的結構。

## Consequences

- 映像 pin 在 `4.48`，不用 `latest`；升級要重跑上述操作確認。
- SeaweedFS 沒設任何金鑰時 S3 是匿名可讀寫，compose 一定要給 `AWS_ACCESS_KEY_ID`／`AWS_SECRET_ACCESS_KEY`；S3 與 filer 連接埠只綁 127.0.0.1，`mini` 模式附帶的 Admin UI 預設無密碼，所以用 `server -s3` 且不發佈其他連接埠。
- 與 AWS／moto 的行為差異：admin 身分 PUT 到不存在的 bucket 會自動建 bucket、建立已存在的 bucket 回 409 `BucketAlreadyOwnedByYou`、HEAD 不存在的物件或 bucket 只回 `"404"`。程式不依賴這些差異：啟動時先 head 再建、容忍 409；「啟動建 bucket」的測試以 moto 為準。
- `tests/` 用 moto 模擬 S3，不連 SeaweedFS；SeaweedFS 本身只在本機手動驗。

## 取照片用 presigned URL 導向

`GET /api/photos/{id}` 不再由 API 讀出圖檔轉送：API 只確認這張照片是登入者本人的（否則 404，不洩漏是否存在），然後回 302 導向一個短效（預設 900 秒，`PHOTO_URL_TTL_SECONDS`）的 presigned GET URL，瀏覽器直接向物件儲存拿圖。前端 `<img src="/api/photos/{id}">` 不用改；`<img>` 跟隨導向到別的 origin 不需要 CORS。presigned URL 只在本機計算簽章、不連物件儲存，所以這個端點不會因儲存故障而失敗；物件不在 bucket 時是瀏覽器拿到物件儲存的 404。

endpoint 分成兩個設定：

- `S3_INTERNAL_ENDPOINT`：API 讀寫（put、delete、head、create bucket）用，compose 裡是容器網路的 `http://seaweedfs:8333`。
- `S3_PUBLIC_ENDPOINT`：只拿來簽 presigned URL，必須是瀏覽器實際連的網址，本機是 `http://localhost:8333`。

不能用內部 endpoint 簽完再把 host 換掉：SigV4 presigned URL 的 `X-Amz-SignedHeaders=host`，簽章綁定 host:port，2026-10-21 對 SeaweedFS 4.48 實測改 host 後回 403 `SignatureDoesNotMatch`。同理，公開 endpoint 寫 `127.0.0.1` 而使用者用 `localhost` 連也會 403——簽什麼就要打什麼。

- 導向回應帶 `Cache-Control: no-store`：快取時間若比 presigned 有效期長，瀏覽器會在網址過期後沿用舊導向拿到 403；每次都回 API 重新簽最簡單。
- 測試用 moto 只能驗網址結構（host 是公開 endpoint、path-style、帶 SigV4 參數與有效秒數）；簽章真的有效、過期失效只在真 SeaweedFS 手動驗。

## 過期照片用程式清理，不用 bucket lifecycle

照片保存 30 天（`PHOTO_RETENTION_DAYS`），由 `python -m nutrition_agent.photo_cleanup` 每天排程跑一次：刪物件，再把資料庫對應的列標記 `expired_at`（API 據此回 410）。不交給 S3 bucket lifecycle 規則自動到期，原因：

- 到期要以資料庫為準：重新評估會複製照片列，多列共用同一個 object key，過期從該 key 最早一筆的建立時間起算。lifecycle 只看物件自己的建立時間，碰巧結果相同，但刪了之後資料庫不知道，列不會標記，API 只能在使用者打開照片時撞到物件儲存的 404。
- 刪除與標記要成對：程式先刪物件再標記列，刪除失敗就不標記、下次重跑；已標記的列跳過、物件已不存在也算成功，所以可以安全重複執行。lifecycle 刪除是儲存端在背景自己做，程式沒有可靠的時機去標記資料庫。
- 可攜與可測：lifecycle 在 SeaweedFS、AWS S3、R2 之間支援程度不一（SeaweedFS 這部分沒實測過），換儲存就得重設、重驗；程式清理只用基本的 delete_object，在 `tests/` 可以用真的測試 DB＋moto 驗證，並支援 `--dry-run` 先看會刪多少。

代價是要另外排程（README 有 cron 與 Windows 工作排程器範例）；忘了排程，照片就不會過期。
