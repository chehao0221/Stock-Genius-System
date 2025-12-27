# 🧠 Stock-Genius-System  
**Quant Intelligence Market Monitor（v1.0-stable）**

> 一套以「風險優先、行為保守、可長期自動運作」為核心設計的  
> **台股 / 美股 AI 市場觀測與預測系統**。  
>  
> 📌 本系統為 **市場風險與趨勢觀測用途**，  
> 模型為機率推估，僅供研究參考，**非自動交易、非投資建議**。

---

## 🔒 系統狀態（Freeze）

- **版本**：`v1.0-stable`
- **狀態**：🔒 Freeze（僅觀測、不再調整行為）
- **設計原則**：
  - 風險優先（Risk-First）
  - 行為保守（No Auto-Execution）
  - 可長期自動運作（Set-and-Run）

- **允許變更（不影響行為）**：  
  - Discord 顯示樣式（Embed / Emoji / 排版）  
  - 績效視覺化與報告模組（Dashboard / Equity Curve）  
  - 觀測欄位與統計指標（不回饋至決策）

- **禁止變更（已凍結）**：  
  - 預測 Horizon（固定 5 日）  
  - 模型結構與訓練方式  
  - L3 / L4 風險判斷邏輯  
  - 排程時間與觸發條件  

> 自 **v1.0-stable** 起，  
> 所有行為邏輯、風控決策與排程設計皆視為**最終版**，  
> 僅允許新增「觀測與顯示」，不再引入任何自動行為調整。

---

## 🎯 系統設計目標

- 📊 **AI 預測作為風險觀測，而非交易指令**
- 🛡 **L3 / L4 風控優先於任何預測行為**
- 🔁 可在 GitHub Actions 上 **長期自動穩定運作**
- 🧠 所有決策皆可回溯、可審計、可封存

---

## 🧩 核心模組概覽

### 🤖 AI 分析模組
- `ai_tw_post.py`：台股 AI 預測與 Discord 推播
- `ai_us_post.py`：美股 AI 預測與 Discord 推播  
- 預設使用 **5 日 Horizon**（由 `horizon_policy.json` 控制）

### 📰 新聞與黑天鵝
- `news_radar.py`：新聞雷達與風險事件偵測
- `black_swan_history.csv`：黑天鵝事件歷史紀錄

### 📊 績效與觀測
- `performance_dashboard.py`：績效計算與 Equity Curve
- `equity_TW.png / equity_US.png`：自動生成的 Equity Curve 圖
- `performance_discord_report.py`：績效 Discord 推播

### 🔁 Horizon 與風控
- `horizon_policy.json`：目前使用的預測 Horizon
- `horizon_optimizer.py`：Horizon 策略初始化（Freeze）
- `hit_rate_trend_guard.py`：命中率趨勢監控
- `horizon_guardian.py`：Horizon 穩定守門員

### 🚨 L4 黑天鵝防禦
- `l4_defense_mode.py`
- `l4_dynamic_pause.py`
- `l4_market_impact.py`
- `l4_ai_performance_compare.py`
- `l4_ai_performance_report.py`
- `l4_postmortem_report.py`

---

---

## ⏱ GitHub Actions（自動排程）

- **整點**：新聞雷達 / 風險觀測
- **07:30（台股）**：台股 AI 分析
- **22:00（美股）**：美股 AI 分析
- **每日 00:00 UTC**：系統狀態回報

所有排程由：
.github/workflows/quant_master.yml

集中控管。

---

## 📣 Discord 推播設計

- 🇹🇼 台股 / 🇺🇸 美股 **獨立頻道**
- 📈 預估 > 0：綠色 emoji
- 📉 預估 < 0：灰色 emoji
- 🏆 Top 1~3：🥇🥈🥉 自動標示
- 📊 附帶支撐 / 壓力 / Horizon / 命中率

---

## ⚠️ 免責聲明

本系統僅供 **研究、學習與市場風險觀測用途**。  
所有 AI 預測結果不構成任何投資建議，  
使用者需自行承擔任何市場風險。

---

## 🏷 版本標記

- **v1.0-stable**
- 🔒 Freeze（行為封存）
- 📦 可長期自動運行
- 🧠 可審計、可回溯、可歸檔


---

## 📁 Stock-Genius-System 專案目錄結構（v1.0-stable）

