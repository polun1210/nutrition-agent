# evals

打真的模型、會花錢、跑得慢的評估放這裡；`tests/` 只放不打外部 API 的測試。

- `vlm/gold/`：人工標註的正確答案，`sources.csv` 記錄每張圖的拍攝情境與涵蓋的難點。標示照片本身不在 repo。
  - p01–p15（w1／holdout）：舊專案組員標註。p01–p06 是組員自拍，原圖已拿不到，`--live` 時會被略過；p07–p15 可依 `source_url` 重新下載。
  - p16–p28（w2）：2026-10-20 本專案開發者實拍（手機原圖），gold 由 agent 依近拍對照照起草、開發者逐列核對。只標評估照（`<image_id>.jpg`）看得到的內容；品名不在評估照時，品名寫「（品名未入鏡）」。
  - 成分欄沒有含量的列只算讀到與否，不評範圍與代碼（紅麴、葡萄糖胺、魚油除外），見 `extraction/evaluation.py` 的 `_scores_scope`。
- `vlm/recorded/`：舊專案錄下的 Cloud Vision／Gemini 原始回應，可重播比對。
- `vlm/recorded/vlm/`：本專案 VLM 輸出（`extraction.reading.PROMPT` 的 JSON 格式）的錄製回應，`<image_id>.json`；目前只有 p01 一份手工依 gold 整理，其餘待打真模型後用 `--save-recorded` 補。
- `vlm/run.py`：逐欄位比對 harness，重播錄製回應或 `--live` 打真模型，輸出各欄位正確率；用法見檔案開頭。
- `medpack/`：藥包 VLM（只讀藥名原文）的 harness；`gold/<image_id>.json` 格式與用法見 `medpack/run.py` 開頭，gold 與錄製回應（`recorded/`）待開發者標註，沒有 gold 也能跑（結果 n/a）。
- `rag/`：`cases.json`（問題 → 預期證據段落 → 預期解釋重點；每條審定規則至少一題，預期證據用規則的出處引文，題目刻意選引文沒點名的同類藥，測同類推廣與跨語言檢索）與 `run.py`（`--dry-run` 離線檢查資料；`--live` 打真模型檢索與產生解釋，需先 ingest 語料）。

`vlm/` 的資料由舊專案組員標註，來源見 `docs/legacy/README.md`。
