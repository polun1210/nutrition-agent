# nutrition-agent

上傳保健食品標示與用藥，判斷多罐加總是否接近上限、是否與用藥有交互作用，並產出附引用來源的報告。

```
標示照片 ─VLM─► 成分＋劑量 ─┐
                            ├─► assessment（確定性判定）
用藥／個人資料 ─────────────┘          │
                                       ▼
                      retrieval（RAG 檢索仿單、DRIs、NIH ODS）
                                       │
                                       ▼
                      reporting（LLM 只解釋判定，每句附引用）
```

## 目錄

| 目錄 | 用途 |
|---|---|
| `src/nutrition_agent/` | `extraction`（VLM）、`assessment`、`retrieval`、`reporting`、`api` |
| `knowledge/` | RAG 語料，見 `knowledge/README.md` |
| `evals/` | VLM 與 RAG 的評估資料 |
| `web/` | 前端（技術選型待定） |
| `docs/adr/` | 決策紀錄 |
| `docs/research/` | 研究筆記 |
| `docs/legacy/` | 舊組內專案的文件，只供參考 |

## 開發

```
uv sync
uv run pytest
```

## 資料來源與致謝

本 repo 延伸自 AIPE04 期末專題組內專案「補對了嗎？」。VLM 標註資料、TFDA 仿單整理、NIH ODS 資料由組員共同整理。