```text
Stock-Genius-System/
│
├─ .github/
│  └─ workflows/
│     └─ quant_master.yml
│        # GitHub Actions 主控排程
│        # - 新聞雷達
│        # - 台股 / 美股 AI 預測
│        # - 風險狀態監控（L3 / L4）
│        # - Explorer 股池更新（只讀）
│
├─ data/
│  ├─ tw_history.csv
│  │   # 🇹🇼 台股 AI 預測歷史紀錄（僅觀測，不影響行為）
│  │
│  ├─ us_history.csv
│  │   # 🇺🇸 美股 AI 預測歷史紀錄（僅觀測，不影響行為）
│  │
│  ├─ explorer_pool_tw.json        🆕
│  │   # 🇹🇼 台股 Explorer 股池
│  │   # - 來源：成交量前 500
│  │   # - 定期更新
│  │   # - 僅供 Lv2 探索使用（只讀）
│  │
│  ├─ explorer_pool_us.json        🆕
│  │   # 🇺🇸 美股 Explorer 股池
│  │   # - 來源：成交量前 500
│  │   # - 定期更新
│  │   # - 僅供 Lv2 探索使用（只讀）
│  │
│  ├─ horizon_policy.json
│  │   # 🔁 預測 Horizon 設定（Freeze，固定 5 日）
│  │
│  ├─ l3_warning.flag
│  │   # 🟡 L3 風險觀察期旗標（命中率惡化 / 趨勢警示）
│  │
│  ├─ l4_active.flag
│  │   # 🔴 L4 黑天鵝防禦啟動旗標（全面停用 AI 行為）
│  │
│  ├─ l4_last_end.flag
│  │   # ⏱ 最近一次 L4 結束時間紀錄
│  │
│  ├─ black_swan_history.csv
│  │   # 🚨 黑天鵝事件歷史紀錄（可為空）
│  │
│  ├─ news_cache.json
│  │   # 📰 新聞雷達快取（避免重複抓取）
│  │
│  ├─ equity_TW.png
│  │   # 📈 台股 Equity Curve（由績效模組自動生成）
│  │
│  └─ equity_US.png
│      # 📈 美股 Equity Curve（由績效模組自動生成）
│
├─ scripts/
│  ├─ ai_tw_post.py
│  │   # 🇹🇼 台股 AI 分析與 Discord 推播
│  │   # - Lv1 核心監控股票
│  │   # - 固定 Horizon（5 日）
│  │   # - 只輸出預測，不影響系統行為
│  │
│  ├─ ai_us_post.py
│  │   # 🇺🇸 美股 AI 分析與 Discord 推播
│  │   # - Lv1 Magnificent 7 核心監控
│  │   # - 固定 Horizon（5 日）
│  │   # - 只輸出預測，不影響系統行為
│  │
│  ├─ ai_tw_explorer_post.py       🆕
│  │   # 🇹🇼 台股 Explorer（Lv2）
│  │   # - 使用 explorer_pool_tw.json
│  │   # - 同一模型 / 同一 Horizon
│  │   # - 僅排序，不寫歷史、不影響風控
│  │   # - 只顯示 Top 5
│  │
│  ├─ ai_us_explorer_post.py       🆕
│  │   # 🇺🇸 美股 Explorer（Lv2）
│  │   # - 使用 explorer_pool_us.json
│  │   # - 同一模型 / 同一 Horizon
│  │   # - 僅排序，不寫歷史、不影響風控
│  │   # - 只顯示 Top 5
│  │
│  ├─ update_tw_explorer_pool.py   🆕
│  │   # 🇹🇼 台股 Explorer 股池更新器
│  │   # - 抓取市場成交量
│  │   # - 篩選成交量前 500
│  │   # - 寫入 explorer_pool_tw.json
│  │
│  ├─ update_us_explorer_pool.py   🆕
│  │   # 🇺🇸 美股 Explorer 股池更新器
│  │   # - 抓取市場成交量
│  │   # - 篩選成交量前 500
│  │   # - 寫入 explorer_pool_us.json
│  │
│  ├─ safe_yfinance.py             🆕（本次你已新增）
│  │   # 🛡 Yahoo Finance 安全封裝
│  │   # - 資料源異常時自動降級
│  │   # - 避免 GitHub Actions 因資料源失效而中斷
│  │
│  ├─ news_radar.py
│  │   # 📰 新聞雷達 / 黑天鵝偵測
│  │
│  ├─ performance_dashboard.py
│  │   # 📊 績效統計模組（只觀測）
│  │
│  ├─ performance_discord_report.py
│  │   # 📣 Discord 績效推播（只觀測）
│  │
│  ├─ horizon_optimizer.py
│  │   # 🔁 Horizon 初始化（Freeze）
│  │
│  ├─ hit_rate_trend_guard.py
│  │   # 🎯 命中率趨勢監控（L3）
│  │
│  ├─ horizon_guardian.py
│  │   # 🛡 Horizon 狀態守門
│  │
│  ├─ horizon_change_notifier.py
│  │   # 🔔 Horizon 狀態變更通知
│  │
│  ├─ l4_defense_mode.py
│  │   # 🔴 L4 黑天鵝防禦核心
│  │
│  ├─ l4_dynamic_pause.py
│  │   # ⏸ 動態停機判斷
│  │
│  ├─ l4_market_impact.py
│  │   # 🌊 市場衝擊分析
│  │
│  ├─ l4_ai_performance_compare.py
│  │   # 📉 L4 前後 AI 表現比較
│  │
│  ├─ l4_ai_performance_report.py
│  │   # 📄 L4 分析報告（觀測）
│  │
│  └─ l4_postmortem_report.py
│      # 🧾 黑天鵝事件事後檢討
│
├─ requirements.txt
│  # 🐍 Python 套件依賴清單
│
├─ README.md
│  # 📘 專案說明文件
│  # - 系統定位（研究 / 觀測）
│  # - Horizon Freeze
│  # - Lv1 / Lv2 架構說明
│
└─ LICENSE
   # 📄 授權文件
   # - Research / Educational Use Only
   # - No Investment Advice


```
---

## 📦 Project Status

This project has been **archived after a final stable run**.

- Version: `v1.0-stable`
- Mode: Observation-only (L3)
- Horizon: Frozen
- Last execution: YYYY-MM-DD

This repository is preserved as a long-term reference of a
fully automated, risk-first quantitative monitoring system.
