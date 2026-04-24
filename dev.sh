#!/usr/bin/env bash
set -e

cleanup() {
    kill $(jobs -p) 2>/dev/null
}
trap cleanup EXIT

echo "Starting backend & frontend..."
uv run uvicorn backend.main:app --reload --port 8000 &
(cd frontend && npm run dev) &
wait
