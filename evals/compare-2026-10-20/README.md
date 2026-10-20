# 2026-10-20 VLM 候選比較

ADR 0005 的原始資料。每個模型一個資料夾：`vlm/<image_id>.json` 是標示讀取結果（`VlmReading`），`medpack/<image_id>.json` 是藥包讀取結果（`MedicationPackReading`），`timing.csv` 是每次呼叫的秒數。

重新評分（不花錢）：

    uv run python evals/vlm/run.py --recorded evals/compare-2026-10-20/anthropic_claude-haiku-5.5/vlm
    uv run python evals/medpack/run.py --recorded evals/compare-2026-10-20/anthropic_claude-haiku-5.5/medpack

`vlm_compare.py` 是產生這些檔案的腳本（照片不在 repo，要自備照片資料夾）：同時 4 個請求，費用取 OpenRouter `/key` 用量的前後差。
