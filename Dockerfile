# syntax=docker/dockerfile:1

# ---- Stage 1: build the Tailwind CSS bundle ----
FROM node:24-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY templates/ /app/templates/
RUN npm run build:css

# ---- Stage 2: the Django app itself ----
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend-build /app/static/css/tailwind.css ./static/css/tailwind.css

# No .env is present at build time (it's runtime-only, mounted via
# docker-compose env_file) — base.py's SECRET_KEY/DB defaults are enough
# for collectstatic, which doesn't need real secrets or a live database.
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
