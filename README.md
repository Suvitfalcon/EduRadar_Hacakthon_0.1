# EduRadar - AI-Based Student Dropout Risk Indicator (CBC042, Black Hats)

Implements every feature in the design-round deck:

| Deck feature | Where |
|---|---|
| Attendance tracking: upload attended/conducted, trends, separate rule alerts | `POST /api/upload/attendance`, profile "Attendance alert" card, `feature_engineering.py` |
| Explainable risk: priority + contributing factors | decision-tree path -> `ml.py`, profile "Why this priority?" |
| Trend warnings: sustained change, not one poor test | `trend_status()` (3 consecutive weeks); one low value = "Single dip" |
| Teacher review: accept/override with reason, keep original | `reviews` table; `predictions` rows are never edited |
| Support tracking: action, owner, follow-up date, compare indicators, outcome notes | `interventions` table, profile "Support tracking", `/follow-ups` |
| Missing-data checks, "Insufficient Data" | `/data-quality`, evidence rule in `feature_engineering.py` |
| CSV upload + batch processing | `POST /api/upload/students` |
| Stack: React + Tailwind, FastAPI/pandas, SQL (SQLite), scikit-learn decision tree | |
| Evaluation: alert precision, withdrawal recall, completed follow-ups; no impact claim | `/evaluation`, `GET /api/metrics` |
| Risks: no future-data leakage, separate test students, label = course withdrawal | `preprocess.py`, `train_model.py` |
| Simulated records clearly labelled; required edge cases | `SIM-E01..E08` + "Simulated" tags |

## Run (first start loads 10,000 students into SQLite, ~10 s)
```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --port 8000      # then open http://localhost:8000
```
The built frontend is in `frontend/dist`. To develop the UI: `cd frontend && npm install && npm run dev` (http://localhost:5173, proxies /api to :8000). Rebuild with `npm run build`.

## Retrain (optional)
```bash
python preprocess.py && python train_model.py
python -m backend.seed --reset
```
## Tests
`python -m pytest tests`

## Notes
* Data is synthetic; metrics are on held-out simulated test students and are not evidence of real impact.
* Priorities: Medium = F2-optimal threshold, High = F1-optimal threshold, both chosen on validation data.
* Deck rules (PPT formatting, TeamID_Domain file names) apply to the slides, not the code.
Working Project Deployed:  https://eduradarhacakthon01-production-9833.up.railway.app/
