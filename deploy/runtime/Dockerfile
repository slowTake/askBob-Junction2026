# The whole app in one container for Aiven Runtime (D-034): nginx serves the UI on :8080
# and proxies /api to the API on 127.0.0.1:8000; the ingest worker runs beside them.
# Build from the repo root: docker build -f deploy/runtime/Dockerfile .
# No vision service (ingest uses pixel heuristics), and /data is the container's own
# disk, so a redeploy or restart loses uploaded files.

FROM node:22-alpine AS ui
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
# Same OCR and fonts as backend/Dockerfile, plus nginx and procps (pkill, for tests).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fin tesseract-ocr-swe \
    fonts-dejavu-core nginx procps \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" DATA_DIR=/data

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY --from=ui /app/dist /srv/ui
COPY deploy/runtime/nginx.conf /etc/nginx/nginx.conf
COPY --chmod=755 deploy/runtime/start.sh /usr/local/bin/start.sh

RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app
EXPOSE 8080
CMD ["start.sh"]
