# Embedding 模型用 qwen/qwen3-embedding-8b

2026-10-20 用同一份語料（72 份文件、4,513 塊）分別以三個候選 ingest，再用 `evals/rag/cases.json` 比較。語料中英混雜、提問是中文，關鍵是跨語言檢索：使用者問「氫離子幫浦抑制劑」，證據原文寫 "proton pump inhibitors"。

只看向量相似度（不篩選、不加權）時，預期段落的排名：

| 模型 | 12 題 16 段的 MRR | 前 10 名 | 單價（每百萬 token） | 維度 |
|---|---|---|---|---|
| qwen/qwen3-embedding-8b | 0.31 | 10/16 | $0.01 | 4096 |
| openai/text-embedding-3-large | 0.23 | 7/16 | $0.13 | 3072 |
| baai/bge-m3 | 0.21 | 7/16 | $0.01 | 1024 |

qwen 最準，價格與最便宜的 bge-m3 相同，整份語料 ingest 約 $0.02。

## Consequences

- 4096 維超過 pgvector 近似索引的上限（`vector` 2000 維、`halfvec` 4000 維），所以目前不建 HNSW／IVFFlat 索引；語料小，又是先用成分標籤篩選再算距離，循序掃描就夠快。語料變大時再考慮降維（qwen3-embedding 支援較短的輸出維度）或換模型。
- 換 embedding 模型必須重新 ingest 到空的表：切塊 ID 不含模型名稱，直接重跑會被視為已存在而跳過，查詢和語料就會用不同模型的向量。
- 評估題目只有 12 題，結論是明顯傾向而非定論；補題後應重跑比較。
