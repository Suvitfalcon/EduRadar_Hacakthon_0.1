import io
from datetime import date, timedelta

import numpy as np
import pandas as pd

from backend.feature_engineering import clean_wide, process_wide, trend_status


# ---------------------------------------------------------- feature logic
def row(**kw):
    base = {"student_id": "X"}
    for w in range(1, 5):
        base.update({f"classes_scheduled_week{w}": 20, f"classes_attended_week{w}": 18,
                     f"assessment_score_week{w}": 70, f"assignments_due_week{w}": 2,
                     f"assignments_submitted_week{w}": 2, f"engagement_score_week{w}": 70,
                     f"active_learning_days_week{w}": 5})
    base.update(kw)
    return pd.DataFrame([base])


def test_invalid_values_become_missing_not_zero():
    clean, issues = clean_wide(row(classes_attended_week2=25, assessment_score_week3=140, active_learning_days_week1=9))
    assert np.isnan(clean.at[0, "classes_attended_week2"])
    assert np.isnan(clean.at[0, "assessment_score_week3"])
    assert np.isnan(clean.at[0, "active_learning_days_week1"])
    assert len(issues[0]) == 3


def test_zero_assignments_due_is_not_applicable():
    clean, _ = clean_wide(row(assignments_due_week1=0, assignments_submitted_week1=0))
    assert np.isnan(clean.at[0, "assignment_completion_week1"])


def test_one_poor_test_is_not_a_trend():
    assert trend_status([82, 80, 35, 81], 10)["status"] == "isolated_dip"
    assert trend_status([80, 70, 60, 48], 10)["status"] == "sustained_decline"
    assert trend_status([80, None, None, 60], 10)["status"] == "insufficient"


def test_insufficient_data_rule():
    cols = {f"{f}_week{w}": np.nan for w in range(1, 5)
            for f in ("classes_scheduled", "classes_attended", "assessment_score", "assignments_due",
                      "assignments_submitted", "engagement_score", "active_learning_days")}
    _, feats, _, q = process_wide(row(**cols))
    assert feats.at[0, "insufficient_data"] == 1 and q[0]["incomplete"]


def test_attendance_alert_is_rule_based():
    _, feats, _, _ = process_wide(row(classes_attended_week1=18, classes_attended_week2=15,
                                      classes_attended_week3=11, classes_attended_week4=8))
    assert feats.at[0, "attendance_alert"] == "Low and declining"


# ------------------------------------------------------------------ API
def first(client, **params):
    r = client.get("/api/students", params={"page_size": 5, **params}).json()
    assert r["items"], params
    return r["items"][0]


def test_summary_and_list(client):
    s = client.get("/api/summary").json()
    assert s["total_students"] >= 400
    assert set(s["by_priority"]) == {"High", "Medium", "Low", "Insufficient Data"}
    assert client.get("/api/students", params={"priority": "High"}).json()["total"] > 0


def test_edge_cases_present_and_labelled(client):
    r = client.get("/api/students", params={"source": "simulated-edge-case"}).json()
    assert r["total"] == 8
    prof = client.get("/api/students/SIM-E01").json()
    assert prof["prediction"]["priority"] == "Insufficient Data" and prof["prediction"]["score"] is None
    assert client.get("/api/students/SIM-E02").json()["trends"]["indicators"]["assessment"]["status"] == "isolated_dip"
    assert client.get("/api/students/SIM-E03").json()["student"]["trend_warning"] is True


def test_profile_has_explanation(client):
    sid = first(client, priority="High")["student_id"]
    p = client.get(f"/api/students/{sid}").json()
    assert p["prediction"]["factors"] and p["prediction"]["factors"][0]["label"]
    assert len(p["weeks"]) == 4


