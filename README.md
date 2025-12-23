本專案之 AI 預測結果僅供參考，不構成任何投資建議。投資一定有風險，請謹慎評估。


💎 核心功能模組
📊 AI 趨勢預測 (Machine Learning)
台美股自動海選：每日收盤後自動從 300 檔大市值標的中，篩選出潛力標的。

多因子建模：採用 XGBoost 演算法，整合 RSI、MA20、乖離率 及 成交量比率 進行 5 日後的走勢預測。

透明化對帳：具備自動對帳機制，比對 5 天前預測與今日收盤價，動態呈現 AI 命中率。

⚡ 市場即時情報 (Smart Notification)
雙市場分流：自動判斷執行時間點，精準推送 08:30 台股前瞻 與 21:30 美股戰報。

智慧時效過濾：獨家採用「12 小時時間窗口」邏輯，自動剔除舊聞，確保資訊新鮮度。

視覺化預警：根據盤前漲跌幅強弱（臨界值 1.5%）自動變換訊息顏色（🔥 強勢 / ❄️ 弱勢 / ⚖️ 平穩）。



🛠️ 技術架構

程式語言,Python 3.10+
數據來源,"Yahoo Finance (Price), Google News (RSS)"
核心模型,XGBoost Regressor
自動化排程,GitHub Actions (Serverless Architecture)
通知系統,Discord Webhook (Rich Embeds Layout)

📅 執行時間表 (台北時間 GMT+8)

08:30,🏹 台股盤前情報,掌握台股開盤前最新消息與關鍵權值股現價
14:00,🇹🇼 台股 AI 分析,進行盤後數據建模、歷史對帳與未來 5 日預測
21:30,⚡ 美股盤前情報,監控美股熱門標的（AI 巨頭、半導體）最新動態
06:30,🇺🇸 美股 AI 分析,進行美股盤後預測、歷史對帳與趨勢更新

🔑 環境變數設定 (Secrets)
為確保系統正常運作，請在 GitHub Repository 的 Settings > Secrets and variables > Actions 中配置以下 Secret：

DISCORD_WEBHOOK_URL：AI 預測報告發送通道。

NEWS_WEBHOOK_URL：即時情報（新聞）發送通道。


📁 Quant-Master-Bot
├── 📁 .github/workflows/
│   └── 📄 main_task.yml       # 自動化排程引擎
├── 📁 scripts/
│   ├── 📄 ai_tw_post.py       # 台股預估主程式
│   ├── 📄 ai_us_post.py       # 美股預估主程式
│   └── 📄 news_radar.py       # 情報雷達系統
├── 📁 data/
│   ├── 📄 tw_history.csv      # 台股預測歷史紀錄
│   └── 📄 us_history.csv      # 美股預測歷史紀錄
├── 📄 requirements.txt        # 套件依賴清單
└── 📄 README.md               # 專案說明書


