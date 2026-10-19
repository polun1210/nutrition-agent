# evals

打真的模型、會花錢、跑得慢的評估放這裡；`tests/` 只放不打外部 API 的測試。

- `vlm/gold/`：人工標註的正確答案，`sources.csv` 記錄每張圖的拍攝情境與涵蓋的難點。標示照片本身不在 repo。
- `vlm/recorded/`：舊專案錄下的 Cloud Vision／Gemini 原始回應，可重播比對。
- `vlm/recorded/vlm/`：本專案 VLM 輸出（`extraction.reading.PROMPT` 的 JSON 格式）的錄製回應，`<image_id>.json`；目前只有 p01 一份手工依 gold 整理，其餘待打真模型後用 `--save-recorded` 補。
- `vlm/run.py`：逐欄位比對 harness，重播錄製回應或 `--live` 打真模型，輸出各欄位正確率；用法見檔案開頭。
- `medpack/`：藥包 VLM（只讀藥名原文）的 harness；`gold/<image_id>.json` 格式與用法見 `medpack/run.py` 開頭，gold 與錄製回應（`recorded/`）待開發者標註，沒有 gold 也能跑（結果 n/a）。
- `rag/`：待建。問題 → 預期檢索到的段落 → 預期報告重點。

`vlm/` 的資料由舊專案組員標註，來源見 `docs/legacy/README.md`。
