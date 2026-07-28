#!/usr/bin/env bash
# Start FinAlly. Builds the image only when it is missing or --build is passed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="finally"
CONTAINER="finally"
VOLUME="finally-data"
PORT="8001"

BUILD=false
if [ "${1:-}" = "--build" ]; then
  BUILD=true
fi

if [ ! -f "$ROOT/.env" ]; then
  echo "No .env found at $ROOT/.env"
  echo "Copy .env.example to .env and add your OPENROUTER_API_KEY."
  exit 1
fi

if [ "$BUILD" = true ] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Building image $IMAGE ..."
  docker build -t "$IMAGE" "$ROOT"
fi

# Idempotent: drop any previous container, keep the data volume.
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true

docker run -d \
  --name "$CONTAINER" \
  -p "$PORT:8001" \
  -v "$VOLUME:/app/db" \
  --env-file "$ROOT/.env" \
  "$IMAGE" >/dev/null

echo "FinAlly is starting at http://localhost:$PORT"
echo "Logs:  docker logs -f $CONTAINER"
echo "Stop:  scripts/stop_mac.sh"
