#!/bin/bash
set -e

########################################################################
# run.sh — Start all Marketing Assistant services for local dev
########################################################################

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

# ── Colours for status messages ──────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Colour

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Cleanup on exit ─────────────────────────────────────────────────
cleanup() {
    echo ""
    warn "Caught signal — shutting down all services..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    info "Stopping MongoDB container..."
    "$PROJECT_ROOT/mongodb/stop.sh"
    info "All services stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

# ── Helper: start a Python service in the background ────────────────
start_python_service() {
    local name="$1"
    local port="$2"
    local dir="$PROJECT_ROOT/$name"

    if [ ! -d "$dir" ]; then
        error "Directory $dir does not exist — skipping $name"
        return
    fi

    info "Starting $name (port $port)..."
    (cd "$dir" && uv run python -m app) &
    PIDS+=($!)
}

# ══════════════════════════════════════════════════════════════════════
# 1. Infrastructure — MongoDB
# ══════════════════════════════════════════════════════════════════════
info "Starting MongoDB (port 27017)..."
"$PROJECT_ROOT/mongodb/run.sh"
sleep 3
info "MongoDB is up."

# ══════════════════════════════════════════════════════════════════════
# 2. Core services — Event Hub + Config Service
# ══════════════════════════════════════════════════════════════════════
start_python_service "event-hub" 8080
start_python_service "config-service" 8081
sleep 2

# ══════════════════════════════════════════════════════════════════════
# 3. MCP tool servers
# ══════════════════════════════════════════════════════════════════════
start_python_service "mongodb-mcp"          8082
start_python_service "imagegen-mcp"         8083
start_python_service "customer-analyst"     8084
sleep 2

# ══════════════════════════════════════════════════════════════════════
# 4. Agent services
# ══════════════════════════════════════════════════════════════════════
start_python_service "policy-guardian"      8085
start_python_service "creative-producer"    8086
start_python_service "delivery-manager"     8087
sleep 2

# ══════════════════════════════════════════════════════════════════════
# 5. Orchestrator — Campaign Director
# ══════════════════════════════════════════════════════════════════════
start_python_service "campaign-director" 8088
sleep 2

# ══════════════════════════════════════════════════════════════════════
# 6. API gateway
# ══════════════════════════════════════════════════════════════════════
start_python_service "campaign-api" 8089
sleep 2

# ══════════════════════════════════════════════════════════════════════
# 7. Frontend (Node.js)
# ══════════════════════════════════════════════════════════════════════
if [ -d "$PROJECT_ROOT/frontend" ]; then
    info "Installing frontend dependencies..."
    (cd "$PROJECT_ROOT/frontend" && npm install)
    info "Starting frontend (port 3000)..."
    (cd "$PROJECT_ROOT/frontend" && npm start) &
    PIDS+=($!)
else
    warn "frontend/ directory not found — skipping frontend."
fi

# ══════════════════════════════════════════════════════════════════════
# Ready
# ══════════════════════════════════════════════════════════════════════
echo ""
info "============================================"
info " All services are starting up!"
info "============================================"
info ""
info " MongoDB          :  localhost:27017"
info " Event Hub        :  localhost:8080"
info " Config Service   :  localhost:8081"
info " MongoDB MCP      :  localhost:8082"
info " ImageGen MCP     :  localhost:8083"
info " Customer Analyst :  localhost:8084"
info " Policy Guardian  :  localhost:8085"
info " Creative Producer:  localhost:8086"
info " Delivery Manager :  localhost:8087"
info " Campaign Director:  localhost:8088"
info " Campaign API     :  localhost:8089"
info " Frontend         :  localhost:3000"
info ""
info " Press Ctrl+C to stop all services."
info "============================================"
echo ""

# Wait for all background processes
wait
