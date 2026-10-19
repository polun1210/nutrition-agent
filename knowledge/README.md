# knowledge — RAG 語料

| 目錄 | 進 git | 內容 |
|---|---|---|
| `sources/dris/` | 是 | 《國人膳食營養素參考攝取量》第八版全文、總表、整理筆記 |
| `sources/nih_ods/` | 是 | NIH Office of Dietary Supplements fact sheets（13 種營養素 × Consumer／HealthProfessional） |
| `raw/` | 否 | TFDA 仿單 Markdown（約 3,400 份、1.9 GB，含 base64 圖片） |
| `processed/` | 是 | `scripts/ingest/` 產出：去重、去圖、按仿單章節切好的文字 |
| `manifest.csv` | 是（待建） | 每份文件的來源、許可證字號、有效成分、抓取日期、雜湊值 |

## raw/ 的來源

組員整理於 Google 雲端硬碟 `AIPE04 期末專題/仿單PDF/`：

- `output/<疾病>/<成分>/<許可證字號>_<日期>.md`：仿單 PDF 轉出的 Markdown
- `TFDA/資料集/`：TFDA 開放資料（藥品許可證、處方成分、仿單索引）
- `TFDA_PDF_爬蟲精簡包_20261015/`：下載仿單的爬蟲

把 `output/` 複製或連結到 `knowledge/raw/tfda/` 後再跑 ingest。

## 已知狀況（2026-10-19）

- 同一成分的學名藥重複嚴重（Acetaminophen 1,358 份），ingest 時每個成分只留代表仿單。
- Markdown 約 98% 是 base64 圖片，切塊前要移除。
- 高血壓、第二型糖尿病尚未轉檔；高血脂只轉了 Atorvastatin。

## ingest

```
docker compose up -d db && uv run alembic upgrade head
uv run python -m nutrition_agent.retrieval.ingest [knowledge目錄，預設 knowledge]
```

需要 `.env` 設定 `OPENROUTER_API_KEY`、`EMBEDDING_MODEL`（embedding 走模型閘道）。

- 讀取：`sources/dris/`（DRIs_Full、DRIs_Table）、`sources/nih_ods/`（HealthProfessional 與 Consumer 分開標記來源類型）、`sources/nccih/`（資料夾存在才處理）、`raw/tfda/<疾病>/<有效成分>/<許可證字號>_<日期>.md`（每個有效成分只取日期最新的一份）。
- 處理：移除 base64 圖片（只在行內刪，行號與原檔一致）；依 Markdown 標題或 `【章節】` 切塊，過長的章節再依段落切到 1500 字以內；不收 References／Disclaimer。
- 寫入 pgvector 的 `evidence_chunk` 表：來源類型、文件名稱與相對路徑、成分或有效成分代碼、章節路徑、字元位置與起訖行號、原文。切塊文字與原檔逐字一致，可回溯。
- 冪等：切塊 ID 由「文件路徑＋章節＋內容」雜湊而來；重跑只 embedding 新增的塊，內容改變的文件會換掉舊塊。
- 成分標記：NIH ODS／NCCIH 由檔名對照成分目錄；DRIs 依段落中出現的成分名稱標記；TFDA 以資料夾名稱對照用藥有效成分目錄。
- 檢索：`nutrition_agent.retrieval.search.retrieve_evidence(conn, gateway, 成分代碼, [藥有效成分代碼])`。

## 授權

TFDA 資料適用政府資料開放授權條款；NIH ODS fact sheets 為美國聯邦政府公有領域。
