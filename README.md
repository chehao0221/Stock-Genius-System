# 🚀 Stock-Genius-System (旗艦三合一版)

本系統整合了 **XGBoost 機器學習預測** 與 **Google News 即時情報**，是專為台美股投資者設計的自動化決策系統。

## 📊 核心能力
- **AI 趨勢預估**：每日分析 300 檔標的，預測未來 5 日走勢。
- **即時情報雷達**：自動過濾 12 小時內新鮮新聞，結合盤前漲跌幅警示。
- **自動化對帳**：每日自動比對歷史預測與實際股價，呈現 AI 勝率。

## 📅 執行時程表 (台北時間)
| 時間 | 任務內容 | 腳本路徑 |
| :--- | :--- | :--- |
| **08:30** | 🏹 台股盤前情報 | `scripts/news_radar.py` |
| **14:00** | 🇹🇼 台股 AI 建模 | `scripts/ai_tw_post.py` |
| **21:30** | ⚡ 美股盤前情報 | `scripts/news_radar.py` |
| **06:30** | 🇺🇸 美股 AI 建模 | `scripts/ai_us_post.py` |

## 🛠️ 環境需求
- Python 3.10+
- 必要套件：`yfinance`, `pandas`, `xgboost`, `feedparser` (詳見 requirements.txt)

## 🔑 Secret 設定
請在 GitHub Settings 設定：
- `DISCORD_WEBHOOK_URL`: AI 分析報告發送。
- `NEWS_WEBHOOK_URL`: 即時消息雷達發送。

---
*Disclaimer: 本專案僅供學術研究與個人參考，不構成投資建議。*
