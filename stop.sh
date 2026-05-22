#!/bin/bash
set -e

########################################################################
# stop.sh — Stop all Marketing Assistant services
########################################################################

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

SERVICES=(
    "event-hub:8080"
    "config-service:8081"
    "mongodb-mcp:8082"
    "imagegen-mcp:8083"
    "customer-analyst:8084"
    "policy-guardian:8085"
    "creative-producer:8086"
    "delivery-manager:8087"
    "campaign-director:8088"
    "campaign-api:8089"
)

info "Stopping all services..."

for entry in "${SERVICES[@]}"; do
    port="${entry##*:}"
    name="${entry%%:*}"
    pid=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill $pid 2>/dev/null || true
        info "Stopped $name (port $port, pid $pid)"
    fi
done

# Stop frontend (port 3000)
pid=$(lsof -ti :3000 2>/dev/null || true)
if [ -n "$pid" ]; then
    kill $pid 2>/dev/null || true
    info "Stopped frontend (port 3000, pid $pid)"
fi

# Stop MongoDB
"$PROJECT_ROOT/mongodb/stop.sh"

info "All services stopped."
