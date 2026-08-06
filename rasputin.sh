#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENABLE_WARSAT=0
ALLOW_LAN=0
NO_OPEN=0
COMMAND="help"

for arg in "$@"; do
    normalized="$(printf '%s' "$arg" | tr '[:upper:]' '[:lower:]')"
    case "$normalized" in
        -enablewarsat|--enable-warsat)
            ENABLE_WARSAT=1
            ;;
        -lan|--lan)
            ALLOW_LAN=1
            ;;
        -noopen|--no-open)
            NO_OPEN=1
            ;;
        -h|--help|help)
            if [ "$COMMAND" = "help" ]; then COMMAND="help"; fi
            ;;
        start|stop|credentials|reset-password|logs|status|config|setup-https)
            if [ "$COMMAND" = "help" ]; then COMMAND="$normalized"; fi
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Run './rasputin.sh help' for usage." >&2
            exit 2
            ;;
    esac
done

show_header() {
    printf '\n=========================================\n'
    printf '             RASPUTIN MANAGER\n'
    printf '=========================================\n\n'
}

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$1" >&2
        exit 1
    fi
}

check_docker() {
    require_command docker
    require_command curl
    if ! docker compose version >/dev/null 2>&1; then
        echo "Docker Compose v2 is required. Install Docker Desktop or Docker Engine with the Compose plugin." >&2
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        echo "The Docker CLI is installed, but the Docker engine is not running or is not accessible." >&2
        echo "Start Docker Desktop, or start the Docker service and retry." >&2
        exit 1
    fi
}

open_browser() {
    local url="$1"
    if [ "$NO_OPEN" -eq 1 ]; then
        echo "Rasputin is ready at $url"
        return
    fi
    if command -v open >/dev/null 2>&1; then
        open "$url" >/dev/null 2>&1 || echo "Open $url in a browser."
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    else
        echo "Could not open a browser automatically. Open $url manually."
    fi
}

get_credentials() {
    echo "Looking for first-run credentials in the current container logs..."
    local logs username password
    logs="$(docker compose logs --no-color rasputin-wrapper 2>&1 || true)"
    username="$(printf '%s\n' "$logs" | sed -nE 's/.*username:[[:space:]]*([^[:space:]]+).*/\1/p' | tail -n 1)"
    password="$(printf '%s\n' "$logs" | sed -nE 's/.*password:[[:space:]]*([^[:space:]]+).*/\1/p' | tail -n 1)"

    if [ -n "$username" ] && [ -n "$password" ]; then
        printf '\nRasputin first-run credentials\n  username: %s\n  password: %s\n\n' "$username" "$password"
        echo "Change the generated password after your first login."
    else
        echo "No generated password was found in the current logs."
        echo "This is normal after the first boot log was rotated or the password was changed."
        echo "Use './rasputin.sh reset-password' if you need a new one."
    fi
}

reset_password() {
    check_docker
    echo "Resetting the admin password inside the running container..."
    docker compose exec -T rasputin-wrapper python -m backend.tools.reset_password
}

show_logs() {
    check_docker
    docker compose logs --no-color --tail "${RASPUTIN_LOG_TAIL:-120}" rasputin-wrapper
}

show_status() {
    check_docker
    docker compose ps
    local port scheme curl_args
    port="${WRAPPER_PORT:-8787}"
    scheme=http
    curl_args=(-sS -f)
    if [ -f "data/tls/rasputin.pem" ] && [ -f "data/tls/rasputin-key.pem" ]; then
        scheme=https
        curl_args+=(-k)
    fi
    if curl "${curl_args[@]}" "${scheme}://127.0.0.1:${port}/api/health" >/dev/null 2>&1; then
        echo "Health: ready (${scheme}://127.0.0.1:${port})"
    else
        echo "Health: unavailable (${scheme}://127.0.0.1:${port})"
        return 1
    fi
}

validate_config() {
    check_docker
    docker compose config --quiet
    echo "Docker Compose configuration is valid."
}

