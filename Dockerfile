# Stage 1: Build React frontend
FROM node:20-slim AS frontend

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: Python backend
FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/requirements.txt

COPY backend/ /app/backend/
COPY saved_model/ /app/saved_model/
COPY knowledge/ /app/knowledge/
COPY student_support_10000.csv /app/
COPY --from=frontend /app/frontend/dist /app/frontend/dist

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]