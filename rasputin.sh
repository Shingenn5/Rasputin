#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

ENABLE_WARSAT=0
ALLOW_LAN=0
COMMAND="help"

for arg in "$@"; do
    if [ "$arg" == "-EnableWarSat" ]; then
        ENABLE_WARSAT=1
    elif [ "$arg" == "-Lan" ] || [ "$arg" == "--lan" ]; then
        ALLOW_LAN=1
    elif [ "$COMMAND" == "help" ]; then
        COMMAND="$arg"
    fi
done

show_header() {
    echo ""
    echo -e "\033[0;36m=========================================\033[0m"
    echo -e "\033[0;36m           🛡️ RASPUTIN MANAGER          \033[0m"
    echo -e "\033[0;36m=========================================\033[0m"
    echo ""
}

check_docker() {
    if ! docker compose version >/dev/null 2>&1; then
        echo -e "\033[0;31m❌ Docker is not running or not installed.\033[0m"
        echo -e "\033[0;33mRasputin requires Docker Desktop to run its sandboxes.\033[0m"
        echo -e "\033[0;33mPlease install Docker Desktop from: https://www.docker.com/products/docker-desktop/\033[0m"
        echo -e "\033[0;33mOnce installed and running, run this script again.\033[0m"
        exit 1
    fi
}

open_browser() {
    local url=$1
    echo -e "\033[0;36mOpening $url in your default browser...\033[0m"
    if command -v open >/dev/null 2>&1; then
        open "$url"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" &>/dev/null &
    else
        echo -e "\033[0;33mCould not open browser automatically. Please navigate to $url\033[0m"
    fi
}

get_credentials() {
    echo -e "\033[0;36mFetching credentials from logs...\033[0m"
    
    USERNAME=$(docker compose logs rasputin-wrapper 2>&1 | grep "username:" | awk '{print $NF}' | tail -n 1)
    PASSWORD=$(docker compose logs rasputin-wrapper 2>&1 | grep "password:" | awk '{print $NF}' | tail -n 1)
    
    if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
        echo ""
        echo -e "\033[0;32m=========================================\033[0m"
        echo -e "\033[0;32m         RASPUTIN CREDENTIALS            \033[0m"
        echo -e "\033[0;32m=========================================\033[0m"
        echo -e " \033[0;32mUsername:\033[0m \033[0;33m$USERNAME\033[0m"
        echo -e " \033[0;32mPassword:\033[0m \033[0;33m$PASSWORD\033[0m"
        echo -e "\033[0;32m=========================================\033[0m"
        echo -e "\033[0;90mChange this password after your first login!\033[0m"
        echo ""
    else
        echo -e "\033[0;90mStill waiting for credentials to be generated... (Check 'docker compose logs' if this persists)\033[0m"
    fi
}

start_rasputin() {
    check_docker

    for dir in data workspace models; do
        mkdir -p "$dir"
    done

    PORT="${WRAPPER_PORT:-8787}"
    if [ -f "data/tls/rasputin.pem" ] && [ -f "data/tls/rasputin-key.pem" ]; then
        export RASPUTIN_HTTPS=1
        SCHEME=https
    else
        export RASPUTIN_HTTPS=0
        SCHEME=http
    fi
    if [ "$ALLOW_LAN" -eq 1 ]; then
        export WRAPPER_BIND=0.0.0.0
    fi
    URL="$SCHEME://localhost:$PORT"

    echo -e "\033[0;36mStarting Rasputin on $URL\033[0m"

    COMPOSE_FILES=(-f docker-compose.yml)
    if [ "$ENABLE_WARSAT" -eq 1 ]; then
        echo -e "\033[0;35mEnabled WarSat Docker Control Layer...\033[0m"
        COMPOSE_FILES+=(-f docker-compose.docker-control.yml)
    fi
    # Approving a local folder from the Workspaces tab writes this file with
    # the new bind mount; including it here means picking it up is just a
    # normal restart, no manual editing of any compose file.
    MOUNTS_OVERRIDE="data/docker-compose.mounts.yml"
    if [ -f "$MOUNTS_OVERRIDE" ]; then
        echo -e "\033[0;36mIncluding approved folder mounts from $MOUNTS_OVERRIDE\033[0m"
        COMPOSE_FILES+=(-f "$MOUNTS_OVERRIDE")
    fi
    docker compose "${COMPOSE_FILES[@]}" up --build -d

    echo -e "\033[0;36mWaiting for Rasputin to become healthy...\033[0m"
    
    MAX_TRIES=30
    TRY=0
    HEALTHY=0
    while [ $TRY -lt $MAX_TRIES ]; do
        sleep 2
        if curl -s -f "$URL/api/health" > /dev/null; then
            HEALTHY=1
            break
        else
            echo -n "."
        fi
        TRY=$((TRY+1))
    done
    echo ""

    if [ "$HEALTHY" -eq 1 ]; then
        echo -e "\033[0;32mRasputin is UP and RUNNING!\033[0m"
        get_credentials
        open_browser "$URL"
    else
        echo -e "\033[0;33mRasputin took too long to respond. It might still be starting up.\033[0m"
        echo -e "\033[0;33mRun './rasputin.sh credentials' in a few moments.\033[0m"
    fi
}

setup_https() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Python 3 is required to run the HTTPS setup helper."
        exit 1
    fi
    python3 scripts/setup_https.py --output-dir data/tls
    echo "HTTPS is ready. Restart Rasputin to use it."
    echo "Install rootCA.pem on other LAN devices; never copy rootCA-key.pem."
}

stop_rasputin() {
    check_docker
    echo -e "\033[0;36mStopping Rasputin...\033[0m"
    docker compose down
    echo -e "\033[0;32mRasputin stopped.\033[0m"
}

show_header

case "$(echo "$COMMAND" | tr '[:upper:]' '[:lower:]')" in
    start)
        start_rasputin
        ;;
    stop)
        stop_rasputin
        ;;
    credentials)
        check_docker
        get_credentials
        ;;
    setup-https)
        setup_https
        ;;
    *)
        echo -e "\033[0;36mUsage:\033[0m"
        echo "  ./rasputin.sh start             - Starts Rasputin in the background"
        echo "  ./rasputin.sh start -EnableWarSat - Starts Rasputin with Docker Control layer"
        echo "  ./rasputin.sh stop              - Stops all Rasputin containers"
        echo "  ./rasputin.sh credentials       - Fetches your login credentials"
        echo "  ./rasputin.sh setup-https       - Creates a trusted local certificate with mkcert"
        echo "  ./rasputin.sh start --lan       - Publishes Docker mode on the LAN (use HTTPS)"
        echo ""
        ;;
esac