start_rasputin() {
    check_docker

    for dir in data workspace models; do
        mkdir -p "$dir"
    done

    local port scheme url
    port="${WRAPPER_PORT:-8787}"
    if [ -f "data/tls/rasputin.pem" ] && [ -f "data/tls/rasputin-key.pem" ]; then
        export RASPUTIN_HTTPS=1
        scheme=https
    else
        export RASPUTIN_HTTPS=0
        scheme=http
    fi
    if [ "$ALLOW_LAN" -eq 1 ]; then
        if [ "$scheme" != "https" ]; then
            echo "Refusing to publish plain HTTP on the LAN. Run './rasputin.sh setup-https' first." >&2
            exit 1
        fi
        export WRAPPER_BIND=0.0.0.0
    elif [ -z "${WRAPPER_BIND:-}" ]; then
        export WRAPPER_BIND=127.0.0.1
    fi
    url="$scheme://localhost:$port"

    echo "Starting Rasputin on $url"

    local compose_files=( -f docker-compose.yml )
    if [ "$ENABLE_WARSAT" -eq 1 ]; then
        echo "Enabled the opt-in WarSat Docker control layer."
        compose_files+=( -f docker-compose.docker-control.yml )
    fi
    local mounts_override="data/docker-compose.mounts.yml"
    if [ -f "$mounts_override" ]; then
        echo "Including approved folder mounts from $mounts_override"
        compose_files+=( -f "$mounts_override" )
    fi
    if ! docker compose "${compose_files[@]}" up --build -d; then
        echo "Docker could not start Rasputin. Recent service status:" >&2
        docker compose "${compose_files[@]}" ps >&2 || true
        exit 1
    fi

    echo "Waiting for Rasputin to become healthy..."
    local max_tries=30 try=0 healthy=0
    local curl_args=(-sS -f)
    if [ "$scheme" = "https" ]; then curl_args+=(-k); fi
    while [ "$try" -lt "$max_tries" ]; do
        sleep 2
        if curl "${curl_args[@]}" "$url/api/health" >/dev/null 2>&1; then
            healthy=1
            break
        fi
        printf '.'
        try=$((try + 1))
    done
    echo

    if [ "$healthy" -eq 1 ]; then
        echo "Rasputin is up and running."
        get_credentials
        open_browser "$url"
    else
        echo "Rasputin did not answer within 60 seconds. Check './rasputin.sh logs'." >&2
        exit 1
    fi
}

setup_https() {
    require_command python3
    python3 scripts/setup_https.py --output-dir data/tls
    echo "HTTPS is ready. Restart Rasputin to use it."
    echo "Install only the public rootCA.pem on trusted client devices; never copy rootCA-key.pem."
}

stop_rasputin() {
    check_docker
    echo "Stopping Rasputin..."
    docker compose down
    echo "Rasputin stopped. Named volumes were preserved."
}

show_header

case "$COMMAND" in
    start) start_rasputin ;;
    stop) stop_rasputin ;;
    credentials) check_docker; get_credentials ;;
    reset-password) reset_password ;;
    logs) show_logs ;;
    status) show_status ;;
    config) validate_config ;;
    setup-https) setup_https ;;
    help)
        cat <<'USAGE'
Usage: ./rasputin.sh <command> [options]

Commands:
  start                 Build and start the Docker server (default port 8787)
  stop                  Stop the Docker server without deleting named volumes
  status                Show container status and query /api/health
  logs                  Show recent wrapper logs (set RASPUTIN_LOG_TAIL to change the count)
  credentials           Read first-run credentials from current container logs
  reset-password        Generate a new admin password inside the running container
  config                Validate the rendered Docker Compose configuration
  setup-https           Generate a trusted local certificate with mkcert

Options:
  --no-open             Do not open a browser after a successful start
  --lan                 Publish directly to the LAN (requires setup-https first)
  --enable-warsat       Mount the Docker socket for opt-in WarSat control
  --help                Show this help

Environment:
  WRAPPER_PORT=8787     Change the host port
  WRAPPER_BIND=127.0.0.1  Change the host bind address (keep loopback by default)
USAGE
        ;;
esac
