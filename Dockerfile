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

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY server.py /app/server.py
COPY backend /app/backend
COPY --from=frontend-builder /app/frontend /app/frontend

RUN mkdir -p /app/data /app/workspace /app/models

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import os,ssl,urllib.request; s='https' if os.getenv('RASPUTIN_HTTPS','0').lower() in ('1','true','yes','on') else 'http'; urllib.request.urlopen(s+'://127.0.0.1:8787/api/health', timeout=3, context=ssl._create_unverified_context() if s == 'https' else None).read()"

CMD ["python", "-u", "server.py"]


FROM runtime-base AS runtime-docker-control

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker


FROM runtime-base AS runtime
