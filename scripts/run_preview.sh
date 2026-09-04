#!/usr/bin/env bash
# Serve built module dist from the API process (no vite preview).
# Default: no rebuild. Pass --build / BUILD=1 to compile first.
# Usage: scripts/run_preview.sh [--build] [base] [wiki] [sale] ...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${MODOOR_WEB_HOST:-127.0.0.1}"
PORT="${MODOOR_WEB_PORT:-8765}"
DO_BUILD=0
MODULES=()

default_modules() {
  local m
  for m in base wiki sale skill; do
    if [[ -d "${ROOT}/modules/${m}/webui" ]]; then
      echo "${m}"
    fi
  done
}

free_port() {
  local p="$1"
  [[ -z "${p}" ]] && return 0
  local pids
  pids="$(lsof -nP -iTCP:"${p}" -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo ">> freeing :${p} (pids: ${pids})"
    # shellcheck disable=SC2086
    kill ${pids} 2>/dev/null || true
    sleep 0.3
  fi
}

for arg in "$@"; do
  case "${arg}" in
    --build|-b) DO_BUILD=1 ;;
    *) MODULES+=("${arg}") ;;
  esac
done

if [[ "${BUILD:-0}" == "1" ]]; then
  DO_BUILD=1
fi

if [[ ${#MODULES[@]} -eq 0 ]]; then
  # shellcheck disable=SC2207
  MODULES=($(default_modules))
fi

if [[ ${#MODULES[@]} -eq 0 ]]; then
  echo "!! no module webui found under modules/*/webui" >&2
  exit 1
fi

if [[ "${DO_BUILD}" == "1" ]]; then
  chmod +x "${ROOT}/scripts/run_build.sh"
  "${ROOT}/scripts/run_build.sh" "${MODULES[@]}"
fi

for name in "${MODULES[@]}"; do
  dist="${ROOT}/modules/${name}/webui/dist"
  if [[ ! -d "${dist}" || ! -f "${dist}/index.html" ]]; then
    echo "!! missing dist for ${name}: ${dist}" >&2
    echo "   run: make build ${name}" >&2
    echo "   or:  make preview BUILD=1 ${name}" >&2
    exit 1
  fi
done

set -a
# shellcheck disable=SC1091
source .env
set +a

# API serves dist itself — do not reverse-proxy vite preview.
unset MODOOR_WEBUI_PROXIES || true
export MODOOR_WEBUI_PROXIES=""
export MODOOR_WEBUI_STATIC_MODULES="$(IFS=,; echo "${MODULES[*]}")"
export MODOOR_WEBUI_URL="http://${HOST}:${PORT}"

echo ""
echo "API / login  http://${HOST}:${PORT}/login"
echo "mode         preview (API mounts dist, no vite)"
for mid in "${MODULES[@]:-}"; do
  [[ -z "${mid}" ]] && continue
  printf "  /web/%-6s → modules/%s/webui/dist\n" "${mid}" "${mid}"
done
echo "static       ${MODOOR_WEBUI_STATIC_MODULES}"
echo ""

free_port "${PORT}"
exec "${ROOT}/.venv/bin/python" -m modoor.web.app
