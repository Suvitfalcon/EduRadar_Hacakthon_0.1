def test_copilot_disabled_by_default(client):
    result = client.post("/api/copilot/ask", json={"question": "low attendance"})
    assert result.status_code == 503


def test_copilot_guideline_and_students(client, monkeypatch):
    monkeypatch.setenv("EDURADAR_COPILOT_ENABLED", "1")
    guide = client.post("/api/copilot/ask", json={"question": "What should we do about missed assignments?"})
    assert guide.status_code == 200
    assert guide.json()["sources"]
    students = client.post("/api/copilot/ask", json={"question": "Which students have declining attendance?"})
    assert students.status_code == 200
    assert students.json()["intent"] == "student_search"
    assert len(students.json()["records"]) <= 20


def test_copilot_question_length(client, monkeypatch):
    monkeypatch.setenv("EDURADAR_COPILOT_ENABLED", "1")
    assert client.post("/api/copilot/ask", json={"question": "x"}).status_code == 422
