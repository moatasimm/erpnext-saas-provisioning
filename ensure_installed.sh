#!/bin/bash
# ============================================================
# ensure_installed.sh — Ensure opentra_retention is pip-installed
# ============================================================
# Run this after server restart if you get "No module named 'opentra_retention'"
# Or call from supervisord / rc.local for automatic startup.
#
# Usage:
#   bash /home/frappe/frappe-bench/apps/opentra_retention/ensure_installed.sh
# ============================================================

set -e

BENCH_DIR="/home/frappe/frappe-bench"
APP_DIR="$BENCH_DIR/apps/opentra_retention"
PIP="$BENCH_DIR/env/bin/pip"

echo "==> Ensuring opentra_retention is installed in virtualenv..."

if "$PIP" show opentra_retention > /dev/null 2>&1; then
    echo "    ✅ Already installed."
else
    echo "    ⚠️  Not installed — running pip install -e ..."
    "$PIP" install -e "$APP_DIR" -q
    echo "    ✅ Installed."
fi

echo "==> Restarting bench..."
cd "$BENCH_DIR"
bench restart

echo "==> Done."
