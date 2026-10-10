# EduRadar

**An early-warning platform that helps teachers spot students who may need support, before problems become dropouts.**

Built for the Code Breaker Challenge (CBC 2.0).

**Live demo:** https://eduradarhacakthon01-production-9833.up.railway.app/
**Repository:** https://github.com/Suvitfalcon/EduRadar_Hacakthon_0.1

---

## 1. Project Description

### The problem
Teachers manage large classes and rarely have time to notice which students are quietly falling behind. Attendance, marks and behaviour signals sit in separate spreadsheets, and by the time a pattern is obvious, the student has often already disengaged.

### Our solution
EduRadar brings student data together and uses a machine-learning model to estimate each student's risk level. It then turns that risk into clear, actionable next steps for the teacher.

### Key features
- **Risk dashboard:** class-wide overview of students by risk level (low / medium / high).
- **Student list and profiles:** searchable list with a detailed profile and risk drivers for each student.
- **ML risk prediction:** a scikit-learn pipeline trained on a 10,000-student dataset, with saved thresholds for risk bands.
- **Follow-ups:** track which students have been contacted and what support was suggested.
- **Support Copilot:** an assistant that suggests support actions, grounded in the guidelines in `knowledge/`.
- **CSV upload:** upload student and attendance CSVs to score new data.
- **Data quality checks:** flags missing or inconsistent data before it affects predictions.
- **Model evaluation page:** shows model metrics and test predictions transparently.
- **Teacher authentication:** login-protected access to student data.
- **Responsive, animated UI** with light and dark themes.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLAlchemy |
| Machine learning | scikit-learn, pandas, NumPy, joblib |
| Testing | pytest, httpx |
| Deployment | Docker, Railway |

---

## 3. Project Structure

```
eduradar/
├── backend/            FastAPI app (main.py, auth.py, ml.py, copilot.py, services.py, db.py, seed.py)
├── frontend/           React + Vite app (src/pages, src/ui.jsx, ...)
├── knowledge/          Support guidelines used by the Copilot
├── sample_data/        Sample CSVs for the Upload page
├── processed_data/     Cleaned data and engineered features
├── saved_model/        Trained model, metrics and risk thresholds
├── tests/              API and Copilot tests
├── preprocess.py       Data cleaning and feature engineering
├── train_model.py      Model training script
├── student_support_10000.csv   Source dataset
└── Dockerfile
```

---

## 4. Setup and Run Instructions

### Prerequisites
- Python 3.11 or newer
- Node.js 18 or newer and npm
- Git

### Step 1: Clone the repository
```bash
git clone https://github.com/Suvitfalcon/EduRadar_Hacakthon_0.1.git
cd EduRadar_Hacakthon_0.1
```

### Step 2: Install backend dependencies
```bash
pip install -r backend/requirements.txt
```

### Step 3: Install and build the frontend
```bash
cd frontend
npm ci
npm run build
cd ..
```
The build output goes to `frontend/dist` and is served by the backend.

### Step 4: Set environment variables
The app will not start without a teacher account. Set these before running:

| Variable | Description |
|---|---|
| `EDURADAR_TEACHER_USERNAME` | Login username for the teacher account |
| `EDURADAR_TEACHER_PASSWORD` | Login password, **minimum 12 characters** |

**Windows (PowerShell):**
```powershell
$env:EDURADAR_TEACHER_USERNAME = "Suvit"
$env:EDURADAR_TEACHER_PASSWORD = "EduRadar@2026!"
```

**macOS / Linux:**
```bash
export EDURADAR_TEACHER_USERNAME="Suvit"
export EDURADAR_TEACHER_PASSWORD="EduRadar@2026!"
```

See `AUTH_SETUP.md` for authentication details and `COPILOT_SETUP.md` for any optional Copilot configuration.

### Step 5: Start the app
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open http://localhost:8000 and log in with the credentials from Step 4.

### Optional: Frontend development mode
Run the backend as above, then in a second terminal:
```bash
cd frontend
npm run dev
```

### Optional: Retrain the model
```bash
python preprocess.py
python train_model.py
```
This regenerates the files in `processed_data/` and `saved_model/`.

### Run the tests
```bash
pytest
```

---

## 5. Deployment (Railway / Docker)

The repository includes a `Dockerfile`. To deploy on Railway:

1. Connect this GitHub repository to a new Railway service.
2. In the service's **Variables** tab, add `EDURADAR_TEACHER_USERNAME` 
Username:Suvit 
Password: EduRadar@2026!  
`EDURADAR_TEACHER_PASSWORD` (12+ characters).
3. In **Settings → Networking**, click **Generate Domain** and enter the port the app listens on.

---

## 6. How to Use

1. Log in with the teacher credentials.
2. Review the **Dashboard** for the class risk overview.
3. Open **Students** and click a student to see their profile and risk drivers.
4. Use **Copilot** for suggested support actions.
5. Record outcomes in **Follow-Ups**.
6. Use **Upload** with the files in `sample_data/` to score new data, and **Data Quality** to check it first.

---

## 7. Team

- **Team name:** Black Hats
- **CBC ID:** CBC042
- **Members:** Suvit,Satwik,Jahnavi,Pavanakumara

---

## 8. Notes

- The dataset is used for demonstration. Do not commit real student data or credentials to this repository.
- Credentials are supplied through environment variables only and are never stored in the code.
