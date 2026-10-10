"""Step 2 - train the explainable decision-tree model.

* Train / validation / test split is by student (stratified); the test set is
  never used for tuning or threshold selection.
* Imputation is fitted inside the pipeline, on training data only.
* Only weeks 1-4 behaviour is used - no follow-up or outcome columns.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score, fbeta_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

DATA_DIR, MODEL_DIR = Path("processed_data"), Path("saved_model")
MODEL_DIR.mkdir(exist_ok=True)
SEED = 42

X = pd.read_csv(DATA_DIR / "training_features.csv")
y = pd.read_csv(DATA_DIR / "training_target.csv").iloc[:, 0]
ids = pd.read_csv(DATA_DIR / "student_mapping.csv")["student_id"]
all_feats = pd.read_csv(DATA_DIR / "engineered_features.csv")

X_tr, X_tmp, y_tr, y_tmp = train_test_split(X, y, test_size=0.30, random_state=SEED, stratify=y)
X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=0.50, random_state=SEED, stratify=y_tmp)
print(f"train {len(X_tr)} | validation {len(X_val)} | test {len(X_te)}")

split = pd.Series("train", index=X.index)
split[X_val.index], split[X_te.index] = "validation", "test"
pd.DataFrame({"student_id": ids, "split": split}).to_csv(MODEL_DIR / "split.csv", index=False)


def make_tree(depth, leaf):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("classifier", DecisionTreeClassifier(max_depth=depth, min_samples_leaf=leaf, random_state=SEED)),
    ])


# ---- tune tree size on validation only (leaf probabilities = observed rates)
best = None
for depth in (3, 4, 5, 6):
    for leaf in (30, 60, 100, 200):
        m = make_tree(depth, leaf).fit(X_tr, y_tr)
        ap = average_precision_score(y_val, m.predict_proba(X_val)[:, 1])
        if best is None or ap > best[0] + 1e-9:
            best = (ap, depth, leaf)
_, depth, leaf = best
print(f"selected decision tree: max_depth={depth}, min_samples_leaf={leaf}")
model = make_tree(depth, leaf).fit(X_tr, y_tr)

# ---- thresholds chosen on validation only
#   Medium = F2-optimal (recall-oriented: do not miss likely withdrawals)
#   High   = F1-optimal (balanced: keeps the High list short enough to act on)
val_scores = model.predict_proba(X_val)[:, 1]
grid = np.unique(np.round(np.concatenate([np.linspace(0.01, 0.99, 99), np.unique(val_scores)]), 4))
medium = float(max(grid, key=lambda t: (fbeta_score(y_val, val_scores >= t, beta=2, zero_division=0), t)))
high = float(max(grid, key=lambda t: (f1_score(y_val, val_scores >= t, zero_division=0), t)))
if high <= medium:
    high = float(min(0.99, medium * 1.5))
print(f"thresholds: medium>={medium:.3f}, high>={high:.3f}")


def evaluate(scores, yt, thr):
    pred = (scores >= thr).astype(int)
    return {
        "precision": float(precision_score(yt, pred, zero_division=0)),
        "recall": float(recall_score(yt, pred, zero_division=0)),
        "f1": float(f1_score(yt, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(yt, scores)),
        "average_precision": float(average_precision_score(yt, scores)),
        "confusion_matrix": confusion_matrix(yt, pred).tolist(),
    }


te_scores = model.predict_proba(X_te)[:, 1]
metrics = {"decision_tree": evaluate(te_scores, y_te, high),
           "tree_params": {"max_depth": depth, "min_samples_leaf": leaf},
           "medium_priority_or_above": evaluate(te_scores, y_te, medium),
           "test_size": int(len(X_te)), "test_positive_rate": float(y_te.mean())}

# ---- baseline for context only (not deployed)
lr = Pipeline([("imp", SimpleImputer(strategy="median", keep_empty_features=True)),
               ("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))]).fit(X_tr, y_tr)
lr_val = lr.predict_proba(X_val)[:, 1]
lr_thr = max(np.linspace(0.05, 0.95, 91), key=lambda t: fbeta_score(y_val, lr_val >= t, beta=2, zero_division=0))
metrics["logistic_baseline"] = evaluate(lr.predict_proba(X_te)[:, 1], y_te, float(lr_thr))
print(json.dumps(metrics, indent=2))

insufficient = all_feats.loc[X_te.index, "insufficient_data"].astype(bool).to_numpy()
prio = np.where(insufficient, "Insufficient Data",
                np.where(te_scores >= high, "High", np.where(te_scores >= medium, "Medium", "Low")))
pd.DataFrame({"source_row_index": X_te.index, "actual_withdrawal": y_te.to_numpy(),
              "prediction_score": te_scores, "predicted_withdrawal": (te_scores >= high).astype(int),
              "support_priority": prio}).to_csv(MODEL_DIR / "test_predictions.csv", index=False)

joblib.dump(model, MODEL_DIR / "model_pipeline.joblib")
json.dump({"feature_names": X.columns.tolist()}, open(MODEL_DIR / "feature_schema.json", "w"), indent=4)
json.dump({"low_below": medium, "medium_below": high, "high_from": high},
          open(MODEL_DIR / "risk_thresholds.json", "w"), indent=4)
json.dump(metrics, open(MODEL_DIR / "metrics.json", "w"), indent=2)
print("Saved model to", MODEL_DIR.resolve())
