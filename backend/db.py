"""SQL layer (SQLite via SQLAlchemy 2.0).

Design rule from the deck: *preserve the original model result*.  The
``predictions`` table is append-only; teacher decisions live in ``reviews``.
"""
from __future__ import annotations

import os
from datetime import datetime, date, timezone


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from pathlib import Path

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String,
                        Text, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

DB_PATH = Path(os.environ.get("EDURADAR_DB", Path(__file__).resolve().parent / "data" / "eduradar.db"))


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"
    student_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    department: Mapped[str] = mapped_column(String(80), index=True, default="Unknown")
    year_of_study: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_source: Mapped[str] = mapped_column(String(40), default="synthetic")  # synthetic / simulated-edge-case / upload
    split: Mapped[str] = mapped_column(String(16), default="upload")          # train / validation / test / upload
    actual_withdrawal: Mapped[int | None] = mapped_column(Integer, nullable=True)  # simulated label (evaluation only)
    # denormalised for fast filtering / sorting
    model_priority: Mapped[str | None] = mapped_column(String(24), index=True)
    effective_priority: Mapped[str | None] = mapped_column(String(24), index=True)
    score: Mapped[float | None] = mapped_column(Float, index=True)
    attendance_alert: Mapped[str | None] = mapped_column(String(40), index=True)
    trend_warning: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    incomplete: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    weekly: Mapped[list["WeeklyRecord"]] = relationship(cascade="all, delete-orphan", order_by="WeeklyRecord.week")


class WeeklyRecord(Base):
    __tablename__ = "weekly_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    week: Mapped[int] = mapped_column(Integer)
    classes_scheduled: Mapped[float | None] = mapped_column(Float)
    classes_attended: Mapped[float | None] = mapped_column(Float)
    assessment_score: Mapped[float | None] = mapped_column(Float)
    assignments_due: Mapped[float | None] = mapped_column(Float)
    assignments_submitted: Mapped[float | None] = mapped_column(Float)
    engagement_score: Mapped[float | None] = mapped_column(Float)
    active_learning_days: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (Index("ix_weekly_student_week", "student_id", "week", unique=True),)


class Prediction(Base):
    """Immutable model output.  Never updated after insert."""
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    model_version: Mapped[str] = mapped_column(String(40))
    score: Mapped[float | None] = mapped_column(Float)
    priority: Mapped[str] = mapped_column(String(24))
    insufficient_data: Mapped[bool] = mapped_column(Boolean, default=False)
    attendance_alert: Mapped[str] = mapped_column(String(40))
    factors: Mapped[list] = mapped_column(JSON)
    trends: Mapped[dict] = mapped_column(JSON)
    quality: Mapped[dict] = mapped_column(JSON)
    features: Mapped[dict] = mapped_column(JSON)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # only flag changes; result is immutable
    source: Mapped[str] = mapped_column(String(40), default="seed")


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"))
    decision: Mapped[str] = mapped_column(String(16))          # accept / override
    original_priority: Mapped[str] = mapped_column(String(24))
    final_priority: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Intervention(Base):
    __tablename__ = "interventions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(80))
    followup_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="Planned", index=True)  # Planned / In progress / Completed / Cancelled
    baseline: Mapped[dict | None] = mapped_column(JSON)    # indicators when the plan was created
    followup: Mapped[dict | None] = mapped_column(JSON)    # indicators recorded at follow-up
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="teacher")  # teacher / simulated
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TeacherSession(Base):
    __tablename__ = "teacher_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    summary: Mapped[dict] = mapped_column(JSON)


_engine = None
_Session = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def _pragmas(conn, _):  # noqa: ANN001
            cur = conn.cursor()                                            
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        _Session = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def get_session():
    get_engine()
    return _Session()


def session_dep():
    s = get_session()
    try:
        yield s
    finally:
        s.close()
