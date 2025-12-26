## 🔒 Release Status

- Current Stable Version: **v1.0-stable**
- Policy: **Observation-only (no behavior change)**


# 🧠 Stock-Genius-System

> 一套可長期運行、具備自我風控與績效回饋閉環的量化 AI 投資分析系統
> **定位：商業級（Production-Ready）自動化量化研究系統**

---

## 📌 系統核心理念

Stock-Genius-System 並非單純的「預測模型」，而是一個 **會觀察結果、會調整行為、會自我保護的智慧系統**。

核心設計目標：

* 🧠 **AI 預測不是目的，風險存活才是**
* 🔁 **績效 → 行為 → 系統狀態 的閉環設計**
* 🚨 **極端風險（黑天鵝）優先於所有收益**

---

## 🏗️ 目前完整專案結構

```
Stock-Genius-System/
│
├─ .github/
│  └─ workflows/
│     └─ quant_master.yml          # GitHub Actions 主控排程
│
├─ data/
│  ├─ tw_history.csv                # 台股歷史交易紀錄
│  ├─ us_history.csv                # 美股歷史交易紀錄
│  ├─ horizon_policy.json           # 當前預測 Horizon 策略
│  ├─ l3_warning.flag               # L3 風險觀察期旗標
│  ├─ l4_active.flag                # L4 黑天鵝防禦旗標
│  ├─ l4_last_end.flag              # L4 結束時間紀錄
│  ├─ black_swan_history.csv        # 黑天鵝事件紀錄
│  ├─ news_cache.json               # 新聞快取
│  ├─ equity_TW.png                 # 台股 Equity Curve（自動生成）
│  └─ equity_US.png                 # 美股 Equity Curve（自動生成）
│
├─ scripts/
│  ├─ ai_tw_post.py                 # 🇹🇼 台股 AI 分析與推播
│  ├─ ai_us_post.py                 # 🇺🇸 美股 AI 分析與推播
│  ├─ news_radar.py                 # 📰 新聞雷達 / 黑天鵝偵測
│  ├─ performance_dashboard.py      # 📊 績效 Dashboard + Equity Curve
│  ├─ horizon_optimizer.py          # 🔁 Horizon 初始化與策略控制
│  │
│  ├─ l4_defense_mode.py             # L4 黑天鵝防禦模組
│  ├─ l4_dynamic_pause.py            # 動態停機邏輯
│  ├─ l4_market_impact.py            # 市場衝擊分析
│  ├─ l4_ai_performance_compare.py   # AI 前後表現比較
│  ├─ l4_ai_performance_report.py    # L4 事件回顧報告
│  └─ l4_postmortem_report.py        # 黑天鵝事後檢討
│
├─ requirements.txt                 # Python 依賴
├─ README.md                        # 專案說明（本文件）
└─ LICENSE (optional)
```

---

## ⚙️ 系統運作流程（高層概覽）

```
市場資料 / 新聞
        ↓
   AI 預測模型
        ↓
   交易紀錄（data/*.csv）
        ↓
   績效 Dashboard
        ↓
 Horizon 自動調整
        ↓
 L3 / L4 風控決策
        ↓
 Discord 即時視覺化回饋
```

---

## 🧠 AI 預測模組

### 🇹🇼 台股（ai_tw_post.py）

* 固定觀察標的（如：2330.TW、2317.TW 等）
* XGBoost 回歸模型
* 預測 **未來 5 個交易日報酬**（Horizon 可調）
* 自動支援：

  * 🟢 NORMAL
  * 🟡 L3（風險觀察期）
  * 🔴 L4（全面停機）

### 🇺🇸 美股（ai_us_post.py）

* Magnificent 7 為核心
* 同樣的模型與風控邏輯
* 獨立 Discord 頻道輸出

---

## 📊 績效 Dashboard（performance_dashboard.py）

每日自動執行，功能包含：

* 📈 Equity Curve（最近 N 筆交易）
* 🎯 命中率
* 💰 累積報酬
* 🔁 Horizon 自動下修
* 🟡 命中率惡化 → 自動寫入 `l3_warning.flag`
* 📣 Discord Embed + 圖片推播（繁體中文）

> **績效不是用來炫耀，而是用來修正系統行為**

---

## 🚨 風控機制（L3 / L4）

### 🟡 L3：風險觀察期

觸發條件：

* 命中率低於門檻
* 連續多次績效惡化

系統行為：

* 自動降低 Horizon
* Embed 顏色轉為黃色
* 保守化運作

### 🔴 L4：黑天鵝防禦模式

觸發來源：

* 新聞雷達
* 極端市場波動

系統行為：

* **全面停止 AI 預測**
* 僅保留監控與通報
* GitHub Actions 停止 commit

---

## ⏱️ 自動化排程（GitHub Actions）

* 📰 每小時：新聞雷達
* 🇹🇼 台股：交易日固定時間
* 🇺🇸 美股：交易日固定時間
* 📊 Dashboard：每日一次
* 🧠 支援手動觸發（workflow_dispatch）

---

## 📣 Discord 輸出

* 分市場頻道（台股 / 美股）
* 系統狀態 Embed（NORMAL / L3 / L4）
* 績效 Dashboard + Equity Curve 圖
* 全繁體中文

---

## 🧭 系統定位與聲明

* 本系統為 **研究與風險監控用途**
* 所有 AI 結果皆為機率模型輸出
* **非投資建議**

---

## 🏁 結語

這不是一個追求「每天賺多少」的系統，
而是一個追求：

> **在不可預測的市場中，長期活下來的智慧系統。**

---

🧠 Stock-Genius-System
