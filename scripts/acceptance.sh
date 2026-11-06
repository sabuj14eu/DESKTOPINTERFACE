#!/usr/bin/env bash
# ACCEPTANCE RUN — nothing to type.   scripts/acceptance.sh [SYMBOL ...]
# Engine (SignalMesh /api/v1) vs terminal (/api/terminal), field by field. Reads the read key
# and symbols from .env; the SignalMesh address from .env (SMT_PUBLIC_SIGNALMESH_URL), else
# from SignalMesh's own .env (BB_BASE_URL) via its running container, else uses the internal
# address through the terminal container. Prints only FAIL/NOTE lines and the totals.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "no .env here — run scripts/setup.sh first"; exit 1; }
getv() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | xargs || true; }
KEY=$(getv SMT_SIGNALMESH_API_KEY); [[ -n "$KEY" ]] || { echo "SMT_SIGNALMESH_API_KEY is empty in .env — run scripts/setup.sh"; exit 1; }
SYMS=("$@"); [[ ${#SYMS[@]} -gt 0 ]] || mapfile -t SYMS < <(getv SMT_SYMBOLS | tr ',' '\n')
URL=${SM_URL:-$(getv SMT_PUBLIC_SIGNALMESH_URL)}
[[ "$URL" == http* ]] || URL=""
if [[ -z "$URL" ]] && docker info >/dev/null 2>&1; then
  for id in $(docker ps -q); do
    if [[ "$(docker inspect -f '{{join .Config.Cmd " "}}' "$id" 2>/dev/null)" == *"app.main:app"* ]]; then
      d=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$id"); URL=$(grep -E '^BB_BASE_URL=' "$d/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]' || true); break
    fi
  done
fi
if [[ "$URL" == http* ]]; then
  echo "▶ acceptance: engine $URL · terminal http://127.0.0.1:8090 · symbols ${SYMS[*]}"
  SM_URL="$URL" SM_KEY="$KEY" TERM_URL="http://127.0.0.1:8090" TERM_TOKEN="$(getv SMT_ACCESS_TOKEN)"  \
    python3 scripts/verify_parity.py "${SYMS[@]}" 2>&1 | grep -E "FAIL|NOTE|checks|^=="
else
  echo "▶ acceptance inside the terminal container (engine http://app:8000 · symbols ${SYMS[*]})"
  docker compose exec -T -e SM_URL=http://app:8000 -e SM_KEY="$KEY" -e TERM_URL=http://127.0.0.1:8090 terminal \
    python /srv/terminal/scripts/verify_parity.py "${SYMS[@]}" 2>&1 | grep -E "FAIL|NOTE|checks|^=="
fi
