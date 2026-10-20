# knowledge — RAG 語料

| 目錄 | 進 git | 內容 |
|---|---|---|
| `sources/dris/` | 是 | 《國人膳食營養素參考攝取量》第八版全文、總表、整理筆記 |
| `sources/nih_ods/` | 是 | NIH Office of Dietary Supplements fact sheets（13 種營養素 × Consumer／HealthProfessional） |
| `sources/nccih/` | 是 | NCCIH「What You Need To Know」頁面：紅麴、Omega-3（魚油）、葡萄糖胺與軟骨素 |
| `raw/` | 否 | TFDA 仿單 Markdown（約 3,400 份、1.9 GB，含 base64 圖片），只在維護者本機與 Google 雲端硬碟 |
| `processed/` | 是（目前是空的） | 預留給進 git 的仿單節錄；規則若以 TFDA 仿單為出處，引文檢查只認這裡（`reference/checks.py`），`raw/` 不進 git 無法重現 |
| `manifest.csv` | 尚未建立 | 預計記錄每份文件的來源、許可證字號、有效成分、抓取日期、雜湊值 |

ingest 不經過 `processed/`：直接讀 `sources/` 與 `raw/tfda/`，切塊後寫進資料庫（見下方〈ingest〉）。

## 只有 clone 這個 repo 時

TFDA 仿單（`raw/`）刻意留在維護者本機，不隨 repo 分享，所以：

| 能做 | 做不到 |
|---|---|
| `uv run pytest`、`uv run ruff check`（不打外部 API、不需要語料） | ingest 出含仿單的資料庫：只會有 DRIs／NIH ODS／NCCIH，藥物相關的檢索查不到仿單段落 |
| 有自己的 `OPENROUTER_API_KEY` 時，ingest `sources/` 的語料並試檢索 | `evals/rag/run.py --dry-run` 全數通過：預期證據在 `raw/tfda/` 的題目會報「找不到文件」 |
| 閱讀切塊、檢索、報告的程式與 `docs/adr/` | 重現 `evals/rag/` 的命中率（limit=8 時開發題預期段落 16/16、保留題 6/8，是在完整語料上量的） |

## raw/ 的來源

組員整理於 Google 雲端硬碟 `AIPE04 期末專題/仿單PDF/`：

- `output/<疾病>/<成分>/<許可證字號>_<日期>.md`：仿單 PDF 轉出的 Markdown
- `TFDA/資料集/`：TFDA 開放資料（藥品許可證、處方成分、仿單索引）
- `TFDA_PDF_爬蟲精簡包_20261015/`：下載仿單的爬蟲

把 `output/` 複製或連結到 `knowledge/raw/tfda/` 後再跑 ingest。

## 已知狀況（2026-10-19）

- 同一成分的學名藥重複嚴重（Acetaminophen 1,358 份），ingest 時每個成分只留代表仿單。
- Markdown 約 98% 是 base64 圖片，切塊前要移除。
- 2026-10-19 補齊高血壓（9 種）、第二型糖尿病（4 種）、高血脂其餘 4 種：每個成分只放一份原廠或代表性仿單（ingest 本來就只取一份）。
  高血壓與糖尿病用組員的爬蟲精簡包（`tfda_pdf_downloader.py --license …`）下載，高血脂沿用 Drive 上 `TFDA/PDF/高血脂/` 已有的 PDF；
  都以 MinerU 4.0.12 `mineru-kit parse --tier standard` 轉檔（見 Drive `PDF轉MD指令.md`）。
  檔名帶 `_01`、`_02` 序號的仿單不符合 `<許可證字號>_<日期>.md`，ingest 不會讀到；insulin 只放了蘭德仕（衛署菌疫輸字第000728號）。
- MinerU 會把上下標轉成 LaTeX，例如「vitamin B12」變成 `vitamin $\mathtt { B _ { 1 2 } }$`，直接搜「B12」會找不到；約 90 份有這種殘留。
  規則引文要逐字比對時，要對照轉檔後的原文。
- 少數仿單轉檔時把符號（例如 Lansoprazole 仿單抗藥性門檻的「≧」）弄丟，留下 NUL 字元；ingest 會換成替代字元「�」，引用時看得出此處缺字。
  目前已知 4 份，都在 Lansoprazole（衛部藥輸字第026128號、衛署藥輸字第025972號、衛署藥製字第046246號、第048056號），內容是抗生素抗藥性與臨床試驗註腳，與營養素無關。

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
- 每份文件一個交易，被限速時模型閘道會自動重試；仍然中斷的話直接重跑，從沒寫完的文件接著做。
- 成分標記：NIH ODS／NCCIH 由檔名對照成分目錄；DRIs 依段落中出現的成分名稱標記；TFDA 以資料夾名稱對照用藥有效成分目錄。
- 檢索：`nutrition_agent.retrieval.search.retrieve_evidence(conn, gateway, 成分代碼, [藥有效成分代碼])`。

## sources/nccih/ 的來源

2026-10-19 從 nccih.nih.gov 下載頁面，只取 `<main>` 轉成 Markdown（檔頭註明網址與抓取日期）。
檔名開頭對照成分目錄：`RedYeastRice` → red_yeast_rice、`FishOil` → omega_3、`Glucosamine` → glucosamine。

## 授權

TFDA 資料適用政府資料開放授權條款；NIH ODS fact sheets 與 NCCIH 頁面為美國聯邦政府公有領域。
