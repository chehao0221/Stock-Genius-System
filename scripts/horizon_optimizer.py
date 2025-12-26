import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = {
    "tw": os.path.join(DATA_DIR, "tw_history.csv"),
    "us": os.path.join(DATA_DIR, "us_history.csv"),
}

MIN_SAMPLE = 20
LOOKBACK = 80
OUTPUT = os.path.join(DATA_DIR, "horizon_policy.json")


def find_best_horizon(file):
    if not os.path.exists(file):
        return None

    df = pd.read_csv(file)

    if "real_ret" not in df.columns:
        return None

    df = df.dropna(subset=["pred_ret", "real_ret", "horizon"])
    if df.empty:
        return None

    scores = {}

    for h in sorted(df["horizon"].unique()):
        sub = df[df["horizon"] == h].tail(LOOKBACK)
        if len(sub) < MIN_SAMPLE:
            continue

        hit = ((sub["pred_ret"] > 0) & (sub["real_ret"] > 0)) | \
              ((sub["pred_ret"] < 0) & (sub["real_ret"] < 0))

        hit_rate = hit.mean()
        avg_ret = sub["real_ret"].mean()

        # 🎯 核心：命中率優先，報酬微調
        score = hit_rate * 0.7 + avg_ret * 0.3

        scores[h] = {
            "hit_rate": round(hit_rate * 100, 1),
            "avg_ret": round(avg_ret * 100, 2),
            "score": score,
            "n": len(sub),
        }

    if not scores:
        return None

    best = max(scores, key=lambda x: scores[x]["score"])
    return best, scores[best]


def main():
    policy = {}

    print("🔁 Horizon Optimizer\n")

    for market, file in FILES.items():
        result = find_best_horizon(file)

        if not result:
            print(f"{market.upper()}: 無足夠資料，保留現狀")
            continue

        h, info = result
        policy[market] = h

        print(
            f"{market.upper()} → Horizon {h} 日 "
            f"(命中率 {info['hit_rate']}%, 平均報酬 {info['avg_ret']}%, 樣本 {info['n']})"
        )

    if policy:
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump(policy, f, indent=2, ensure_ascii=False)

        print(f"\n✅ 已更新 {OUTPUT}")
    else:
        print("\n⚠️ 無任何市場更新")


if __name__ == "__main__":
    main()
