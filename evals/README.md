# evals

打真的模型、會花錢、跑得慢的評估放這裡；`tests/` 只放不打外部 API 的測試。

- `vlm/gold/`：人工標註的正確答案，`sources.csv` 記錄每張圖的拍攝情境與涵蓋的難點。標示照片本身不在 repo。
  - p01–p15（w1／holdout）：開發者在舊專案時期標註。repo 只有 w1 的 gold（p01–p03、p05、p07–p12，共 10 份）；holdout（p04、p06、p13–p15）只在 `sources.csv` 留紀錄，沒有 gold。p01–p06 是開發者當時自拍，原圖已拿不到，`--live` 時會被略過；p07–p15 可依 `source_url` 重新下載。
  - p16–p28（w2）：2026-10-20 本專案開發者實拍（手機原圖），gold 由 agent 依近拍對照照起草、開發者逐列核對。只標評估照（`<image_id>.jpg`）看得到的內容；品名不在評估照時，品名寫「（品名未入鏡）」。
  - 成分欄沒有含量的列只算讀到與否，不評範圍與代碼（紅麴、葡萄糖胺、魚油除外），見 `extraction/evaluation.py` 的 `_scores_scope`。
- `vlm/recorded/cloud_vision/`、`vlm/recorded/gemini/`：舊專案時期錄下的 Cloud Vision／Gemini OCR 文字區塊（p01–p03、p05、p07–p12 各 10 份）。格式不是 `VlmReading`，`run.py` 不能重播，目前沒有程式讀取，只供對照。
- `vlm/recorded/vlm/`：`run.py` 預設重播的資料夾（`extraction.reading.PROMPT` 的 JSON 格式，`<image_id>.json`）。只有 p01 一份，是依 gold 手工整理的夾具，`tests/` 與 e2e 的假閘道也讀它；不是真模型的輸出。
  - 真模型的標示讀取結果在 `compare-2026-10-20/anthropic_claude-haiku-5.5/vlm/`（p07–p12、p16–p28，共 19 份，現用的 claude-haiku-5.5），重新評分用 `run.py --recorded` 指到該資料夾。
- `vlm/run.py`：逐欄位比對 harness，重播錄製回應或 `--live` 打真模型，輸出各欄位正確率；用法見檔案開頭。
- `medpack/`：藥包 VLM（只讀藥名原文）的 harness，格式與用法見 `medpack/run.py` 開頭。
  - `gold/`：m01–m32 共 32 份，由開發者標註；m16–m32 是 LINE 傳來的壓縮圖。
  - `recorded/`：32 份錄製回應已補齊，是 #19 修完後重跑 claude-haiku-5.5 的結果（見 ADR 0005），預設重播就能評分，不花錢。
- `compare-2026-10-20/`：ADR 0005 的 VLM 候選比較原始資料（四個模型的讀取結果與秒數），可用 `run.py --recorded` 重新評分，見該資料夾的 README。
- `rag/`：`cases.json`（問題 → 預期證據段落 → 預期解釋重點；每條審定規則至少一題，預期證據用規則的出處引文，題目刻意選引文沒點名的同類藥，測同類推廣與跨語言檢索）與 `run.py`（`--dry-run` 離線檢查資料；`--live` 打真模型檢索與產生解釋，需先 ingest 語料）。
  - `adversarial.json`：換句話說繞過禁用詞黑名單的對抗句（例如「可以放心」「收起來別再吃」），以及應放行的對照句。每句都附上它假裝引用的段落定位，以及預期的評審判定。
  - `--live --judge`：另一個模型（`EVAL_JUDGE_MODEL`，建議和 `LLM_MODEL` 不同）逐句判斷解釋是否被引用的段落支持、有沒有違規說法，彙總出被支持的比例並列出有問題的句子；接著跑對抗句，報告程式的輸出檢查是否放行、評審是否攔下。評審只用在 eval，不放進正式的送出流程；主要評分仍是不依賴 LLM 的檢索命中與重點涵蓋。

`vlm/` 與 `medpack/` 的 gold 都由開發者本人標註或逐列核對（p01–p15 標於舊專案時期），保健食品每張圖的來源見 `vlm/gold/sources.csv`。
