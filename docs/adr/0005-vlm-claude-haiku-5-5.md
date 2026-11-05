# 標示與藥包 VLM 用 anthropic/claude-haiku-5.5

2026-10-20 用實拍照片比較四個候選：保健食品 19 張（`evals/vlm/gold` p07–p12 網路圖、p16–p28 實拍原圖），藥包 32 張（`evals/medpack/gold` m01–m32，m16–m32 是 LINE 傳來的壓縮圖）。每個模型每張只跑一次，同時 4 個請求；讀取結果與秒數在 `evals/compare-2026-10-20/`。

| 模型 | 範圍內含量全對 | 每份量正確 | 產品全對 | 藥包成分 recall／precision（模擬 #19） | 標示單張秒數 中位數／最大 | 51 張費用 |
|---|---|---|---|---|---|---|
| anthropic/claude-haiku-5.5 | 73/75 | 17/19 | 14/19 | 85%／96% | 12.5／20 | $0.03 |
| google/gemini-3.8-flash | 72/75 | 18/19 | 14/19 | 96%／86% | 16／142 | $0.36 |
| anthropic/claude-sonnet-5.5 | 71/75 | 17/19 | 14/19 | 88%／88% | 11／25 | $0.61 |
| openai/gpt-6-luna | 67/75 | 16/19 | 14/19 | 77%／80% | 18／28 | $0.09 |

「範圍內含量全對」只算 gold 有標準代碼且有含量的列：名稱、含量、單位都要對。haiku 與 gemini 的目標營養素全對，沒讀對的都是只判有沒有的允許成分（p26 葡萄糖胺、p27 魚油）。藥包的成分指標用現在的逐字比對時，所有模型都低於 15%（#19），所以改用模擬的部分比對規則（逐字比對不到時，品名包含讀到的字、且所有候選成分相同才帶入）來比較模型。

「每份量正確」與「產品全對」是 2026-10-23 用同一批錄製回應離線補算的（`evals/vlm/run.py --recorded`，欄位 `serving_size` 與 `product_exact`）。「產品全對」以照片為單位：每份幾個劑型單位、劑型單位，以及上述每一列範圍內列的名稱、含量、單位全部正確，才算一張。列層級的含量正確率（haiku 97.9%）每列分開算，但每份量是整瓶所有成分的乘數：讀錯一次，換算成每日攝取量時整瓶每個成分都錯好幾倍，列層級卻一列也不扣。使用者拿到的是一整份辨識結果，任何一處錯都要自己找出來改，所以產品層級才貼近使用者實際得到的結果。

四個模型的產品全對都是 14/19，選型上分不出高下。p23、p26、p27 四個模型都錯：

- p26：每份量都沒讀到或讀錯（gold 每份 2 粒）。
- p27：haiku、sonnet、luna 沒讀到每份量；gemini 每份量對，但 EPA、DHA 讀成「equiv. to …」，名稱與 gold 不同。
- p23：四個模型都把葡萄糖胺鹽酸鹽 200 mg 讀進營養標示表，gold 標在每粒備註。

harness 用正規化後的名稱加標示區塊比對列，名稱多了字或區塊不同都算沒讀到。p23 四個模型讀法一致，要回頭核對 gold 的標法。其餘各錯兩張：haiku 是 p08（只讀出「Monacolin K」，gold 是完整名稱）與 p10（錠讀成粒）；gemini 是 p08、p10 的劑型單位；sonnet 是 p10 的劑型單位與 p25（鎂、鋅沒讀到含量）；luna 是 p08（Monacolin K 沒讀到含量）與 p17（整張讀不到）。

標示的等待時間是硬門檻：gemini 有 5 張超過 30 秒，最慢 142 秒。luna 有一張整張解析失敗（成分名稱回傳 null），藥包會把藥名讀成別的字（「金舒胃得」讀成「金胃錠」、「必胃康」讀成「必胃寧」），事後無法修正，淘汰。sonnet 貴 20 倍，沒有比較準。haiku 標示最準、最快、最便宜，也與 LLM 是同一個模型。

## Consequences

- 藥包 haiku 比 gemini 低約 11 個百分點，主要是兩種可用程式修的錯誤：店內照片把背景貨架的藥也讀進來（各模型都有）、把「金舒胃得 Gisowed」合成一個字串。兩者都併進 #19 處理，修完重跑藥包 eval；若 haiku 仍明顯落後，再考慮藥包另用 gemini。
  - #19 修完後（部分比對、拆開中英文藥名、忽略商標符號、prompt 只讀照片主體）重跑 haiku：成分 recall 92.3%、precision 100%，不另用 gemini。剩下沒對到的 m05、m07 是只印有效成分學名、沒有商品名的盒子背面，模型沒有列出任何藥名。錄製回應在 `evals/medpack/recorded/`。
- 每個模型只跑一次、照片數少，差一兩張就會改變排名，只能看大方向。
- 實拍藥包 m16–m32 是壓縮圖；保健食品 p01–p06 的原圖已拿不到，沒有納入。
- 結構化輸出（structured outputs，#43，2026-11-05）：OpenRouter 上 haiku-5.5 的部分供應商（Anthropic、Google、Azure）支援 `structured_outputs`，Amazon Bedrock 與 Claude Platform on AWS 只列 `response_format`、不保證遵守 schema。所以用 `response_format` 的 `json_schema`（`strict: true`）並加 `provider.require_parameters: true`，只路由到真的支援的供應商。schema 由 pydantic 模型產生（展開 `$ref`、每個物件 `additionalProperties: false`、全部欄位 required）；去掉 code fence、擷取大括號的寬鬆解析保留為後備。
  - **藥包讀取採用**：live 成分 recall 92.3%、precision 96.0%，與上面持平。
  - **標示讀取不採用**：同一天、同一批 19 張各跑兩次 live eval，strict 的 row_recall 62.4%／64.2%，plain 是 65.6%／69.1%，strict 也較常漏讀成分列（p16 曾一次只讀出 0 列）。plain 在這 38 次呼叫中沒有發生過格式解析失敗，所以 strict 在這條路徑上沒有換到好處。閘道的 `schema` 參數仍保留，之後換模型或調 schema 時可以再比較。

