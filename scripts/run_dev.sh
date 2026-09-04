#!/usr/bin/env bash
# Start API (:8765) + selected module Vue apps; API reverse-proxies /web/<module>.
# Usage: scripts/run_dev.sh [base] [wiki] [sale] ...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${MODOOR_WEB_HOST:-127.0.0.1}"
PORT="${MODOOR_WEB_PORT:-8765}"

module_port() {
  case "$1" in
    base) echo 5175 ;;
    wiki) echo 5176 ;;
    sale) echo 5177 ;;
    skill) echo 5178 ;;
    doc) echo 5179 ;;
    *) echo "" ;;
  esac
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

MODULES=("$@")
if [[ ${#MODULES[@]} -eq 0 ]]; then
  echo "usage: make dev <module> [module...]"
  echo "  modules: base wiki sale skill doc"
  echo "  example: make dev base"
  echo "           make dev base wiki"
  exit 1
fi

PIDS=()
API_PID=""
PROXY_PARTS=()

cleanup() {
  trap - EXIT INT TERM
  local pid
  for pid in "${PIDS[@]:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
    wait "${API_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

start_webui() {
  local name="$1"
  local dir="${ROOT}/modules/${name}/webui"
  local p
  p="$(module_port "${name}")"
  if [[ ! -d "${dir}" ]]; then
    echo "!! unknown or missing module webui: ${name}" >&2
    echo "   expected: ${dir}" >&2
    exit 1
  fi
  free_port "${p}"
  PROXY_PARTS+=("${name}=http://127.0.0.1:${p}")
  (
    cd "${dir}"
    if [[ ! -d node_modules ]]; then
      echo ">> npm install (${name})"
      npm install
    fi
    export MODOOR_PUBLIC_HOST="${HOST}"
    export MODOOR_PUBLIC_PORT="${PORT}"
    npm run dev
  ) &
  PIDS+=($!)
}

for mid in "${MODULES[@]:-}"; do
  [[ -z "${mid}" ]] && continue
  start_webui "${mid}"
done

set -a
# shellcheck disable=SC1091
source .env
set +a

# Join proxies: base=http://127.0.0.1:5175,wiki=... → mounted as /web/base, /web/wiki
MODOOR_WEBUI_PROXIES="$(IFS=,; echo "${PROXY_PARTS[*]}")"
export MODOOR_WEBUI_PROXIES
# Same-origin entries for resolve_entry
export MODOOR_WEBUI_URL="http://${HOST}:${PORT}"

echo ""
echo "API / login  http://${HOST}:${PORT}/login"
echo "same port    http://${HOST}:${PORT}/web/<module>"
for mid in "${MODULES[@]:-}"; do
  [[ -z "${mid}" ]] && continue
  printf "  /web/%-6s → vite :%s\n" "${mid}" "$(module_port "${mid}")"
done
echo "proxies      ${MODOOR_WEBUI_PROXIES}"
echo "  MCP binary: ${ROOT}/.venv/bin/modoor-mcp"
echo ""

free_port "${PORT}"
"${ROOT}/.venv/bin/python" -m modoor.web.app &
API_PID=$!
PIDS+=("${API_PID}")

wait "${API_PID}"
