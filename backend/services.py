"""Scoring + persistence helpers shared by seed, uploads and re-scoring."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from .db import Intervention, Prediction, Review, Student, WeeklyRecord
from .feature_engineering import MODEL_FEATURES, WEEKLY_FIELDS, WEEKS, process_wide
from .ml import MODEL_VERSION, get_model

CHUNK = 500


def _clean_json(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    return v


def _none(v):
    v = _clean_json(v)
    return v


def baseline_from_features(f: dict) -> dict:
    def r(v):
        v = _none(v)
        return None if v is None else round(v, 1)
    return {"attendance_pct": r(f.get("attendance_latest")),
            "assignment_completion_pct": r(f.get("assignment_latest")),
            "engagement_score": r(f.get("engagement_latest"))}


def wide_from_db(s: Session, ids: list[str]) -> pd.DataFrame:
    rows = []
    for i in range(0, len(ids), CHUNK):
        part = ids[i:i + CHUNK]
        rows += s.execute(select(WeeklyRecord).where(WeeklyRecord.student_id.in_(part))).scalars().all()
    data: dict[str, dict] = {sid: {"student_id": sid} for sid in ids}
    for r in rows:
        for f in WEEKLY_FIELDS:
            data[r.student_id][f"{f}_week{r.week}"] = getattr(r, f)
    return pd.DataFrame(list(data.values()))


def score_and_store(s: Session, wide: pd.DataFrame, meta: pd.DataFrame | None = None, *,
                    source: str = "upload", labels: dict | None = None, split_map: dict | None = None,
                    commit: bool = True) -> dict:
    """Clean -> engineer -> score -> persist.  Appends a new immutable Prediction per student.

    ``meta`` may supply student_name / department / year_of_study / data_source per student_id.
    Existing students keep their metadata unless the new file supplies it.
    """
    model = get_model()
    wide = wide.reset_index(drop=True)
    clean, feats, trends, quality = process_wide(wide)
    results = model.score(feats)
    ids = wide["student_id"].astype(str).tolist()
    meta_d = {}
    if meta is not None:
        meta_d = meta.drop_duplicates("student_id", keep="last").set_index("student_id").to_dict("index")

    existing = {}
    for i in range(0, len(ids), CHUNK):
        for st in s.execute(select(Student).where(Student.student_id.in_(ids[i:i + CHUNK]))).scalars():
            existing[st.student_id] = st
    ex_ids = list(existing)
    for i in range(0, len(ex_ids), CHUNK):
        part = ex_ids[i:i + CHUNK]
        s.execute(update(Prediction).where(Prediction.student_id.in_(part)).values(is_latest=False))
        s.query(WeeklyRecord).filter(WeeklyRecord.student_id.in_(part)).delete(synchronize_session=False)

    new_students, upd_students, weekly, preds = [], [], [], []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    feat_rows = feats[MODEL_FEATURES].to_dict("records")
    for i, sid in enumerate(ids):
        res, tr, q = results[i], trends[i], quality[i]
        m = meta_d.get(sid, {})
        priority = res["priority"]
        alert = str(feats.at[i, "attendance_alert"])
        denorm = dict(model_priority=priority, effective_priority=priority, score=res["score"],
                      attendance_alert=alert, trend_warning=tr["warning"], incomplete=q["incomplete"],
                      reviewed=False, updated_at=now)
        if sid in existing:
            d = {"student_id": sid, **denorm}
            for key, col in (("student_name", "name"), ("department", "department"),
                             ("year_of_study", "year_of_study"), ("data_source", "data_source")):
                if m.get(key) is not None and not (isinstance(m.get(key), float) and math.isnan(m[key])):
                    d[col] = m[key]
            if labels and sid in labels:
                d["actual_withdrawal"] = labels[sid]
            upd_students.append(d)
        else:
            yr = m.get("year_of_study")
            new_students.append(dict(
                student_id=sid, name=str(m.get("student_name") or sid),
                department=str(m.get("department") or "Unknown"),
                year_of_study=None if yr is None or (isinstance(yr, float) and math.isnan(yr)) else int(yr),
                data_source=str(m.get("data_source") or "upload"),
                split=(split_map or {}).get(sid, "upload"),
                actual_withdrawal=(labels or {}).get(sid), **denorm))
        for w in WEEKS:
            rec = {"student_id": sid, "week": w}
            for f in WEEKLY_FIELDS:
                rec[f] = _none(clean.at[i, f"{f}_week{w}"])
            weekly.append(rec)
        preds.append(dict(
            student_id=sid, created_at=now, model_version=MODEL_VERSION, score=res["score"],
            priority=priority, insufficient_data=priority == "Insufficient Data",
            attendance_alert=alert, factors=res["factors"], trends=tr, quality=q,
            features={k: _none(v) for k, v in feat_rows[i].items()}, is_latest=True, source=source))

    for i in range(0, len(new_students), CHUNK):
        s.execute(insert(Student), new_students[i:i + CHUNK])
    if upd_students:
        s.bulk_update_mappings(Student, upd_students)
    for i in range(0, len(weekly), 2000):
        s.execute(insert(WeeklyRecord), weekly[i:i + 2000])
    for i in range(0, len(preds), CHUNK):
        s.execute(insert(Prediction), preds[i:i + CHUNK])
    if commit:
        s.commit()

    pr = pd.Series([r["priority"] for r in results]).value_counts().to_dict()
    return {
        "students": len(ids), "created": len(new_students), "updated": len(upd_students),
        "priority_counts": pr,
        "incomplete_records": sum(q["incomplete"] for q in quality),
        "insufficient_data": int(pr.get("Insufficient Data", 0)),
        "trend_warnings": sum(t["warning"] for t in trends),
        "attendance_alerts": int((feats["attendance_alert"].isin(
            ["Low attendance", "Declining attendance", "Low and declining"])).sum()),
    }


def latest_prediction(s: Session, student_id: str) -> Prediction | None:
    return s.execute(select(Prediction).where(Prediction.student_id == student_id,
                                              Prediction.is_latest.is_(True))).scalars().first()


def latest_review(s: Session, prediction_id: int) -> Review | None:
    return s.execute(select(Review).where(Review.prediction_id == prediction_id)
                     .order_by(Review.id.desc())).scalars().first()
