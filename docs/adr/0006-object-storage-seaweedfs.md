# 照片物件儲存本機用 SeaweedFS，不用 MinIO

照片從 API 容器的磁碟改存 S3 相容的物件儲存，程式只透過 boto3 走 S3 API 的基本操作（put、get、delete、head、create bucket），換成 AWS S3 或 R2 只改設定。本機開發需要一個能放進 docker compose 的 S3 相容服務。

最常見的選擇是 MinIO，但 MinIO 社群版 2025-10 起不再發佈 Docker 映像與執行檔，repo 在 2026-04 封存，之後不會有安全修補。新專案不該從一個已停止維護的映像開始。

改用 SeaweedFS（Apache-2.0，持續發版）：官方映像 `chrislusf/seaweedfs`，`server -s3` 一個容器就帶起 master、volume、filer 與 S3 gateway。2026-10-21 用 4.48 實測：boto3 的 path-style＋SigV4 put／get／head／delete／create bucket 都可用，設了金鑰後無簽章請求回 403、錯誤金鑰回 SignatureDoesNotMatch，filer 的 web UI 可以瀏覽 `/buckets/photos/` 看物件，展示時好說明 bucket 與 object key 的結構。

## Consequences

- 映像 pin 在 `4.48`，不用 `latest`；升級要重跑上述操作確認。
- SeaweedFS 沒設任何金鑰時 S3 是匿名可讀寫，compose 一定要給 `AWS_ACCESS_KEY_ID`／`AWS_SECRET_ACCESS_KEY`；S3 與 filer 連接埠只綁 127.0.0.1，`mini` 模式附帶的 Admin UI 預設無密碼，所以用 `server -s3` 且不發佈其他連接埠。
- 與 AWS／moto 的行為差異：admin 身分 PUT 到不存在的 bucket 會自動建 bucket、建立已存在的 bucket 回 409 `BucketAlreadyOwnedByYou`、HEAD 不存在的物件或 bucket 只回 `"404"`。程式不依賴這些差異：啟動時先 head 再建、容忍 409；「啟動建 bucket」的測試以 moto 為準。
- `tests/` 用 moto 模擬 S3，不連 SeaweedFS；SeaweedFS 本身只在本機手動驗。
