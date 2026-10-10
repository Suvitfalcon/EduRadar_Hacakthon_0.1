# EduRadar responsive UI refresh

This version changes the React presentation layer only: `frontend/src/App.jsx`, `AuthGate.jsx`, `pages/Dashboard.jsx`, and `index.css`.
It keeps the original FastAPI backend, SQLite authentication, saved model, student workflows, and API client.

## Run on Windows (PowerShell)

From the extracted `eduradar` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:EDURADAR_TEACHER_USERNAME="teacher1"
$env:EDURADAR_TEACHER_PASSWORD="replace-with-a-unique-strong-password"
$env:EDURADAR_TEACHER_NAME="Demo Teacher"
$env:EDURADAR_COOKIE_SECURE="0"
$env:EDURADAR_COPILOT_ENABLED="1"
$env:EDURADAR_COPILOT_DEMO_ONLY="1"
cd frontend
npm ci
npm run build
cd ..
python -m uvicorn backend.main:app --reload
```

Visit http://127.0.0.1:8000/ and sign in with your configured credentials.

## Deployment

Deploy the Dockerfile through Railway as before, preserving `EDURADAR_DB` and its persistent volume. Commit the frontend source changes to your repository. The Docker build installs npm packages and builds the frontend; no `node_modules` directory is included in this archive.

## Notes

- Animations honor `prefers-reduced-motion`.
- On smaller viewports, navigation becomes a slide-out menu and wide student tables scroll horizontally.
- The supplied test suite was originally written for an unauthenticated API, so several older API tests now receive `401` until a test login fixture is used. This is separate from the UI changes.
- This environment could not complete the Vite build because its archived dependencies were Windows-specific and external npm downloads timed out. Verify `npm ci && npm run build` on Windows before deploying.
- Do not publish a copy of your SQLite database, credentials, or real student records to GitHub.