def test_override_requires_reason_and_preserves_original(client):
    sid = first(client, priority="High")["student_id"]
    base = {"decision": "override", "final_priority": "Low", "reviewer": "Dr. T"}
    assert client.post(f"/api/students/{sid}/review", json=base).status_code == 422
    assert client.post(f"/api/students/{sid}/review", json={**base, "reason": "Family issue resolved"}).status_code == 201
    p = client.get(f"/api/students/{sid}").json()
    assert p["student"]["priority"] == "Low" and p["student"]["overridden"]
    assert p["prediction"]["priority"] == "High"              # original model result untouched
    assert p["current_review"]["original_priority"] == "High"
    # overriding to the model's own priority is refused (use Accept); a later valid override is allowed
    assert client.post(f"/api/students/{sid}/review", json={"decision": "override", "final_priority": "High",
                                                            "reason": "same as model", "reviewer": "x"}).status_code == 422
    assert client.post(f"/api/students/{sid}/review", json={"decision": "override", "final_priority": "Medium",
                                                            "reason": "second look", "reviewer": "x"}).status_code == 201
    assert len(client.get(f"/api/students/{sid}").json()["reviews"]) == 2


def test_accept_and_insufficient(client):
    sid = first(client, priority="Medium")["student_id"]
    assert client.post(f"/api/students/{sid}/review", json={"decision": "accept", "reviewer": "Dr. T"}).status_code == 201
    assert client.post("/api/students/SIM-E01/review", json={"decision": "accept", "reviewer": "Dr. T"}).status_code == 422


def test_intervention_lifecycle_and_compare(client):
    sid = first(client, priority="High", needs_action="true")["student_id"]
    body = {"type": "Mentoring", "action": "Weekly mentor check-in", "owner": "Prof. Rao",
            "followup_date": (date.today() + timedelta(days=14)).isoformat()}
    assert client.post(f"/api/students/{sid}/interventions", json={**body, "followup_date": "2000-01-01"}).status_code == 422
    iv = client.post(f"/api/students/{sid}/interventions", json=body).json()
    assert iv["status"] == "Planned" and iv["baseline"] is not None
    url = f"/api/interventions/{iv['id']}"
    assert client.patch(url, json={"status": "Completed"}).status_code == 422          # needs notes + indicators
    done = client.patch(url, json={"status": "Completed", "outcome_notes": "Attendance improved",
                                   "followup": {"attendance_pct": 90, "engagement_score": 70}}).json()
    assert done["status"] == "Completed" and done["completed_at"] and "attendance_pct" in done["deltas"]
    assert client.patch(url, json={"status": "Planned"}).status_code == 409
    assert client.get("/api/interventions", params={"status": "Completed"}).json()["total"] > 0


def test_upload_students_and_missing_data(client):
    cols = "student_id,student_name,department,year_of_study,classes_attended_week1,classes_scheduled_week1,classes_attended_week2,classes_scheduled_week2,future_withdrawal_by_week16\n"
    csv = cols + "U001,Upload One,Civil,2,10,20,8,20,1\nU001,Upload One,Civil,2,18,20,17,20,1\nU002,Upload Two,Civil,1,20,20,20,20,0\n,,,,,,,,\n"
    r = client.post("/api/upload/students", files={"file": ("s.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["students"] == 2 and j["created"] == 2 and j["incomplete_records"] == 2
    assert "future_withdrawal_by_week16" in j["ignored_columns"]
    assert client.get("/api/students/U001").json()["student"]["priority"] == "Insufficient Data"
    assert client.post("/api/upload/students", files={"file": ("s.csv", "name\nx\n", "text/csv")}).status_code == 422
    assert client.post("/api/upload/students", files={"file": ("s.csv", "", "text/csv")}).status_code == 422


def test_upload_attendance_rescoring(client):
    before = client.get("/api/students/U002").json()
    csv = "student_id,week,classes_attended,classes_conducted\nU002,3,5,20\nU002,4,25,20\nNOPE,1,1,2\nU002,9,1,2\n"
    r = client.post("/api/upload/attendance", files={"file": ("a.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["rows_applied"] == 1 and j["rows_rejected"] == 3
    after = client.get("/api/students/U002").json()
    assert after["weeks"][2]["classes_attended"] == 5
    assert len(after["history"]) == len(before["history"]) + 1       # old result kept, new appended


def test_data_quality_and_metrics(client):
    dq = client.get("/api/data-quality").json()
    assert dq["total"] > 0 and dq["common_gaps"]
    m = client.get("/api/metrics").json()
    assert m["evaluation_set"]["students"] > 0 and m["completed_followups"]["total"] > 0
    assert "risks" in m
