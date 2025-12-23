🚀 Stock-Genius-System (旗艦級 AI 量化投資系統)這是一個全自動化的金融量化分析系統，專為**台股（TW）與美股（US）**設計。系統結合了 XGBoost 機器學習預測、技術指標工程與 Google News 即時情報雷達，能自動在盤後進行建模分析，並將高潛力標的推播至 Discord。💎 核心價值AI 預測引擎：不只看過去，更預測未來。每日掃描標普 300 與台股核心標的，預測未來 5 日回報率。技術指標深度分析：整合 RSI、Momentum、均線乖離率（Bias）等多維度指標。自動化對帳系統：具備「回頭看」功能，自動驗證 5 天前 AI 預測的準確度，確保模型不失真。情報雷達：自動過濾 12 小時內的重磅財經新聞，結合即時漲跌幅給予投資警示。📂 目錄結構詳解PlaintextStock-Genius-System/
├── .github/workflows/
│   └── quant_master.yml      # 自動化中樞：控制台美股與新聞的觸發時序
├── data/
│   ├── tw_history.csv        # 台股歷史預測紀錄與對帳庫
│   └── us_history.csv        # 美股歷史預測紀錄與對帳庫
├── scripts/
│   ├── ai_tw_post.py         # 台股 AI 建模、分析與 Discord 推播腳本
│   ├── ai_us_post.py         # 美股 AI 建模、分析與 Discord 推播腳本
│   └── news_radar.py         # 全球財經新聞爬蟲與即時狀態監控
├── requirements.txt          # 專案依賴環境
└── README.md                 # 專案說明文件
⚙️ 系統工作流程 (Workflow)1. 數據採集與特徵工程系統使用 yfinance 獲取數據，並計算以下特徵：Momentum (20d)：股價動能趨勢。RSI (14d)：市場超買/超賣狀態。Bias (20d)：與 20 日均線的乖離率。Support/Resistance：基於 60 日高低點計算的技術支撐與壓力位。2. AI 模型訓練使用 XGBoost Regressor 模型：目標：預測未來 5 日的累積回報率。防止過擬合：實作 soft clip 機制將預測限制在合理的 $\pm 15\%$ 區間。3. 自動化排程 (台北時間)時間任務名稱目的08:30🏹 台股盤前情報掃描最新新聞與美股昨夜對台股的影響14:00🇹🇼 台股盤後分析台股收盤後立即進行 AI 預測與模型訓練21:30⚡ 美股盤前情報美股開盤前過濾重要新聞與趨勢06:30🇺🇸 美股盤後分析美股收盤後（隔日清晨）進行 AI 建模與對帳🚀 快速部署手冊第一步：環境準備建議使用 Python 3.10 以上版本：Bashgit clone https://github.com/你的用戶名/Stock-Genius-System.git
cd Stock-Genius-System
pip install -r requirements.txt
第二步：設定 GitHub Secrets請前往你的 GitHub Repository ➡️ Settings ➡️ Secrets and variables ➡️ Actions 新增：DISCORD_WEBHOOK_URL: 接收 AI 分析報告（台美股預測）。NEWS_WEBHOOK_URL: 接收每日新聞雷達。註：兩者可設為同一個網址。第三步：開啟自動化寫入權限為了讓系統能自動更新 data/ 下的 CSV 對帳檔案：前往 Settings ➡️ Actions ➡️ General。將 Workflow permissions 改為 Read and write permissions。📊 報表範例呈現AI 預測報告📊 台股 AI 進階預測報告 (2025-12-23)🏆 AI 推薦 Top 5🥇 2330.TW: 預估 +2.45% (現價: 1045 | 支撐: 1010)🥈 2454.TW: 預估 +1.92% (現價: 1420 | 支撐: 1380)5 日對帳結算🎯 5 日預測結算對帳2317.TW: 預估 +1.50% ➜ 實際 +2.10% ✅NVDA: 預估 +3.00% ➜ 實際 -0.50% ❌🛡️ 免責聲明 (Disclaimer)本專案僅供程式開發與量化研究參考，不構成任何形式的投資建議。金融市場具有高度風險，模型之預測結果基於歷史數據模擬，不代表未來獲利保證。投資前請務必進行獨立思考與風險評估，開發者不對任何投資損失負責。
