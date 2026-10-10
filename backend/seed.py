"""Load the dataset (+ clearly labelled simulated edge cases) into the SQL database.

    python -m backend.seed [--reset] [--csv path]
"""
from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import func, insert, select

from .db import DB_PATH, Intervention, Student, Base, get_engine, get_session, init_db
from .ml import get_model
from .services import score_and_store

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = Path(os.environ.get("EDURADAR_SEED_CSV", ROOT / "student_support_10000.csv"))
HIST_STATUS = {"Completed": "Completed", "Pending": "In progress"}


def _week_row(**vals):
    return vals


def edge_cases() -> pd.DataFrame:
    """Simulated records that exercise every rule in the deck."""
    nan = np.nan

    def build(sid, name, dept, att, sched, assess, due, sub, eng, days):
        r = {"student_id": sid, "student_name": name, "department": dept, "year_of_study": 2,
             "data_source": "simulated-edge-case"}
        for w in range(1, 5):
            i = w - 1
            r[f"classes_scheduled_week{w}"] = sched[i]
            r[f"classes_attended_week{w}"] = att[i]
            r[f"assessment_score_week{w}"] = assess[i]
            r[f"assignments_due_week{w}"] = due[i]
            r[f"assignments_submitted_week{w}"] = sub[i]
            r[f"engagement_score_week{w}"] = eng[i]
            r[f"active_learning_days_week{w}"] = days[i]
        return r

    s20 = [20, 20, 20, 20]
    rows = [
        build("SIM-E01", "Demo: Insufficient Data", "Computer Science", [18, nan, nan, nan], [20, nan, nan, nan],
              [nan, nan, 60, nan], [2, nan, nan, nan], [1, nan, nan, nan], [nan, nan, nan, 55], [nan, 4, nan, nan]),
        build("SIM-E02", "Demo: One Poor Test Only", "Civil", [19, 19, 19, 19], s20,
              [82, 80, 35, 81], [2, 2, 2, 2], [2, 2, 2, 2], [78, 80, 79, 81], [6, 6, 6, 6]),
        build("SIM-E03", "Demo: Sustained Decline", "Electronics", [18, 17, 14, 11], s20,
              [78, 70, 62, 51], [2, 2, 2, 2], [2, 2, 1, 0], [80, 70, 58, 45], [6, 5, 4, 2]),
        build("SIM-E04", "Demo: Invalid Entries", "Mechanical", [18, 25, 18, 18], s20,
              [75, 140, 72, 74], [2, 2, 2, 2], [2, 2, 3, 2], [70, 72, 71, 69], [6, 9, 6, 6]),
        build("SIM-E05", "Demo: No Assignments Due", "Business Studies", [19, 18, 19, 18], s20,
              [70, 72, 69, 71], [0, 0, 0, 0], [0, 0, 0, 0], [66, 67, 65, 66], [5, 5, 5, 5]),
        build("SIM-E06", "Demo: Low Steady Attendance", "Mechanical", [12, 12, 12, 12], s20,
              [85, 84, 86, 85], [2, 2, 2, 2], [2, 2, 2, 2], [82, 83, 84, 82], [6, 6, 6, 6]),
        build("SIM-E07", "Demo: Recovering Student", "Civil", [13, 15, 17, 19], s20,
              [48, 55, 63, 72], [2, 2, 2, 2], [1, 1, 2, 2], [45, 55, 65, 74], [3, 4, 5, 6]),
        build("SIM-E08", "Demo: Two Missing Weeks", "Computer Science", [18, nan, nan, 17], [20, nan, nan, 20],
              [70, nan, nan, 66], [2, nan, nan, 2], [2, nan, nan, 1], [64, nan, nan, 60], [5, nan, nan, 5]),
    ]
    return pd.DataFrame(rows)


def seed(csv: Path = DEFAULT_CSV, reset: bool = False) -> dict:
    if reset:
        get_engine().dispose()
        for suffix in ("", "-wal", "-shm"):
            Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
        import backend.db as dbm
        dbm._engine = None
    init_db()
    s = get_session()
    if s.execute(select(func.count()).select_from(Student)).scalar():
        s.close()
        return {"skipped": "database already has students"}
    model = get_model()
    df = pd.read_csv(csv).drop_duplicates("student_id").reset_index(drop=True)
    df["student_id"] = df["student_id"].astype(str)
    df["data_source"] = df.get("data_source", "synthetic")
    labels = {}
    if "future_withdrawal_by_week16" in df:
        y = pd.to_numeric(df["future_withdrawal_by_week16"], errors="coerce")
        labels = {sid: int(v) for sid, v in zip(df["student_id"], y) if v in (0, 1)}
    summary = score_and_store(s, df, df[["student_id", "student_name", "department", "year_of_study", "data_source"]],
                              source="seed", labels=labels, split_map=model.split, commit=False)

    # ---- historical (simulated) interventions recorded in the dataset
    today = date.today()
    base = {r.student_id: r for r in df.itertuples()}
    rows = []
    for r in df.itertuples():
        itype = getattr(r, "intervention_type_after_week4", None)
        if not isinstance(itype, str) or itype == "None":
            continue
        status = HIST_STATUS.get(getattr(r, "intervention_status_week8", ""), "In progress")

        def pct(a, b):
            a, b = getattr(r, a, np.nan), getattr(r, b, np.nan)
            return None if (pd.isna(a) or pd.isna(b) or not b) else round(a / b * 100, 1)

        def val(x):
            x = getattr(r, x, np.nan)
            return None if pd.isna(x) else round(float(x), 1)

        followup = None
        if status == "Completed":
            followup = {"attendance_pct": val("followup_attendance_pct_week8"),
                        "assignment_completion_pct": val("followup_assignment_completion_pct_week8"),
                        "engagement_score": val("followup_engagement_score_week8")}
        rows.append(dict(
            student_id=r.student_id, type=itype,
            action=f"{itype} started in week {int(r.intervention_week)} (simulated record from dataset)",
            owner="Simulated (dataset)", status=status,
            followup_date=today + timedelta(days=-7 if status == "Completed" else 7),
            baseline={"attendance_pct": val("attendance_pct_week4"),
                      "assignment_completion_pct": pct("assignments_submitted_week4", "assignments_due_week4"),
                      "engagement_score": val("engagement_score_week4")},
            followup=followup, source="simulated",
            outcome_notes="Simulated follow-up from dataset week-8 columns." if followup else None,
            completed_at=None))
    for i in range(0, len(rows), 500):
        s.execute(insert(Intervention), rows[i:i + 500])

    # ---- labelled simulated edge cases
    edge = edge_cases()
    score_and_store(s, edge, edge[["student_id", "student_name", "department", "year_of_study", "data_source"]],
                    source="seed-edge", split_map={}, commit=False)
    s.commit()
    s.close()
    summary["interventions_seeded"] = len(rows)
    summary["edge_cases"] = len(edge)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    a = ap.parse_args()
    print(seed(Path(a.csv), a.reset))
