# ---------- stage 1: frontend build ----------
FROM node:20-alpine AS web
WORKDIR /web
# Dependencies are pinned to exact versions in package.json, so npm install is reproducible.
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- stage 2: runtime ----------
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=web /web/dist ./static

RUN useradd --create-home arena && chown -R arena:arena /app
USER arena

EXPOSE 8000
ENV ARENA_STATIC_DIR=/app/static

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
