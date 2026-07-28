#!/usr/bin/env bash
# Stop FinAlly. Removes the container, never the finally-data volume.
set -euo pipefail

CONTAINER="finally"

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped and removed container $CONTAINER"
else
  echo "Container $CONTAINER is not running"
fi

echo "Volume finally-data kept - your portfolio survives."
