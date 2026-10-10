"""Step 1 - clean the dataset and build features (shared logic lives in
backend/feature_engineering.py so training and serving use identical code)."""
from pathlib import Path

import pandas as pd

from backend.feature_engineering import MODEL_FEATURES, process_wide

INPUT_FILE = "student_support_10000.csv"
OUTPUT_DIR = Path("processed_data")
TARGET = "future_withdrawal_by_week16"


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    df = pd.read_csv(INPUT_FILE)
    print("Original dataset shape:", df.shape)
    df = df.drop_duplicates(subset=["student_id"]).reset_index(drop=True)

    clean, feats, _, quality = process_wide(df)
    # Future-data leakage guard: follow-up / outcome columns are never features.
    X = feats[MODEL_FEATURES]
    y = pd.to_numeric(df[TARGET], errors="coerce")
    ok = y.isin([0, 1])

    clean.to_csv(OUTPUT_DIR / "cleaned_students.csv", index=False)
    feats.to_csv(OUTPUT_DIR / "engineered_features.csv", index=False)
    X[ok].to_csv(OUTPUT_DIR / "training_features.csv", index=False)
    y[ok].astype(int).to_frame(TARGET).to_csv(OUTPUT_DIR / "training_target.csv", index=False)
    df.loc[ok, ["student_id", "student_name"]].to_csv(OUTPUT_DIR / "student_mapping.csv", index=False)

    print("Cleaned:", clean.shape, "| training features:", X[ok].shape)
    print("Target distribution:\n", y[ok].value_counts().to_string())
    print("Insufficient-data cases:", int(feats["insufficient_data"].sum()))
    print("Records with missing/invalid inputs:", sum(q["incomplete"] for q in quality))


if __name__ == "__main__":
    main()
