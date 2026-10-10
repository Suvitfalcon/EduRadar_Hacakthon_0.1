# EduRadar Mark4 teacher login integration

## What changed
- SQLite `teachers` and `teacher_sessions` tables (automatic via SQLAlchemy `create_all`).
- Passwords stored as salted PBKDF2-SHA256 hashes, not plaintext.
- Random opaque HttpOnly session cookie; 12-hour sessions; logout revokes DB session.
- CSRF token required for all protected POST/PATCH/DELETE requests.
- Server middleware protects **all** `/api/*` endpoints (except `/api/health`, `/api/auth/login`, `/api/auth/me`), including Copilot and CSV downloads/uploads.
- React login screen; reviewer ID is taken from the session on new reviews.

## Local testing (PowerShell, project root)
```powershell
$env:EDURADAR_TEACHER_USERNAME="teacher1"
$env:EDURADAR_TEACHER_PASSWORD="Use-A-Unique-Long-Password-Here"
$env:EDURADAR_TEACHER_NAME="Demo Teacher"
$env:EDURADAR_COOKIE_SECURE="0"
python -m uvicorn backend.main:app --reload
```

In another shell: `cd frontend; npm ci; npm run build` (build before starting API if using FastAPI-served React).
Open http://127.0.0.1:8000, sign in. Before login `/api/students` must return 401; after login the dashboard should load. Logout must lock the dashboard again. Existing `pytest` tests that call APIs anonymously need an authenticated test client.

## Railway deployment
Set Railway service variables `EDURADAR_TEACHER_USERNAME`, `EDURADAR_TEACHER_PASSWORD`, `EDURADAR_TEACHER_NAME`, and `EDURADAR_COOKIE_SECURE=1`. Use strong unique password and HTTPS. Keep `EDURADAR_DB` pointed to mounted persistent storage, e.g. `/data/eduradar.db`. Git push triggers rebuild. DO NOT commit passwords to git or paste them into chat.

## Notes
- Initial teacher is provisioned **only once** on first startup. Changing the env password later does not automatically rotate an existing account password.
- For multiple teachers, add an admin-only provisioning tool; do not publish a public signup page.
- The login rate limit is per process and a minimal demo safeguard; use gateway/WAF limits for public high-volume use.
- The browser still downloads static HTML and assets before login. Sensitive data remains protected by the API. Never embed sensitive data in the React build.
- The Mark4 ZIP contains local `.db`, `.db-wal`, `.db-shm` files. Never commit or publish these. The ZIP provided here is a source patch and does not include them.
