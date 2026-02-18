#!/usr/bin/env bash
# ============================================================
#  TBB Platform - Automated Setup & Start
#  Detects host hardware, configures memory limits, and starts
#  all services automatically.
#
#  Usage:
#    ./start.sh              # Auto: 70% of total RAM
#    ./start.sh 8g           # Fixed: 8 GB RAM
#    ./start.sh 60%          # Percentage: 60% of total RAM
#    ./start.sh --build      # Force rebuild images
# ============================================================

set -e

cd "$(dirname "$0")"

RAM=""
BUILD_FLAG=""

for arg in "$@"; do
    case "$arg" in
        --build) BUILD_FLAG="--build" ;;
        *)       RAM="$arg" ;;
    esac
done

# ---- 1. Environment file ----
if [ ! -f .env ]; then
    echo "[1/4] Creating .env from .env.example..."
    cp .env.example .env
else
    echo "[1/4] .env already exists, skipping."
fi

# ---- 2. Install script dependencies ----
echo "[2/4] Checking Python dependencies..."
if python3 -c "import psutil, ruamel.yaml" 2>/dev/null; then
    echo "  Dependencies already installed."
else
    echo "  Installing psutil and ruamel.yaml..."
    pip3 install -q -r scripts/requirements.txt
fi

# ---- 3. Configure memory limits ----
echo "[3/4] Configuring memory limits..."
if [ -n "$RAM" ]; then
    python3 scripts/configure_resources.py --ram "$RAM"
else
    # Default: 70% of total RAM (server-oriented)
    python3 scripts/configure_resources.py --ram 70%
fi

# ---- 4. Start services ----
echo "[4/4] Starting Docker services..."
docker compose up -d $BUILD_FLAG

echo ""
echo "============================================"
echo "  TBB Platform is starting!"
echo "============================================"
echo ""
echo "  Frontend  : http://localhost:3000"
echo "  API Docs  : http://localhost:8000/docs"
echo "  Airflow   : http://localhost:8080"
echo ""
echo "  Logs: docker compose logs -f fastapi"
echo "============================================"
