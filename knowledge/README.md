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

## 授權

TFDA 資料適用政府資料開放授權條款；NIH ODS fact sheets 為美國聯邦政府公有領域。
