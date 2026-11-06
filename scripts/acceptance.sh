#!/usr/bin/env bash
# ACCEPTANCE RUN WITHOUT RETYPING ANYTHING.
#
#   scripts/acceptance.sh                 engine vs terminal, every symbol in SMT_SYMBOLS
#   scripts/acceptance.sh --dashboard     + old dashboard vs terminal (asks your dashboard password, hidden)
#   scripts/acceptance.sh GOLD            one symbol
#
# Reads from .env: SMT_SIGNALMESH_API_KEY (the bb_ read key), SMT_ACCESS_TOKEN (terminal token),
# SMT_SYMBOLS, SMT_PUBLIC_SIGNALMESH_URL (https://app.<domain>; detected from the SignalMesh
# Caddyfile the first time and written back), SMT_DASHBOARD_LOGIN (your dashboard email, for
# --dashboard; set it once and it is remembered). The password is never stored anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "no .env here — run scripts/setup.sh first"; exit 1; }
getv() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | xargs || true; }
setv() { if grep -qE "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }

DASH=0; SYMS=()
for a in "$@"; do case "$a" in --dashboard) DASH=1 ;; *) SYMS+=("$a") ;; esac; done

KEY=$(getv SMT_SIGNALMESH_API_KEY); [[ -n "$KEY" ]] || { echo "SMT_SIGNALMESH_API_KEY is empty in .env — run scripts/setup.sh"; exit 1; }
TOKEN=$(getv SMT_ACCESS_TOKEN)
[[ ${#SYMS[@]} -gt 0 ]] || mapfile -t SYMS < <(getv SMT_SYMBOLS | tr ',' '\n')

# The public SignalMesh address: from .env, else from the SignalMesh Caddyfile (via the caddy
# container's mount), else ask once. Remembered in .env.
URL=${SM_URL:-$(getv SMT_PUBLIC_SIGNALMESH_URL)}
if [[ -z "$URL" ]] && command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  for id in $(docker ps -q); do
    svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id" 2>/dev/null || true)
    if [[ "$svc" == "caddy" ]]; then
      cf=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$id" 2>/dev/null || true)
      [[ -f "$cf" ]] || cf=/srv/brotherbot/Caddyfile
      host=$(grep -E '^[a-zA-Z0-9.-]+\s*\{' "$cf" 2>/dev/null | head -1 | awk '{print $1}' || true)
      [[ -n "$host" && "$host" != "app.yourdomain.com" ]] && URL="https://$host"
      break
    fi
  done
fi
if [[ -z "$URL" ]]; then read -r -p "   SignalMesh public address (e.g. https://app.signalmesh.dev): " URL; fi
[[ "$(getv SMT_PUBLIC_SIGNALMESH_URL)" == "$URL" ]] || setv SMT_PUBLIC_SIGNALMESH_URL "$URL"

LOGIN=""
if [[ $DASH -eq 1 ]]; then
  LOGIN=${SM_LOGIN:-$(getv SMT_DASHBOARD_LOGIN)}
  if [[ -z "$LOGIN" ]]; then read -r -p "   your SignalMesh dashboard email (remembered in .env; the password is not): " LOGIN; setv SMT_DASHBOARD_LOGIN "$LOGIN"; fi
fi

echo "▶ acceptance: engine $URL  ·  terminal http://127.0.0.1:8090  ·  symbols ${SYMS[*]}  ·  dashboard comparison: $([[ $DASH -eq 1 ]] && echo "yes ($LOGIN)" || echo no)"
SM_URL="$URL" SM_KEY="$KEY" TERM_URL="http://127.0.0.1:8090" TERM_TOKEN="$TOKEN" SM_LOGIN="$LOGIN" \
  python3 scripts/verify_parity.py "${SYMS[@]}" 2>&1 | grep -E "FAIL|NOTE|logged in|dashboard|checks|^==" 
