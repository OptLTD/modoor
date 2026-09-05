#!/usr/bin/env bash
# Build selected module webuis (dist only).
# Usage: scripts/run_build.sh <module> [module...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODULES=("$@")
if [[ ${#MODULES[@]} -eq 0 ]]; then
  echo "usage: make build <module> [module...]"
  echo "  modules: base wiki sale skill"
  echo "  example: make build base"
  echo "           make build base wiki"
  exit 1
fi

for name in "${MODULES[@]}"; do
  [[ -z "${name}" ]] && continue
  dir="${ROOT}/modules/${name}/webui"
  if [[ ! -d "${dir}" ]]; then
    dir="${ROOT}/platform/${name}/webui"
  fi
  if [[ ! -d "${dir}" ]]; then
    echo "!! unknown or missing module webui: ${name}" >&2
    echo "   expected under modules/ or platform/: ${name}/webui" >&2
    exit 1
  fi
  (
    cd "${dir}"
    if [[ ! -d node_modules ]]; then
      echo ">> npm install (${name})"
      npm install
    fi
    echo ">> npm run build (${name})"
    npm run build
  )
done

echo "build ok: ${MODULES[*]}"
