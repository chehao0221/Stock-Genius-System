# 🧠 Stock-Genius-System  
**Quant Intelligence Market Monitor（v1.0-stable）**

> 一套以「風險優先、行為保守、可長期自動運作」為核心設計的  
> **台股 / 美股 AI 市場觀測與預測系統**。  
>  
> 📌 本系統為 **市場風險與趨勢觀測用途**，非自動交易、非投資建議。

---

## 🔒 系統狀態（Freeze）

- **版本**：`v1.0-stable`
- **狀態**：🔒 Freeze（僅觀測、不再調整行為）
- **允許變更**：  
  - 顯示樣式（Discord Embed）  
  - 觀測與報告模組（不影響決策）

> 自此版本起，所有交易邏輯、風控行為、排程決策皆視為最終版。

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

## 📁 專案目錄結構（完整）

```text
Stock-Genius-System/
│
├─ .github/
│  └─ workflows/
│     └─ quant_master.yml          # GitHub Actions 主控排程（新聞 / AI / 風控）
│
├─ data/
│  ├─ tw_history.csv               # 🇹🇼 台股 AI 預測歷史紀錄
│  ├─ us_history.csv               # 🇺🇸 美股 AI 預測歷史紀錄
│  ├─ horizon_policy.json          # 🔁 預測 Horizon 設定（Freeze）
│  ├─ l3_warning.flag              # 🟡 L3 風險觀察期旗標
│  ├─ l4_active.flag               # 🔴 L4 黑天鵝防禦啟動旗標
│  ├─ l4_last_end.flag             # ⏱ L4 結束時間紀錄
│  ├─ black_swan_history.csv       # 🚨 黑天鵝事件歷史紀錄
│  ├─ news_cache.json              # 📰 新聞雷達快取
│  ├─ equity_TW.png                # 📈 台股 Equity Curve（自動生成）
│  └─ equity_US.png                # 📈 美股 Equity Curve（自動生成）
│
├─ scripts/
│  ├─ ai_tw_post.py                # 🇹🇼 台股 AI 分析與 Discord 推播
│  ├─ ai_us_post.py                # 🇺🇸 美股 AI 分析與 Discord 推播
│  ├─ news_radar.py                # 📰 新聞雷達 / 黑天鵝偵測
│  │
│  ├─ performance_dashboard.py     # 📊 績效統計 + Equity Curve 產生
│  ├─ performance_discord_report.py# 📣 Discord 績效推播（僅觀測）
│  │
│  ├─ horizon_optimizer.py         # 🔁 Horizon 初始化與策略控制（Freeze）
│  ├─ hit_rate_trend_guard.py      # 🎯 命中率趨勢監控
│  ├─ horizon_guardian.py          # 🛡 Horizon 狀態守門
│  ├─ horizon_change_notifier.py   # 🔔 Horizon 變更通知
│  │
│  ├─ l4_defense_mode.py            # 🔴 L4 黑天鵝防禦核心邏輯
│  ├─ l4_dynamic_pause.py           # ⏸ 動態停機判斷
│  ├─ l4_market_impact.py           # 🌊 市場衝擊分析
│  ├─ l4_ai_performance_compare.py  # 📉 L4 前後 AI 表現比較
│  ├─ l4_ai_performance_report.py   # 📄 L4 分析報告
│  └─ l4_postmortem_report.py       # 🧾 黑天鵝事後檢討
│
├─ requirements.txt                # 🐍 Python 套件依賴
├─ README.md                       # 📘 專案說明文件
└─ LICENSE                         # 📄 授權文件（選用）
```
