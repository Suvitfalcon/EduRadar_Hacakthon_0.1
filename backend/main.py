"""EduRadar API - AI-based student dropout (course withdrawal) risk indicator."""
from __future__ import annotations

import io
import math
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .db import Intervention, Prediction, Review, Student, Upload, WeeklyRecord, init_db, session_dep
from .copilot import router as copilot_router
from .auth import router as auth_router, lookup_teacher, bootstrap_teacher, digest
from .feature_engineering import (LOW_ATTENDANCE_PCT, DECLINING_ATTENDANCE_SLOPE, MIN_INDICATORS_WITH_EVIDENCE,
                                  MIN_WEEKS_PER_INDICATOR, WEEKS, WEEKLY_FIELDS)
from .ml import MODEL_VERSION, get_model
from .seed import seed
from .services import baseline_from_features, latest_prediction, latest_review, score_and_store, wide_from_db

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"
PRIORITIES = ["High", "Medium", "Low", "Insufficient Data"]
RANK = case({"High": 0, "Medium": 1, "Low": 2, "Insufficient Data": 3}, value=Student.effective_priority, else_=4)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
INTERVENTION_TYPES = ["Academic tutoring", "Assignment support", "Attendance counselling", "Mentoring", "Other"]
STATUSES = ["Planned", "In progress", "Completed", "Cancelled"]
DISCLAIMER = ("Course-withdrawal risk indicator for teacher prioritisation, not a verdict on any student. "
              "Records labelled 'synthetic' / 'simulated' are simulated. No impact claim is made before evaluation.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    bootstrap_teacher()
    seed()  # no-op when the database already holds students
    get_model()
    yield


app = FastAPI(title="EduRadar API", description="AI-Based Student Dropout Risk Indicator",
              version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


app.include_router(copilot_router)
app.include_router(auth_router)

from fastapi.responses import JSONResponse
import hmac

@app.middleware("http")
async def enforce_teacher_login(request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in ("/api/health", "/api/auth/login", "/api/auth/me"):
        if request.method == "OPTIONS":
            return await call_next(request)
        teacher = lookup_teacher(request)
        if not teacher:
            return JSONResponse({"detail": "Teacher login required"}, status_code=401)
        request.state.teacher = teacher
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            csrf = request.headers.get("x-eduradar-csrf", "")
            if not csrf or not hmac.compare_digest(digest(csrf), teacher["csrf_hash"]):
                return JSONResponse({"detail": "Invalid security token. Please log in again"}, status_code=403)
    return await call_next(request)


# ------------------------------------------------------------------ helpers
def nn(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        return None if (math.isnan(v) or math.isinf(v)) else round(float(v), 2)
    if isinstance(v, np.integer):
        return int(v)
    return v


def student_row(st: Student, open_iv: int = 0) -> dict:
    return {"student_id": st.student_id, "name": st.name, "department": st.department,
            "year_of_study": st.year_of_study, "data_source": st.data_source, "split": st.split,
            "model_priority": st.model_priority, "priority": st.effective_priority,
            "overridden": st.reviewed and st.effective_priority != st.model_priority,
            "score": st.score, "attendance_alert": st.attendance_alert,
            "trend_warning": st.trend_warning, "incomplete": st.incomplete, "reviewed": st.reviewed,
            "open_interventions": open_iv}


def apply_filters(q, priority=None, department=None, search=None, alert=None, trend=None,
                  incomplete=None, reviewed=None, source=None, needs_action=None):
    if priority:
        q = q.where(Student.effective_priority.in_([p.strip() for p in priority.split(",")]))
    if department:
        q = q.where(Student.department == department)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Student.name.ilike(like), Student.student_id.ilike(like)))
    if alert == "any":
        q = q.where(Student.attendance_alert.in_(["Low attendance", "Declining attendance", "Low and declining"]))
    elif alert:
        q = q.where(Student.attendance_alert == alert)
    if trend is not None:
        q = q.where(Student.trend_warning.is_(trend))
    if incomplete is not None:
        q = q.where(Student.incomplete.is_(incomplete))
    if reviewed is not None:
        q = q.where(Student.reviewed.is_(reviewed))
    if source:
        q = q.where(Student.data_source == source)
    if needs_action:
        active = select(Intervention.id).where(Intervention.student_id == Student.student_id,
                                               Intervention.status.in_(["Planned", "In progress"])).exists()
        q = q.where(Student.effective_priority.in_(["High", "Medium"]), ~active)
    return q


def get_student_or_404(s: Session, sid: str) -> Student:
    st = s.get(Student, sid)
    if not st:
        raise HTTPException(404, f"Student {sid} not found")
    return st


def iv_dict(iv: Intervention) -> dict:
    deltas = {}
    if iv.baseline and iv.followup:
        for k in ("attendance_pct", "assignment_completion_pct", "engagement_score"):
            b, f = iv.baseline.get(k), iv.followup.get(k)
            deltas[k] = None if b is None or f is None else round(f - b, 1)
    overdue = iv.status in ("Planned", "In progress") and iv.followup_date < date.today()
    return {"id": iv.id, "student_id": iv.student_id, "type": iv.type, "action": iv.action, "owner": iv.owner,
            "followup_date": iv.followup_date.isoformat(), "status": iv.status, "overdue": overdue,
            "baseline": iv.baseline, "followup": iv.followup, "deltas": deltas, "outcome_notes": iv.outcome_notes,
            "source": iv.source, "created_at": iv.created_at.isoformat(),
            "completed_at": iv.completed_at.isoformat() if iv.completed_at else None}


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health():
    return {"status": "healthy", "model": MODEL_VERSION}


@app.get("/api/config")
def config():
    m = get_model()
    return {"model_version": MODEL_VERSION, "thresholds": m.thresholds, "priorities": PRIORITIES,
            "intervention_types": INTERVENTION_TYPES, "statuses": STATUSES, "disclaimer": DISCLAIMER,
            "rules": {"low_attendance_pct": LOW_ATTENDANCE_PCT, "declining_slope_per_week": DECLINING_ATTENDANCE_SLOPE,
                      "min_weeks_per_indicator": MIN_WEEKS_PER_INDICATOR,
                      "min_indicators_with_evidence": MIN_INDICATORS_WITH_EVIDENCE}}


# ------------------------------------------------------------------ dashboard
@app.get("/api/summary")
def summary(s: Session = Depends(session_dep)):
    total = s.scalar(select(func.count()).select_from(Student))
    by_pri = dict(s.execute(select(Student.effective_priority, func.count()).group_by(Student.effective_priority)).all())
    dept = {}
    for d, p, n in s.execute(select(Student.department, Student.effective_priority, func.count())
                             .group_by(Student.department, Student.effective_priority)):
        dept.setdefault(d, {})[p] = n
    alert_any = ["Low attendance", "Declining attendance", "Low and declining"]
    active = select(Intervention.id).where(Intervention.student_id == Student.student_id,
                                           Intervention.status.in_(["Planned", "In progress"])).exists()
    cnt = lambda *c: s.scalar(select(func.count()).select_from(Student).where(*c))  # noqa: E731
    iv = dict(s.execute(select(Intervention.status, func.count()).group_by(Intervention.status)).all())
    overdue = s.scalar(select(func.count()).select_from(Intervention).where(
        Intervention.status.in_(["Planned", "In progress"]), Intervention.followup_date < date.today()))
    top = s.execute(apply_filters(select(Student), priority="High", needs_action=True)
                    .order_by(Student.score.desc()).limit(8)).scalars().all()
    return {
        "total_students": total, "by_priority": {p: by_pri.get(p, 0) for p in PRIORITIES},
        "by_department": dept,
        "attendance_alerts": cnt(Student.attendance_alert.in_(alert_any)),
        "trend_warnings": cnt(Student.trend_warning.is_(True)),
        "incomplete_records": cnt(Student.incomplete.is_(True)),
        "insufficient_data": by_pri.get("Insufficient Data", 0),
        "awaiting_review": cnt(Student.effective_priority.in_(["High", "Medium"]), Student.reviewed.is_(False)),
        "overridden": cnt(Student.reviewed.is_(True), Student.effective_priority != Student.model_priority),
        "needs_support_plan": cnt(Student.effective_priority.in_(["High", "Medium"]), ~active),
        "interventions": {st: iv.get(st, 0) for st in STATUSES}, "overdue_followups": overdue,
        "top_needs_action": [student_row(t) for t in top],
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------ students
@app.get("/api/departments")
def departments(s: Session = Depends(session_dep)):
    return [d for (d,) in s.execute(select(Student.department).distinct().order_by(Student.department))]


@app.get("/api/students")
def list_students(priority: str | None = None, department: str | None = None, search: str | None = None,
                  alert: str | None = None, trend: bool | None = None, incomplete: bool | None = None,
                  reviewed: bool | None = None, source: str | None = None, needs_action: bool | None = None,
                  sort: Literal["risk", "score", "name", "attendance"] = "risk",
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                  s: Session = Depends(session_dep)):
    base = apply_filters(select(Student), priority, department, search, alert, trend, incomplete, reviewed,
                         source, needs_action)
    total = s.scalar(select(func.count()).select_from(base.subquery()))
    order = {"risk": [RANK, Student.score.desc()], "score": [Student.score.desc()],
             "name": [Student.name], "attendance": [Student.attendance_alert.desc(), Student.score.desc()]}[sort]
    rows = s.execute(base.order_by(*order, Student.student_id).offset((page - 1) * page_size).limit(page_size)
                     ).scalars().all()
    ids = [r.student_id for r in rows]
    open_counts = dict(s.execute(select(Intervention.student_id, func.count()).where(
        Intervention.student_id.in_(ids), Intervention.status.in_(["Planned", "In progress"]))
        .group_by(Intervention.student_id)).all()) if ids else {}
    return {"total": total, "page": page, "page_size": page_size,
            "items": [student_row(r, open_counts.get(r.student_id, 0)) for r in rows]}


@app.get("/api/students/{student_id}")
def student_profile(student_id: str, s: Session = Depends(session_dep)):
    st = get_student_or_404(s, student_id)
    pred = latest_prediction(s, student_id)
    weeks = []
    for w in st.weekly:
        att = (w.classes_attended / w.classes_scheduled * 100
               if w.classes_attended is not None and w.classes_scheduled else None)
        comp = (w.assignments_submitted / w.assignments_due * 100
                if w.assignments_submitted is not None and w.assignments_due else None)
        weeks.append({"week": w.week, **{f: nn(getattr(w, f)) for f in WEEKLY_FIELDS},
                      "attendance_pct": nn(att), "assignment_completion_pct": nn(comp),
                      "assignment_not_applicable": w.assignments_due == 0})
    reviews = s.execute(select(Review).where(Review.student_id == student_id).order_by(Review.id.desc())).scalars().all()
    ivs = s.execute(select(Intervention).where(Intervention.student_id == student_id)
                    .order_by(Intervention.id.desc())).scalars().all()
    history = s.execute(select(Prediction.id, Prediction.created_at, Prediction.priority, Prediction.score,
                               Prediction.source).where(Prediction.student_id == student_id)
                        .order_by(Prediction.id.desc())).all()
    current_review = latest_review(s, pred.id) if pred else None
    return {
        "student": student_row(st),
        "prediction": None if not pred else {
            "id": pred.id, "created_at": pred.created_at.isoformat(), "model_version": pred.model_version,
            "score": pred.score, "priority": pred.priority, "insufficient_data": pred.insufficient_data,
            "factors": pred.factors, "features": pred.features, "base_rate": get_model().tree.tree_.value[0, 0, 1]
            / get_model().tree.tree_.value[0, 0].sum(),
            "source": pred.source},
        "attendance": {"alert": st.attendance_alert, "weighted_pct": nn((pred.features or {}).get("weighted_attendance_pct")) if pred else None,
                       "slope": nn((pred.features or {}).get("attendance_slope")) if pred else None,
                       "rule": f"Alert if overall attendance < {LOW_ATTENDANCE_PCT:.0f}% and/or it falls by {abs(DECLINING_ATTENDANCE_SLOPE):.0f}+ points per week."},
        "trends": pred.trends if pred else None, "quality": pred.quality if pred else None,
        "weeks": weeks,
        "current_review": None if not current_review else {
            "decision": current_review.decision, "original_priority": current_review.original_priority,
            "final_priority": current_review.final_priority, "reason": current_review.reason,
            "reviewer": current_review.reviewer, "created_at": current_review.created_at.isoformat()},
        "reviews": [{"id": r.id, "prediction_id": r.prediction_id, "decision": r.decision,
                     "original_priority": r.original_priority, "final_priority": r.final_priority,
                     "reason": r.reason, "reviewer": r.reviewer, "created_at": r.created_at.isoformat()} for r in reviews],
        "interventions": [iv_dict(i) for i in ivs],
        "history": [{"id": h.id, "created_at": h.created_at.isoformat(), "priority": h.priority, "score": h.score,
                     "source": h.source} for h in history],
    }


# ------------------------------------------------------------------ teacher review
class ReviewIn(BaseModel):
    decision: Literal["accept", "override"]
    final_priority: Literal["High", "Medium", "Low"] | None = None
    reason: str | None = None
    reviewer: str = Field(min_length=1, max_length=80)


@app.post("/api/students/{student_id}/review", status_code=201)
def review_student(student_id: str, body: ReviewIn, request: Request, s: Session = Depends(session_dep)):
    st = get_student_or_404(s, student_id)
    pred = latest_prediction(s, student_id)
    if not pred:
        raise HTTPException(409, "No model result to review")
    reason = (body.reason or "").strip()
    if body.decision == "override":
        if not body.final_priority:
            raise HTTPException(422, "final_priority is required to override")
        if len(reason) < 5:
            raise HTTPException(422, "A reason (at least 5 characters) is required to override the priority")
        if body.final_priority == pred.priority:
            raise HTTPException(422, "Override must differ from the model priority - use Accept instead")
        final = body.final_priority
    else:
        if pred.priority == "Insufficient Data":
            raise HTTPException(422, "The model gave no result (insufficient data). Override with a reason, or complete the data.")
        final = pred.priority
    r = Review(student_id=student_id, prediction_id=pred.id, decision=body.decision, original_priority=pred.priority,
               final_priority=final, reason=reason or None, reviewer=request.state.teacher["display_name"])
    s.add(r)
    st.effective_priority, st.reviewed = final, True   # prediction row itself is never touched
    s.commit()
    return {"ok": True, "original_priority": pred.priority, "final_priority": final}


# ------------------------------------------------------------------ support tracking
class InterventionIn(BaseModel):
    type: str
    action: str = Field(min_length=3)
    owner: str = Field(min_length=1, max_length=80)
    followup_date: date
    status: Literal["Planned", "In progress"] = "Planned"

    @field_validator("type")
    @classmethod
    def _t(cls, v):
        if v not in INTERVENTION_TYPES:
            raise ValueError(f"type must be one of {INTERVENTION_TYPES}")
        return v


class Indicators(BaseModel):
    attendance_pct: float | None = Field(None, ge=0, le=100)
    assignment_completion_pct: float | None = Field(None, ge=0, le=100)
    engagement_score: float | None = Field(None, ge=0, le=100)


class InterventionPatch(BaseModel):
    status: Literal["Planned", "In progress", "Completed", "Cancelled"] | None = None
    action: str | None = None
    owner: str | None = None
    followup_date: date | None = None
    outcome_notes: str | None = None
    followup: Indicators | None = None


@app.post("/api/students/{student_id}/interventions", status_code=201)
def create_intervention(student_id: str, body: InterventionIn, s: Session = Depends(session_dep)):
    get_student_or_404(s, student_id)
    if body.followup_date < date.today():
        raise HTTPException(422, "Follow-up date cannot be in the past")
    pred = latest_prediction(s, student_id)
    iv = Intervention(student_id=student_id, type=body.type, action=body.action.strip(), owner=body.owner.strip(),
                      followup_date=body.followup_date, status=body.status, source="teacher",
                      baseline=baseline_from_features(pred.features) if pred else None)
    s.add(iv)
    s.commit()
    return iv_dict(iv)


@app.patch("/api/interventions/{iv_id}")
def update_intervention(iv_id: int, body: InterventionPatch, s: Session = Depends(session_dep)):
    iv = s.get(Intervention, iv_id)
    if not iv:
        raise HTTPException(404, "Intervention not found")
    if iv.status in ("Completed", "Cancelled") and body.status not in (None, iv.status):
        raise HTTPException(409, f"A {iv.status.lower()} follow-up cannot be reopened")
    if body.status == "Completed":
        notes = (body.outcome_notes if body.outcome_notes is not None else iv.outcome_notes) or ""
        if len(notes.strip()) < 3:
            raise HTTPException(422, "Outcome notes are required to complete a follow-up")
        fu = body.followup.model_dump() if body.followup else iv.followup
        if not fu or all(v is None for v in fu.values()):
            raise HTTPException(422, "Record at least one follow-up indicator to compare against the baseline")
        iv.followup = fu
        iv.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    elif body.followup is not None:
        iv.followup = body.followup.model_dump()
    if body.status:
        iv.status = body.status
    for f in ("action", "owner", "followup_date", "outcome_notes"):
        v = getattr(body, f)
        if v is not None:
            setattr(iv, f, v.strip() if isinstance(v, str) else v)
    s.commit()
    return iv_dict(iv)


@app.get("/api/interventions")
def list_interventions(status: str | None = None, overdue: bool | None = None, owner: str | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                       s: Session = Depends(session_dep)):
    q = select(Intervention, Student.name, Student.effective_priority).join(Student)
    if status:
        q = q.where(Intervention.status == status)
    if owner:
        q = q.where(Intervention.owner.ilike(f"%{owner}%"))
    if overdue:
        q = q.where(Intervention.status.in_(["Planned", "In progress"]), Intervention.followup_date < date.today())
    total = s.scalar(select(func.count()).select_from(q.subquery()))
    rows = s.execute(q.order_by(Intervention.followup_date, Intervention.id).offset((page - 1) * page_size)
                     .limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{**iv_dict(i), "student_name": n, "student_priority": p} for i, n, p in rows]}


# ------------------------------------------------------------------ data quality
@app.get("/api/data-quality")
def data_quality(insufficient: bool | None = None, search: str | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                 s: Session = Depends(session_dep)):
    q = select(Student, Prediction).join(Prediction, and_(Prediction.student_id == Student.student_id,
                                                        Prediction.is_latest.is_(True))).where(Student.incomplete.is_(True))
    if insufficient:
        q = q.where(Student.effective_priority == "Insufficient Data")
    if search:
        q = q.where(or_(Student.name.ilike(f"%{search}%"), Student.student_id.ilike(f"%{search}%")))
    total = s.scalar(select(func.count()).select_from(q.subquery()))
    rows = s.execute(q.order_by(RANK, Student.student_id).offset((page - 1) * page_size).limit(page_size)).all()
    # tally of the most common gaps (across all incomplete records)
    tally: dict[str, int] = {}
    for (qual,) in s.execute(select(Prediction.quality).join(Student, Student.student_id == Prediction.student_id)
                             .where(Prediction.is_latest.is_(True), Student.incomplete.is_(True))):
        for m in qual.get("missing", []):
            key = m.split(": ", 1)[1]
            tally[key] = tally.get(key, 0) + 1
    return {"total": total, "page": page, "page_size": page_size,
            "common_gaps": sorted(({"field": k, "records": v} for k, v in tally.items()), key=lambda d: -d["records"])[:7],
            "rule": (f"Insufficient data: fewer than {MIN_INDICATORS_WITH_EVIDENCE} of the 4 main indicators "
                     f"(attendance, assessment, assignments, engagement) have at least {MIN_WEEKS_PER_INDICATOR} weeks of data."),
            "items": [{**student_row(st), "completeness_pct": p.quality["completeness_pct"],
                       "missing": p.quality["missing"], "invalid": p.quality["invalid"]} for st, p in rows]}


# ------------------------------------------------------------------ evaluation
@app.get("/api/metrics")
def metrics(s: Session = Depends(session_dep)):
    rows = s.execute(select(Prediction.priority, Student.actual_withdrawal).join(
        Student, Student.student_id == Prediction.student_id).where(
        Prediction.source == "seed", Student.split == "test", Student.actual_withdrawal.is_not(None))).all()
    df = pd.DataFrame(rows, columns=["priority", "y"])
    scored = df[df.priority != "Insufficient Data"]
    n_pos = int(scored.y.sum())

    def block(levels):
        flagged = scored[scored.priority.isin(levels)]
        tp = int(flagged.y.sum())
        return {"levels": levels, "flagged": int(len(flagged)), "true_withdrawals_flagged": tp,
                "alert_precision": round(tp / len(flagged), 3) if len(flagged) else None,
                "withdrawal_recall": round(tp / n_pos, 3) if n_pos else None}

    by_level = {p: {"students": int((scored.priority == p).sum()),
                    "withdrawal_rate": (round(float(scored[scored.priority == p].y.mean()), 3)
                                        if (scored.priority == p).any() else None)} for p in ["High", "Medium", "Low"]}
    iv_all = dict(s.execute(select(Intervention.status, func.count()).group_by(Intervention.status)).all())
    iv_teacher = dict(s.execute(select(Intervention.status, func.count()).where(Intervention.source == "teacher")
                                .group_by(Intervention.status)).all())
    total_iv = sum(iv_all.values())
    reviews = s.execute(select(Review.decision, func.count()).group_by(Review.decision)).all()
    rv = dict(reviews)
    return {
        "evaluation_set": {"students": int(len(df)), "withdrawals": n_pos, "insufficient_data_excluded": int((df.priority == "Insufficient Data").sum()),
                           "note": "Held-out test students only (never used for training, tuning or thresholds). Simulated outcome labels - these figures are not evidence of real-world impact."},
        "high_priority": block(["High"]), "medium_or_high": block(["High", "Medium"]),
        "by_priority": by_level,
        "completed_followups": {"completed": iv_all.get("Completed", 0), "total": total_iv,
                                "completion_rate": round(iv_all.get("Completed", 0) / total_iv, 3) if total_iv else None,
                                "teacher_created": sum(iv_teacher.values()), "teacher_completed": iv_teacher.get("Completed", 0),
                                "by_status": iv_all},
        "teacher_review": {"accepted": rv.get("accept", 0), "overridden": rv.get("override", 0)},
        "model": {"version": MODEL_VERSION, "thresholds": get_model().thresholds, "training": get_model().training_metrics},
        "risks": ["Future-data leakage prevented: only weeks 1-4 behaviour is used; follow-up and outcome columns are never features.",
                  "Separate test students: split is by student; thresholds and tree size are chosen on validation data only.",
                  "The label is withdrawal by week 16 (course withdrawal), not permanent dropout.",
                  "Teacher review is kept: the original model result is preserved beside any override."],
    }


# ------------------------------------------------------------------ uploads
async def read_csv_upload(file: UploadFile) -> pd.DataFrame:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 15 MB")
    if not raw.strip():
        raise HTTPException(422, "The file is empty")
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=True, skipinitialspace=True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Could not read the file as CSV: {e}") from e
    df.columns = [str(c).strip().lower() for c in df.columns]
    if df.empty:
        raise HTTPException(422, "The CSV has a header but no rows")
    return df


@app.post("/api/upload/students")
async def upload_students(file: UploadFile = File(...), s: Session = Depends(session_dep)):
    df = await read_csv_upload(file)
    if "student_id" not in df.columns:
        raise HTTPException(422, "Missing required column: student_id")
    weekly_cols = [f"{f}_week{w}" for w in WEEKS for f in WEEKLY_FIELDS]
    present = [c for c in weekly_cols if c in df.columns]
    if not present:
        raise HTTPException(422, "No weekly columns found, e.g. classes_attended_week1, assessment_score_week1 ...")
    rejected = []
    df["student_id"] = df["student_id"].fillna("").astype(str).str.strip()
    blank = df["student_id"].isin(["", "nan", "None"])
    if blank.any():
        rejected.append(f"{int(blank.sum())} row(s) without student_id were skipped")
        df = df[~blank]
    dup = df["student_id"].duplicated(keep="last")
    if dup.any():
        rejected.append(f"{int(dup.sum())} duplicate student_id row(s) - the last one was kept")
        df = df[~dup]
    if df.empty:
        raise HTTPException(422, "No usable rows")
    meta = pd.DataFrame({"student_id": df["student_id"],
                         "student_name": df.get("student_name", pd.Series([None] * len(df), index=df.index)),
                         "department": df.get("department", pd.Series([None] * len(df), index=df.index)),
                         "year_of_study": pd.to_numeric(df.get("year_of_study", pd.Series([None] * len(df), index=df.index)),
                                                        errors="coerce"),
                         "data_source": "upload"})
    ignored = [c for c in df.columns if c.startswith("future_") or c.startswith("followup_")]
    result = score_and_store(s, df[["student_id"] + present], meta, source="upload")
    result.update({"filename": file.filename, "weekly_columns_found": len(present),
                   "weekly_columns_expected": len(weekly_cols), "warnings": rejected,
                   "ignored_columns": ignored,
                   "note": "Outcome / follow-up columns are never used as model inputs." if ignored else None})
    s.add(Upload(kind="students", filename=file.filename or "students.csv", summary=result))
    s.commit()
    return result


@app.post("/api/upload/attendance")
async def upload_attendance(file: UploadFile = File(...), s: Session = Depends(session_dep)):
    df = await read_csv_upload(file)
    if "classes_scheduled" not in df.columns and "classes_conducted" in df.columns:
        df = df.rename(columns={"classes_conducted": "classes_scheduled"})
    need = ["student_id", "week", "classes_attended", "classes_scheduled"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise HTTPException(422, f"Missing column(s): {', '.join(miss)} (classes_conducted is accepted for classes_scheduled)")
    df["student_id"] = df["student_id"].fillna("").astype(str).str.strip()
    errors, good = [], []
    known = {sid for (sid,) in s.execute(select(Student.student_id).where(Student.student_id.in_(df["student_id"].unique().tolist())))}
    for i, r in df.iterrows():
        line = i + 2
        try:
            w = float(r["week"]); att = float(r["classes_attended"]); sch = float(r["classes_scheduled"])
        except (TypeError, ValueError):
            errors.append(f"Line {line}: week / attended / conducted must be numbers"); continue
        if r["student_id"] not in known:
            errors.append(f"Line {line}: unknown student {r['student_id']}"); continue
        if w not in (1, 2, 3, 4):
            errors.append(f"Line {line}: week must be 1-4"); continue
        if any(math.isnan(x) or x < 0 or x % 1 for x in (att, sch)):
            errors.append(f"Line {line}: counts must be whole numbers >= 0"); continue
        if att > sch:
            errors.append(f"Line {line}: attended ({int(att)}) is greater than conducted ({int(sch)}) - row skipped"); continue
        good.append((r["student_id"], int(w), att, sch))
    if not good:
        raise HTTPException(422, {"message": "No valid attendance rows", "errors": errors[:50]})
    ids = sorted({g[0] for g in good})
    for sid, w, att, sch in good:
        rec = s.execute(select(WeeklyRecord).where(WeeklyRecord.student_id == sid, WeeklyRecord.week == w)).scalar_one()
        rec.classes_attended, rec.classes_scheduled = att, sch
    s.flush()
    result = score_and_store(s, wide_from_db(s, ids), None, source="attendance-upload")
    result.update({"filename": file.filename, "rows_applied": len(good), "rows_rejected": len(errors),
                   "errors": errors[:50]})
    s.add(Upload(kind="attendance", filename=file.filename or "attendance.csv", summary=result))
    s.commit()
    return result


TEMPLATE_STUDENTS = ("student_id,student_name,department,year_of_study,"
                     + ",".join(f"{f}_week{w}" for w in WEEKS for f in WEEKLY_FIELDS) + "\n")
TEMPLATE_ATTENDANCE = "student_id,week,classes_attended,classes_conducted\nS00001,1,23,24\n"


@app.get("/api/templates/{kind}")
def template(kind: Literal["students", "attendance"]):
    body = TEMPLATE_STUDENTS if kind == "students" else TEMPLATE_ATTENDANCE
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={kind}_template.csv"})


@app.get("/api/export/students.csv")
def export_students(priority: str | None = None, department: str | None = None, needs_action: bool | None = None,
                    s: Session = Depends(session_dep)):
    rows = s.execute(apply_filters(select(Student), priority, department, needs_action=needs_action)
                     .order_by(RANK, Student.score.desc())).scalars().all()
    df = pd.DataFrame([{**student_row(r)} for r in rows])
    return Response(df.to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=eduradar_students.csv"})


# ------------------------------------------------------------------ frontend (built React app)
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def root():
        return {"message": "EduRadar API is running. Build the frontend (cd frontend && npm run build) or open /docs.",
                "status": "success"}
