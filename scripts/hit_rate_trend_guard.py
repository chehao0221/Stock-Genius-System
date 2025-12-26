import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

FILES = [
    os.path.join(DATA_DIR, "metrics_tw.csv"),
    os.path.join(DATA_DIR, "metrics_us.csv"),
]

L3_FLAG = os.path.join(DATA_DIR, "l3_warning.flag")

N = 3  # 連續惡化次數門檻


def is_deteriorating(series):
    return all(series[i] < series[i - 1] for i in range(1, len(series)))


def main():
    for file in FILES:
        if not os.path.exists(file):
            continue

        df = pd.read_csv(file)
        if len(df) < N:
            continue

        recent = df["hit_rate"].tail(N).values

        if is_deteriorating(recent):
            if not os.path.exists(L3_FLAG):
                open(L3_FLAG, "w").write("auto\n")
                print("🚨 命中率連續惡化，系統自動進入 L3 風險警示模式")
            return

    print("🟢 命中率趨勢穩定，系統維持正常模式")


if __name__ == "__main__":
    main()
