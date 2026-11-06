#!/usr/bin/env bash
# ONE-COMMAND SETUP for the SignalMesh Terminal on the server where SignalMesh runs.
#
#   scripts/setup.sh bb_<read-key>            detect, configure, build, start, verify, add HTTPS host — no prompts
#   scripts/setup.sh                          same, asks once for the read key (hidden input)
#   scripts/setup.sh bb_<read-key> --no-caddy same, but leave the SignalMesh Caddyfile alone
#   scripts/setup.sh --dry-run                detect and print what would be written; change nothing
#
# What it detects FROM THE SYSTEM (no typing):
#   * the SignalMesh app container and the docker network it lives on
#   * the SignalMesh checkout directory and its Caddyfile domain (-> terminal.<domain>)
#   * a fresh SMT_ACCESS_TOKEN (generated, shown ONCE)
# What it must ASK for (a secret is never guessed or scraped):
#   * the READ-ONLY SignalMesh API key (Dashboard -> API -> new key, permissions "read")
# It never touches SignalMesh's containers, database or .env. The ONLY thing it
# changes outside this directory is one appended site block in the SignalMesh
# Caddyfile (plus a caddy restart) so the terminal gets an HTTPS hostname.
set -euo pipefail
cd "$(dirname "$0")/.."
DRY=0; NOCADDY=0; ARG_KEY=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --no-caddy) NOCADDY=1 ;;
    bb_*) ARG_KEY="$a" ;;
    *) echo "unknown argument: $a"; exit 2 ;;
  esac
done

say() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '   \033[1;32m✔\033[0m %s\n' "$*"; }
warn(){ printf '   \033[1;33m!\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }

command -v docker >/dev/null || die "docker is not installed (SignalMesh runs on docker; install it first)"
docker info >/dev/null 2>&1 || die "cannot talk to docker — run: sudo usermod -aG docker \$USER && re-login, or run this script with sudo"

# ---------------------------------------------------------------- 1. find SignalMesh
say "Looking for the running SignalMesh app container"
APP_ID=""
# a) a compose service named "app" whose image/command is the Brother Bot platform (uvicorn app.main:app)
for id in $(docker ps -q); do
  svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id" 2>/dev/null || true)
  cmd=$(docker inspect -f '{{join .Config.Cmd " "}}' "$id" 2>/dev/null || true)
  if [[ "$svc" == "app" && "$cmd" == *"app.main:app"* ]]; then APP_ID="$id"; break; fi
done
# b) fallback: any container running uvicorn app.main:app
if [[ -z "$APP_ID" ]]; then
  for id in $(docker ps -q); do
    cmd=$(docker inspect -f '{{join .Config.Cmd " "}}' "$id" 2>/dev/null || true)
    if [[ "$cmd" == *"app.main:app"* ]]; then APP_ID="$id"; break; fi
  done
fi
[[ -n "$APP_ID" ]] || die "no running SignalMesh app container found (docker ps shows none running 'uvicorn app.main:app'). Start SignalMesh first."

APP_NAME=$(docker inspect -f '{{.Name}}' "$APP_ID" | sed 's#^/##')
APP_SERVICE=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$APP_ID"); APP_SERVICE=${APP_SERVICE:-$APP_NAME}
PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$APP_ID")
SM_DIR=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$APP_ID")
NETWORK=$(docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$APP_ID" | awk '{print $1}')
[[ -n "$NETWORK" ]] || die "the app container $APP_NAME is on no docker network"
ok "container $APP_NAME (compose project '${PROJECT:-?}', service '$APP_SERVICE')"
ok "docker network: $NETWORK"
ok "SignalMesh directory: ${SM_DIR:-unknown}"

# ---------------------------------------------------------------- 2. domain from Caddyfile
DOMAIN=""
CADDYFILE=""
for c in "${SM_DIR:-/nonexistent}/Caddyfile" /srv/brotherbot/Caddyfile; do
  if [[ -f "$c" ]]; then CADDYFILE="$c"; break; fi
done
if [[ -n "$CADDYFILE" ]]; then
  # first site block: "app.example.com {"  -> example.com
  HOST=$(grep -E '^[a-zA-Z0-9.-]+\s*\{' "$CADDYFILE" | head -1 | awk '{print $1}')
  if [[ -n "$HOST" && "$HOST" != "app.yourdomain.com" ]]; then
    DOMAIN=${HOST#*.}; APP_HOST="$HOST"
    ok "SignalMesh public host: $APP_HOST  ->  terminal host: terminal.$DOMAIN"
  else
    warn "Caddyfile found but the domain is still the placeholder; the terminal hostname must be chosen by hand"
  fi
else
  warn "no SignalMesh Caddyfile found; HTTPS hostname step will be manual"
fi
TERM_HOST=${TERM_HOST:-${DOMAIN:+terminal.$DOMAIN}}

# ---------------------------------------------------------------- 3. the .env
say "Writing the terminal's own .env (SMT_* only)"
ENVF=.env
[[ -f "$ENVF" ]] || cp .env.example "$ENVF"
getv() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | xargs || true; }
setv() {  # setv KEY VALUE — replace or append, keep the file otherwise intact
  if grep -qE "^$1=" "$ENVF"; then sed -i "s|^$1=.*|$1=$2|" "$ENVF"; else echo "$1=$2" >> "$ENVF"; fi
}

KEY="${ARG_KEY:-${SMT_SIGNALMESH_API_KEY:-$(getv SMT_SIGNALMESH_API_KEY)}}"
if [[ -z "$KEY" && $DRY -eq 0 ]]; then
  echo
  echo "   The READ-ONLY SignalMesh API key: log in to https://${APP_HOST:-app.yourdomain.com}"
  echo "   -> Dashboard -> API -> new key, label 'terminal', permissions 'read' -> copy the bb_... value."
  read -r -s -p "   Paste it here (input hidden): " KEY; echo
  [[ "$KEY" == bb_* ]] || die "that does not look like a SignalMesh API key (expected bb_...)"
fi

TOKEN=$(getv SMT_ACCESS_TOKEN)
NEW_TOKEN=0
if [[ -z "$TOKEN" ]]; then TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); NEW_TOKEN=1; fi

SYMS=$(getv SMT_SYMBOLS); SYMS=${SYMS:-GOLD,SILVER,BTC}

if [[ $DRY -eq 1 ]]; then
  say "DRY RUN — would write to $ENVF:"
  echo "   SMT_PROVIDER=signalmesh"
  echo "   SMT_SIGNALMESH_URL=http://$APP_SERVICE:8000"
  echo "   SMT_SIGNALMESH_API_KEY=<asked, hidden>"
  echo "   SMT_ACCESS_TOKEN=<generated>"
  echo "   SMT_SYMBOLS=$SYMS"
  echo "   SMT_ENV=production"
  echo "   SIGNALMESH_NETWORK=$NETWORK"
  echo "   terminal hostname: ${TERM_HOST:-<manual>}"
  exit 0
fi

setv SMT_PROVIDER signalmesh
setv SMT_SIGNALMESH_URL "http://$APP_SERVICE:8000"
setv SMT_SIGNALMESH_API_KEY "$KEY"
setv SMT_ACCESS_TOKEN "$TOKEN"
setv SMT_SYMBOLS "$SYMS"
setv SMT_ENV production
setv SIGNALMESH_NETWORK "$NETWORK"
chmod 600 "$ENVF"
ok ".env written (chmod 600). Symbols: $SYMS — edit SMT_SYMBOLS in .env to change the watch list."

# ---------------------------------------------------------------- 4. build + start
say "Building and starting the terminal container"
docker compose up -d --build
say "Waiting for the adapter to answer"
HEALTH=""
for i in $(seq 1 30); do
  HEALTH=$(curl -s --max-time 3 http://127.0.0.1:8090/api/terminal/health || true)
  [[ -n "$HEALTH" ]] && break
  sleep 2
done
[[ -n "$HEALTH" ]] || { docker compose logs --tail 40 terminal; die "the adapter did not answer on :8090 (logs above)"; }
python3 - "$HEALTH" <<'PY'
import json, sys
h = json.loads(sys.argv[1])
p, u, e = h["provider"], h["upstream"], h["execution"]
def line(okk, msg): print(("   \033[1;32m✔\033[0m " if okk else "   \033[1;31m✖\033[0m ") + msg)
line(p["configured"], f"provider {p['name']} configured={p['configured']} fixture={p['is_fixture']} url={p.get('url')}")
line(u.get("reachable") and u.get("ok"), f"SignalMesh upstream reachable={u.get('reachable')} ok={u.get('ok')} schema={u.get('schema')} {u.get('error','')}")
line(not e["can_place"], f"execution can_place={e['can_place']} phase={e['phase']}")
if not (p["configured"] and u.get("reachable") and u.get("ok") and not e["can_place"]):
    sys.exit(1)
PY
# the key must actually be accepted: one real read
MW=$(curl -s --max-time 30 -H "X-Terminal-Token: $TOKEN" http://127.0.0.1:8090/api/terminal/market-watch || true)
if echo "$MW" | grep -q '"rows"'; then
  ok "API key accepted — market watch answered"
  echo "$MW" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for r in d["rows"]:
    print(f"      {r[\"symbol\"]:8} close1m={r[\"price\"]} fresh={r[\"freshness\"][\"state\"]} source={r[\"source_kind\"]} {r.get(\"error\",\"\")}")
kinds={r["source_kind"] for r in d["rows"]}
print("      candle provenance:", "ALL MT5 REPORTER" if kinds=={"mt5_reporter"} else "NOT ALL BROKER DATA -> "+", ".join(sorted(kinds)))'
else
  warn "market watch did not answer: $(echo "$MW" | head -c 200)"
  warn "if it says UNAUTHORIZED, the API key was refused by SignalMesh — create a new read key and run this script again"
fi

# ---------------------------------------------------------------- 5. HTTPS hostname (optional, asked)
echo
if [[ -n "$TERM_HOST" && -n "$CADDYFILE" ]]; then
  if grep -q "^$TERM_HOST" "$CADDYFILE"; then
    ok "$CADDYFILE already has a block for $TERM_HOST"
  else
    if [[ $NOCADDY -eq 1 ]]; then
      warn "--no-caddy: not touching $CADDYFILE. Later: sed \"s/terminal.yourdomain.com/$TERM_HOST/\" Caddyfile.snippet | sudo tee -a $CADDYFILE && (cd $SM_DIR && docker compose restart caddy)"
    else
      say "Adding $TERM_HOST to $CADDYFILE and restarting caddy (SignalMesh's own site block is untouched)"
      SUDO=""; [[ -w "$CADDYFILE" ]] || SUDO=sudo
      sed "s/terminal.yourdomain.com/$TERM_HOST/" Caddyfile.snippet | $SUDO tee -a "$CADDYFILE" >/dev/null
      ( cd "$SM_DIR" && docker compose restart caddy )
      ok "Caddy restarted — open https://$TERM_HOST (needs a DNS A record $TERM_HOST -> this server; Caddy fetches the certificate once DNS resolves)"
    fi
  fi
else
  warn "no domain detected — front http://127.0.0.1:8090 with your own reverse proxy, or add the Caddyfile.snippet block by hand"
fi

echo
say "DONE"
if [[ $NEW_TOKEN -eq 1 ]]; then
  echo "   Terminal access token (type it on the terminal's lock screen; it is also in .env):"
  echo "   $TOKEN"
fi
echo "   Local check:   curl -s http://127.0.0.1:8090/api/terminal/health | python3 -m json.tool | head -30"
echo "   Acceptance:    SM_URL=https://${APP_HOST:-app.yourdomain.com} SM_KEY=<read key> TERM_URL=http://127.0.0.1:8090 TERM_TOKEN=$TOKEN SM_SESSION_COOKIE=<bb_session> python3 scripts/verify_parity.py $(echo "$SYMS" | tr ',' ' ')"
echo "   Update later:  git pull && docker compose up -d --build"
