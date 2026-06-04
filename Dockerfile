FROM node:22-alpine AS frontend-builder

WORKDIR /app

COPY package.json package-lock.json vite.config.mjs /app/
COPY frontend-src /app/frontend-src
RUN npm ci
RUN npm run build


FROM docker:27-cli AS docker-cli

FROM python:3.12-slim AS runtime-base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8787
ENV WRAPPER_RUNTIME=docker
ENV CONTAINER_MODELS_DIR=/app/models

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY server.py /app/server.py
COPY backend /app/backend
COPY cookbook /app/cookbook
COPY --from=frontend-builder /app/frontend /app/frontend

RUN mkdir -p /app/data /app/workspace /app/models

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=3).read()"

CMD ["python", "-u", "server.py"]


FROM runtime-base AS runtime-docker-control

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker


FROM runtime-base AS runtime
