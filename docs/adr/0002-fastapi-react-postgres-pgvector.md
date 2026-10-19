# 技術選型：FastAPI＋React（Vite）＋PostgreSQL／pgvector

後端用 FastAPI，跟既有的 Python＋uv 專案和確定性判定程式放在同一個語言。前端用 React＋Vite＋TypeScript 做手機優先的 SPA，不用 Next.js，因為所有頁面都在登入之後，用不到 SSR。業務資料（帳號、個人資料、評估個案、規則表）和 RAG 向量都放在同一個 PostgreSQL，用 pgvector 做檢索。語料規模小（DRIs、NIH ODS、每個有效成分一份代表仿單），沒必要另外維護一套向量資料庫。

LLM、VLM 和 embedding 都透過 OpenRouter 呼叫，模型寫完整版本號；具體用哪個模型由 `evals/` 的結果決定。登入用 email＋密碼，交給現成套件處理，不自己實作。
