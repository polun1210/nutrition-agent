# evals

打真的模型、會花錢、跑得慢的評估放這裡；`tests/` 只放不打外部 API 的測試。

- `vlm/gold/`：人工標註的正確答案，`sources.csv` 記錄每張圖的拍攝情境與涵蓋的難點。標示照片本身不在 repo。
- `vlm/recorded/`：舊專案錄下的 Cloud Vision／Gemini 原始回應，可重播比對。
- `rag/`：待建。問題 → 預期檢索到的段落 → 預期報告重點。

`vlm/` 的資料由舊專案組員標註，來源見 `docs/legacy/README.md`。
