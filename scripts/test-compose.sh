#!/bin/sh
set -eu

cleanup() {
  status=$?
  if ! docker compose --profile test rm -sf backend-tests frontend-tests e2e-tests; then
    printf '%s\n' "Failed to remove one or more Compose test containers." >&2
    if [ "$status" -eq 0 ]; then
      status=1
    fi
  fi
  exit "$status"
}
trap cleanup EXIT

docker compose up -d --build backend frontend
docker compose --profile test run --build --rm backend-tests

docker compose restart backend
docker compose --profile test run --build --rm \
  -e CHECK_AFTER_BACKEND_RESTART=1 \
  backend-tests \
  pytest tests/integration/test_compose_network.py::test_backend_restart_drops_in_memory_history_when_requested -q

docker compose --profile test run --build --rm frontend-tests
docker compose --profile test run --build --rm e2e-tests
