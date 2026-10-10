"""Cleaning, feature engineering, rule-based alerts, trend warnings and
missing-data checks for EduRadar.

Everything here works on a *wide* frame with the same columns as the
student_support CSV (``classes_attended_week3`` ...).  The same code is used by
preprocess.py (training), the seed script and the upload endpoints, so training
and serving can never drift apart.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEEKS = [1, 2, 3, 4]
COUNT_FIELDS = ["classes_scheduled", "classes_attended", "assignments_due",
                "assignments_submitted", "active_learning_days"]
SCORE_FIELDS = ["assessment_score", "engagement_score"]
WEEKLY_FIELDS = ["classes_scheduled", "classes_attended", "assessment_score",
                 "assignments_due", "assignments_submitted",
                 "engagement_score", "active_learning_days"]
FIELD_LABELS = {
    "classes_scheduled": "classes conducted",
    "classes_attended": "classes attended",
    "assessment_score": "assessment score",
    "assignments_due": "assignments due",
    "assignments_submitted": "assignments submitted",
    "engagement_score": "engagement score",
    "active_learning_days": "active learning days",
}
MODEL_FEATURES = [
    "attendance_avg", "attendance_latest", "attendance_missing_weeks", "attendance_slope",
    "assessment_avg", "assessment_latest", "assessment_missing_weeks", "assessment_slope",
    "assignment_avg", "assignment_latest", "assignment_missing_weeks", "assignment_slope",
    "engagement_avg", "engagement_latest", "engagement_missing_weeks", "engagement_slope",
    "active_days_avg", "active_days_latest", "active_days_missing_weeks", "active_days_slope",
    "weighted_attendance_pct", "weighted_assignment_completion",
    "missing_input_count", "observed_input_count",
]
MAIN_INDICATORS = ["attendance", "assessment", "assignment", "engagement"]

# ---- configurable prototype policies -------------------------------------
LOW_ATTENDANCE_PCT = 75.0          # rule-based alert: below this overall
DECLINING_ATTENDANCE_SLOPE = -5.0  # rule-based alert: percentage points / week
MIN_WEEKS_PER_INDICATOR = 2        # evidence rule
MIN_INDICATORS_WITH_EVIDENCE = 2   # evidence rule
TREND_DROP = {"attendance": 10.0, "assessment": 10.0, "assignment": 25.0, "engagement": 10.0}


def week_cols(prefix: str) -> list[str]:
    return [f"{prefix}_week{w}" for w in WEEKS]


# ---------------------------------------------------------------- cleaning
def clean_wide(df: pd.DataFrame) -> tuple[pd.DataFrame, list[list[str]]]:
    """Validate weekly data.  Invalid values become *missing*, never zero.

    Returns the cleaned frame and, per row, a list of human readable issues
    describing every value that had to be discarded.
    """
    df = df.copy().reset_index(drop=True)
    issues: list[list[str]] = [[] for _ in range(len(df))]

    def flag(mask: pd.Series, text: str) -> None:
        for i in np.flatnonzero(mask.to_numpy()):
            issues[i].append(text)

    for w in WEEKS:
        for f in WEEKLY_FIELDS:
            col = f"{f}_week{w}"
            if col not in df.columns:
                df[col] = np.nan
            raw = df[col]
            num = pd.to_numeric(raw, errors="coerce")
            label = f"Week {w}: {FIELD_LABELS[f]}"
            flag(raw.notna() & num.isna(), f"{label} is not a number - treated as missing")
            df[col] = num
            if f in COUNT_FIELDS:
                bad = (num < 0) | (num.notna() & (num % 1 != 0))
                if f == "active_learning_days":
                    bad |= num > 7
            else:
                bad = num.notna() & ~num.between(0, 100)
            flag(bad.fillna(False), f"{label} has an impossible value - treated as missing")
            df.loc[bad.fillna(False), col] = np.nan

        sch, att = f"classes_scheduled_week{w}", f"classes_attended_week{w}"
        due, sub = f"assignments_due_week{w}", f"assignments_submitted_week{w}"
        bad = df[att] > df[sch]
        flag(bad, f"Week {w}: attended is greater than classes conducted - treated as missing")
        df.loc[bad, att] = np.nan
        bad = df[sub] > df[due]
        flag(bad, f"Week {w}: submitted is greater than assignments due - treated as missing")
        df.loc[bad, sub] = np.nan

        df[f"attendance_pct_week{w}"] = np.where(df[sch] > 0, df[att] / df[sch] * 100, np.nan)
        # zero assignments due = not applicable (NaN), not 0 %
        df[f"assignment_completion_week{w}"] = np.where(df[due] > 0, df[sub] / df[due] * 100, np.nan)
    return df, issues


# ------------------------------------------------------- feature engineering
def _slope(values: np.ndarray) -> np.ndarray:
    """Least-squares slope per row across observed weeks (needs >= 2 points)."""
    x = np.arange(1, values.shape[1] + 1, dtype=float)[None, :]
    mask = np.isfinite(values)
    n = mask.sum(axis=1)
    v = np.where(mask, values, 0.0)
    xm = np.where(mask, x, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        xbar = xm.sum(axis=1) / n
        vbar = v.sum(axis=1) / n
        dx = np.where(mask, x - xbar[:, None], 0.0)
        dv = np.where(mask, values - vbar[:, None], 0.0)
        slope = (dx * dv).sum(axis=1) / (dx ** 2).sum(axis=1)
    slope[n < 2] = np.nan
    return slope


def engineer(clean: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame(index=clean.index)
    for prefix, name in [("attendance_pct", "attendance"), ("assessment_score", "assessment"),
                         ("assignment_completion", "assignment"),
                         ("engagement_score", "engagement"),
                         ("active_learning_days", "active_days")]:
        cols = week_cols(prefix)
        vals = clean[cols].to_numpy(dtype=float)
        feats[f"{name}_avg"] = clean[cols].mean(axis=1)
        feats[f"{name}_latest"] = clean[cols].ffill(axis=1).iloc[:, -1]
        feats[f"{name}_missing_weeks"] = clean[cols].isna().sum(axis=1)
        feats[f"{name}_slope"] = _slope(vals)

    def weighted(num_prefix: str, den_prefix: str) -> np.ndarray:
        num = clean[week_cols(num_prefix)].to_numpy(dtype=float)
        den = clean[week_cols(den_prefix)].to_numpy(dtype=float)
        ok = np.isfinite(num) & np.isfinite(den)
        n, d = np.where(ok, num, 0).sum(axis=1), np.where(ok, den, 0).sum(axis=1)
        return np.where(d > 0, n / np.maximum(d, 1) * 100, np.nan)

    feats["weighted_attendance_pct"] = weighted("classes_attended", "classes_scheduled")
    feats["weighted_assignment_completion"] = weighted("assignments_submitted", "assignments_due")

    inputs = [f"{f}_week{w}" for w in WEEKS for f in WEEKLY_FIELDS]
    feats["missing_input_count"] = clean[inputs].isna().sum(axis=1)
    feats["observed_input_count"] = clean[inputs].notna().sum(axis=1)

    # ---- evidence rule (kept OUT of the model features)
    have = sum((feats[f"{n}_missing_weeks"] <= len(WEEKS) - MIN_WEEKS_PER_INDICATOR).astype(int)
               for n in MAIN_INDICATORS)
    feats["insufficient_data"] = (have < MIN_INDICATORS_WITH_EVIDENCE).astype(int)

    # ---- rule-based attendance alert (separate from the model)
    low = feats["weighted_attendance_pct"] < LOW_ATTENDANCE_PCT
    dec = feats["attendance_slope"] <= DECLINING_ATTENDANCE_SLOPE
    feats["attendance_alert"] = np.select(
        [low & dec, low, dec],
        ["Low and declining", "Low attendance", "Declining attendance"],
        default="No alert")
    feats.loc[feats["weighted_attendance_pct"].isna(), "attendance_alert"] = "Attendance data missing"
    feats["engagement_declining"] = (feats["engagement_slope"] < 0).astype(int)
    return feats


# ------------------------------------------------------------ trend warnings
def trend_status(values: list[float], drop: float) -> dict:
    """Classify one indicator's weekly series.

    A *sustained* decline needs three consecutive observed weeks that keep
    falling with a total drop of at least ``drop``.  A single poor result with
    otherwise steady values is reported as an *isolated dip* and is NOT treated
    as the student's trend.
    """
    obs = [(i + 1, float(v)) for i, v in enumerate(values) if v is not None and np.isfinite(v)]
    if len(obs) < 3:
        return {"status": "insufficient", "message": "Fewer than 3 weeks of data - no trend claimed."}
    ys = [v for _, v in obs]
    a, b, c = ys[-3:]
    if a > b > c and (a - c) >= drop:
        return {"status": "sustained_decline",
                "message": f"Fell for 3 consecutive weeks ({a:.0f} -> {b:.0f} -> {c:.0f})."}
    if a < b < c and (c - a) >= drop:
        return {"status": "improving",
                "message": f"Rose for 3 consecutive weeks ({a:.0f} -> {b:.0f} -> {c:.0f})."}
    for i, v in enumerate(ys):
        others = ys[:i] + ys[i + 1:]
        if len(others) >= 2 and (max(others) - min(others)) < drop and v <= float(np.median(others)) - drop:
            where = "latest week" if i == len(ys) - 1 else f"week {obs[i][0]}"
            tail = " Watch next week before calling it a trend." if i == len(ys) - 1 else " Other weeks are steady."
            return {"status": "isolated_dip",
                    "message": f"One low value in {where} ({v:.0f}); not treated as a trend.{tail}"}
    return {"status": "stable", "message": "No sustained change."}


def analyze_trends(clean: pd.DataFrame) -> list[dict]:
    series = {
        "attendance": clean[week_cols("attendance_pct")].to_numpy(dtype=float),
        "assessment": clean[week_cols("assessment_score")].to_numpy(dtype=float),
        "assignment": clean[week_cols("assignment_completion")].to_numpy(dtype=float),
        "engagement": clean[week_cols("engagement_score")].to_numpy(dtype=float),
    }
    out = []
    for i in range(len(clean)):
        row = {k: trend_status(list(v[i]), TREND_DROP[k]) for k, v in series.items()}
        decl = [k for k, t in row.items() if t["status"] == "sustained_decline"]
        out.append({"indicators": row, "sustained_declines": decl,
                    "warning": bool(decl)})
    return out


# -------------------------------------------------------- missing-data checks
def build_quality(clean: pd.DataFrame, issues: list[list[str]]) -> list[dict]:
    inputs = [(w, f) for w in WEEKS for f in WEEKLY_FIELDS]
    arr = clean[[f"{f}_week{w}" for w, f in inputs]].isna().to_numpy()
    out = []
    for i in range(len(clean)):
        missing = [f"Week {w}: {FIELD_LABELS[f]}" for (w, f), m in zip(inputs, arr[i]) if m]
        out.append({
            "missing": missing,
            "invalid": issues[i],
            "completeness_pct": round(100 * (1 - len(missing) / len(inputs)), 1),
            "incomplete": bool(missing or issues[i]),
        })
    return out


def process_wide(df: pd.DataFrame):
    """Full pipeline: clean -> features -> trends -> quality."""
    clean, issues = clean_wide(df)
    feats = engineer(clean)
    return clean, feats, analyze_trends(clean), build_quality(clean, issues)
