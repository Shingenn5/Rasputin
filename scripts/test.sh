#!/usr/bin/env sh
set -eu

port="${RASPUTIN_TEST_PORT:-8877}"
baseUrl="http://127.0.0.1:${port}"
export RASPUTIN_TEST_PORT="$port"

cleanup() {
  if [ "${RASPUTIN_KEEP_RUNNING:-0}" != "1" ]; then
    docker compose -f docker-compose.test.yml down
  fi
}

trap cleanup EXIT

if [ "${RASPUTIN_RUN_UI:-0}" = "1" ]; then
  npm run build
fi

if [ "${RASPUTIN_SKIP_BUILD:-0}" = "1" ]; then
  docker compose -f docker-compose.test.yml up -d
else
  docker compose -f docker-compose.test.yml up -d --build
fi

ready=0
i=0
while [ "$i" -lt 45 ]; do
  if python - "$baseUrl" <<'PY'
import json
import sys
import urllib.request

baseUrl = sys.argv[1]
try:
    data = json.loads(urllib.request.urlopen(baseUrl + "/api/health", timeout=3).read().decode("utf-8"))
    sys.exit(0 if data.get("ok") else 1)
except Exception:
    sys.exit(1)
PY
  then
    ready=1
    break
  fi
  i=$((i + 1))
  sleep 1
done

if [ "$ready" != "1" ]; then
  docker compose -f docker-compose.test.yml logs --tail 120 rasputin-wrapper-test
  echo "Rasputin test container did not become healthy at ${baseUrl}" >&2
  exit 1
fi

docker compose -f docker-compose.test.yml exec -T rasputin-wrapper-test python -m unittest tests.testBackendSmoke
docker compose -f docker-compose.test.yml exec -T rasputin-wrapper-test python /app/tests/liveSmoke.py

if [ "${RASPUTIN_RUN_UI:-0}" = "1" ]; then
  RASPUTIN_TEST_BASE_URL="$baseUrl" npm run testUi
fi

echo "Rasputin test harness passed at ${baseUrl}"
