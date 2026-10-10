"""Model loading, priority assignment and decision-path explanations."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .feature_engineering import MODEL_FEATURES

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "saved_model"
MODEL_VERSION = "decision-tree-v1"

FEATURE_LABELS = {
    "attendance": "Attendance", "assessment": "Assessment score", "assignment": "Assignment completion",
    "engagement": "Engagement score", "active_days": "Active learning days",
}


def feature_label(name: str) -> tuple[str, str]:
    """Return (readable label, unit)."""
    if name == "weighted_attendance_pct":
        return "Overall attendance (classes attended / conducted)", "%"
    if name == "weighted_assignment_completion":
        return "Overall assignment completion", "%"
    if name == "missing_input_count":
        return "Number of missing weekly inputs", ""
    if name == "observed_input_count":
        return "Number of recorded weekly inputs", ""
    base, _, kind = name.rpartition("_")
    group = FEATURE_LABELS.get(base, base)
    unit = "" if base == "active_days" else "%" if base in ("attendance", "assignment") else " pts"
    if base == "active_days":
        unit = " days"
    text = {"avg": "average", "latest": "latest week", "weeks": "missing weeks", "slope": "weekly change"}.get(kind, kind)
    if name.endswith("missing_weeks"):
        text = "missing weeks"
    return f"{group} - {text}", unit


class ModelService:
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.pipeline = joblib.load(model_dir / "model_pipeline.joblib")
        self.thresholds = json.loads((model_dir / "risk_thresholds.json").read_text())
        self.features = json.loads((model_dir / "feature_schema.json").read_text())["feature_names"]
        assert self.features == MODEL_FEATURES, "feature schema mismatch - retrain the model"
        self.imputer = self.pipeline.named_steps["imputer"]
        self.tree = self.pipeline.named_steps["classifier"]
        split = model_dir / "split.csv"
        self.split = (pd.read_csv(split).set_index("student_id")["split"].to_dict() if split.exists() else {})
        mf = model_dir / "metrics.json"
        self.training_metrics = json.loads(mf.read_text()) if mf.exists() else {}

    # ------------------------------------------------------------ priority
    def priority(self, score: float, insufficient: bool) -> str:
        if insufficient:
            return "Insufficient Data"
        if score >= self.thresholds["high_from"]:
            return "High"
        if score >= self.thresholds["low_below"]:
            return "Medium"
        return "Low"

    # -------------------------------------------------------------- scoring
    def score(self, feats: pd.DataFrame, top_k: int = 5) -> list[dict]:
        X = feats[self.features]
        Xi = self.imputer.transform(X)
        scores = self.tree.predict_proba(Xi)[:, 1]
        paths = self.tree.decision_path(Xi)
        t = self.tree.tree_
        node_p = t.value[:, 0, 1] / t.value[:, 0, :].sum(axis=1)
        raw = X.to_numpy(dtype=float)
        insuff = feats["insufficient_data"].astype(bool).to_numpy()
        out = []
        for i in range(len(X)):
            nodes = paths.indices[paths.indptr[i]:paths.indptr[i + 1]]
            factors = []
            for parent, child in zip(nodes[:-1], nodes[1:]):
                f = int(t.feature[parent])
                name = self.features[f]
                label, unit = feature_label(name)
                went_left = child == t.children_left[parent]
                contrib = float(node_p[child] - node_p[parent])
                imputed = bool(np.isnan(raw[i, f]))
                factors.append({
                    "feature": name, "label": label, "unit": unit,
                    "value": None if imputed else round(float(raw[i, f]), 2),
                    "imputed": imputed,
                    "rule": f"{'<=' if went_left else '>'} {t.threshold[parent]:.1f}{unit}",
                    "contribution": round(contrib, 4),
                    "direction": "raises risk" if contrib > 0 else "lowers risk" if contrib < 0 else "neutral",
                })
            # merge repeated features, keep strongest effects first
            merged: dict[str, dict] = {}
            for fct in factors:
                m = merged.get(fct["feature"])
                if m is None:
                    merged[fct["feature"]] = dict(fct)
                else:
                    m["contribution"] = round(m["contribution"] + fct["contribution"], 4)
                    m["rule"] += f" and {fct['rule']}"
                    m["direction"] = "raises risk" if m["contribution"] > 0 else "lowers risk"
            ranked = sorted(merged.values(), key=lambda d: -abs(d["contribution"]))[:top_k]
            out.append({
                "score": None if insuff[i] else round(float(scores[i]), 4),
                "priority": self.priority(float(scores[i]), bool(insuff[i])),
                "factors": [] if insuff[i] else ranked,
                "base_rate": round(float(node_p[0]), 4),
            })
        return out


_service: ModelService | None = None


def get_model() -> ModelService:
    global _service
    if _service is None:
        _service = ModelService()
    return _service
