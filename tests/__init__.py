import os

# 測試用開發環境設定（允許內建的開發用 session 密鑰）。
os.environ.setdefault("APP_ENV", "development")
