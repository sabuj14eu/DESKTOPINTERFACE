#!/usr/bin/env bash
# ACCEPTANCE RUN — nothing to type.   scripts/acceptance.sh [SYMBOL ...]
# Runs INSIDE the terminal container: engine = SignalMesh over the docker network (the same
# address the terminal itself uses), terminal = the adapter in the same container. Needs no
# public address, no certificate, no cookie, no token: the key is already in the container.
# Prints only FAIL/NOTE lines and the totals.
set -euo pipefail
cd "$(dirname "$0")/.."
SYMS=("$@")
if [[ ${#SYMS[@]} -eq 0 ]]; then mapfile -t SYMS < <(grep -E '^SMT_SYMBOLS=' .env | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr ',' '\n' | xargs -n1); fi
[[ ${#SYMS[@]} -gt 0 ]] || SYMS=(GOLD SILVER BTC)
echo "▶ acceptance inside the terminal container · symbols ${SYMS[*]}"
docker compose exec -T terminal sh -c 'SM_URL="$SMT_SIGNALMESH_URL" SM_KEY="$SMT_SIGNALMESH_API_KEY" TERM_URL=http://127.0.0.1:8090 python /srv/terminal/scripts/verify_parity.py "$@"' sh "${SYMS[@]}" 2>&1 | grep -E "FAIL|NOTE|checks|^=="
