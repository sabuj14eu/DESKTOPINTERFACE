#!/usr/bin/env bash
# ONE-COMMAND SETUP for the SignalMesh Terminal on the server where SignalMesh runs.
#
#   scripts/setup.sh bb_<read-key>            detect, configure, build, start, verify, add HTTPS host — no prompts
#   scripts/setup.sh                          same, asks once for the read key (hidden input)
#   scripts/setup.sh bb_<read-key> --no-caddy same, but leave the SignalMesh Caddyfile alone
#   scripts/setup.sh bb_<read-key> --subdomain  serve at terminal.<domain> (needs a DNS record) instead of /terminal/
#   scripts/setup.sh --dry-run                detect and print what would be written; change nothing
#
# DEFAULT = PATH MODE: the terminal is served at https://<SignalMesh host>/terminal/ through the
# existing Caddy site block (one redir + one handle_path inserted). No DNS, no subdomain.
#
# What it detects FROM THE SYSTEM (no typing):
#   * the SignalMesh app container and the docker network it lives on
#   * the SignalMesh checkout directory and its Caddyfile domain (-> terminal.<domain>)
#   * the public SignalMesh address (from SignalMesh's .env BB_BASE_URL or its Caddyfile)
#   * LOGIN: the terminal uses the user's own SignalMesh login (SMT_AUTH=signalmesh). No token.
#     (--token switches to a separate lock-screen token instead.)
# What it must ASK for (a secret is never guessed or scraped):
#   * the READ-ONLY SignalMesh API key (Dashboard -> API -> new key, permissions "read")
# Before every rebuild it copies the terminal's own forecast journal to ./backups/ (scripts/journal_backup.sh).
# It never touches SignalMesh's containers, database or .env. The ONLY thing it
# changes outside this directory is one appended site block in the SignalMesh
# Caddyfile (plus a caddy restart) so the terminal gets an HTTPS hostname.
set -euo pipefail
cd "$(dirname "$0")/.."
DRY=0; NOCADDY=0; SUBDOMAIN=0; TOKENMODE=0; ARG_KEY=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --no-caddy) NOCADDY=1 ;;
    --subdomain) SUBDOMAIN=1 ;;
    --token) TOKENMODE=1 ;;
    bb_*) ARG_KEY="$a" ;;
    *) echo "✖ '$a' is not a SignalMesh API key. The key starts with bb_ and is created INSIDE SignalMesh:"
       echo "    log in to the SignalMesh dashboard -> /api-access -> new key -> permissions 'read' -> copy bb_..."
       echo "  (The random token from 'python3 -c \"import secrets...\"' is NOT needed: this script generates the terminal token itself.)"
       echo "  Then: scripts/setup.sh bb_<that key>      or run scripts/setup.sh with no argument and paste it when asked."
       exit 2 ;;
  esac
done

say() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '   \033[1;32m✔\033[0m %s\n' "$*"; }
warn(){ printf '   \033[1;33m!\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }

ENVF=.env
[[ -f "$ENVF" ]] || cp .env.example "$ENVF"
getv() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | xargs || true; }
setv() {  # setv KEY VALUE — replace or append, keep the file otherwise intact
  if grep -qE "^$1=" "$ENVF"; then sed -i "s|^$1=.*|$1=$2|" "$ENVF"; else echo "$1=$2" >> "$ENVF"; fi
}

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

# ---------------------------------------------------------------- 2. the SignalMesh Caddyfile and public host
DOMAIN=""; APP_HOST=""; CADDYFILE=""; CADDY_ID=""
# a) the caddy container of the same compose project: its /etc/caddy/Caddyfile bind mount is the file
for id in $(docker ps -q); do
  proj=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$id" 2>/dev/null || true)
  svc=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.service"}}' "$id" 2>/dev/null || true)
  if [[ "$svc" == "caddy" && ( -z "$PROJECT" || "$proj" == "$PROJECT" ) ]]; then
    CADDY_ID="$id"
    CADDYFILE=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$id" 2>/dev/null || true)
    break
  fi
done
# b) fallbacks by path
if [[ -z "$CADDYFILE" || ! -f "$CADDYFILE" ]]; then
  for c in "${SM_DIR:-/nonexistent}/Caddyfile" /srv/brotherbot/Caddyfile; do
    if [[ -f "$c" ]]; then CADDYFILE="$c"; break; fi
  done
fi
# b2) nginx on the host serving the SignalMesh app: the site file is the one that proxies to the
#     app container's published port
NGINX_FILE=""; APP_PORT=$(docker inspect -f '{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostPort}} {{end}}{{end}}' "$APP_ID" 2>/dev/null | awk '{print $1}')
if systemctl is-active --quiet nginx 2>/dev/null; then
  # -R follows the symlinks that sites-enabled is made of; match proxy_pass and upstream "server" lines
  [[ -n "$APP_PORT" ]] && NGINX_FILE=$(grep -RlE "(proxy_pass\s+http://|server\s+)(127\.0\.0\.1|localhost):$APP_PORT\b" /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/nginx/sites-available 2>/dev/null | head -1 || true)
  # fallback: the site file whose server_name is the host we were given / remembered
  WANT=${SMT_PUBLIC_HOST:-$(getv SMT_PUBLIC_SIGNALMESH_URL | sed 's#https\?://##; s#/.*##')}
  [[ -z "$NGINX_FILE" && -n "$WANT" && "$WANT" != *yourdomain* ]] && NGINX_FILE=$(grep -RlE "server_name[^;]*\b$WANT\b" /etc/nginx/sites-enabled /etc/nginx/conf.d /etc/nginx/sites-available 2>/dev/null | head -1 || true)
  [[ -n "$NGINX_FILE" && -L "$NGINX_FILE" ]] && NGINX_FILE=$(readlink -f "$NGINX_FILE")
  if [[ -n "$NGINX_FILE" ]]; then
    ok "nginx serves the SignalMesh app (port $APP_PORT) from $NGINX_FILE"
    NH=$(grep -E '^\s*server_name' "$NGINX_FILE" | head -1 | sed -E 's/^\s*server_name\s+//; s/;.*//' | awk '{print $1}')
    [[ -n "$NH" && "$NH" != "_" && "$NH" == *.* ]] && { APP_HOST="$NH"; DOMAIN=${APP_HOST#*.}; ok "SignalMesh public host (nginx): $APP_HOST"; }
  else
    warn "nginx is running but no site file proxies to port ${APP_PORT:-?} — pass the host once: SMT_PUBLIC_HOST=app.example.com scripts/setup.sh"
  fi
fi
# c) Caddy installed on the host itself (systemd), not in docker
CADDY_HOST=0
if [[ -z "$CADDYFILE" || ! -f "$CADDYFILE" ]] && [[ -f /etc/caddy/Caddyfile ]] && systemctl is-active --quiet caddy 2>/dev/null; then
  CADDYFILE=/etc/caddy/Caddyfile; CADDY_HOST=1
fi
# the public address SignalMesh itself is configured with (one non-secret line of its .env)
BB_BASE=$(grep -E '^BB_BASE_URL=' "${SM_DIR:-/nonexistent}/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]' || true)
if [[ -n "$CADDYFILE" && -f "$CADDYFILE" ]]; then
  ok "Caddyfile: $CADDYFILE$([[ $CADDY_HOST -eq 1 ]] && echo ' (Caddy runs on the host)')"
  # the first site block "app.example.com {"
  CH=$(grep -E '^[a-zA-Z0-9.-]+\s*\{' "$CADDYFILE" | head -1 | awk '{print $1}')
  [[ -z "$APP_HOST" ]] && APP_HOST="$CH"
  if [[ -n "$APP_HOST" && "$APP_HOST" != "app.yourdomain.com" ]]; then
    DOMAIN=${APP_HOST#*.}
    ok "SignalMesh public host: $APP_HOST"
  else
    warn "the Caddyfile's site host is still the placeholder; HTTPS step will be manual"; APP_HOST=""
  fi
else
  warn "no SignalMesh Caddyfile found; HTTPS step will be manual"; CADDYFILE=""
fi
if [[ -z "$APP_HOST" && "$BB_BASE" == https://* && "$BB_BASE" != *yourdomain* ]]; then APP_HOST=${BB_BASE#https://}; APP_HOST=${APP_HOST%%/*}; DOMAIN=${APP_HOST#*.}; ok "SignalMesh public host (from BB_BASE_URL): $APP_HOST"; fi
[[ "$APP_HOST" == *yourdomain* ]] && APP_HOST=""
if [[ -z "$APP_HOST" ]]; then
  warn "SignalMesh's public host is not written in its Caddyfile or BB_BASE_URL (both still say app.yourdomain.com)."
  warn "Pass it once:  SMT_PUBLIC_HOST=app.signalmesh.dev scripts/setup.sh   — it is remembered in .env"
  pub=$(getv SMT_PUBLIC_SIGNALMESH_URL); [[ "$pub" == https://* && "$pub" != *yourdomain* ]] && { APP_HOST=${pub#https://}; APP_HOST=${APP_HOST%%/*}; DOMAIN=${APP_HOST#*.}; ok "using remembered public host $APP_HOST"; }
  [[ -n "${SMT_PUBLIC_HOST:-}" ]] && { APP_HOST="$SMT_PUBLIC_HOST"; DOMAIN=${APP_HOST#*.}; ok "using given public host $APP_HOST"; }
fi
TERM_HOST=${TERM_HOST:-${DOMAIN:+terminal.$DOMAIN}}
NGINX_FILE=${NGINX_FILE:-}
if [[ $SUBDOMAIN -eq 1 ]]; then TERM_URL_PUBLIC="https://$TERM_HOST"; else TERM_URL_PUBLIC="${APP_HOST:+https://$APP_HOST/terminal/}"; fi

# ---------------------------------------------------------------- 3. the .env
say "Writing the terminal's own .env (SMT_* only)"

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
if [[ $TOKENMODE -eq 1 && -z "$TOKEN" ]]; then TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); NEW_TOKEN=1; fi
AUTH=$([[ $TOKENMODE -eq 1 ]] && echo token || echo signalmesh)

SYMS=$(getv SMT_SYMBOLS)   # empty = discover every instrument SignalMesh has candles for
if [[ "$SYMS" == "GOLD,SILVER,BTC" ]]; then
  # the first release wrote this default as a pin; pins only RESTRICT, so it hid every other
  # instrument SignalMesh has candles for. Clear it; set SMT_SYMBOLS yourself only to restrict.
  SYMS=""; warn "SMT_SYMBOLS was the old default GOLD,SILVER,BTC — cleared so every instrument with candles is shown"
fi

if [[ $DRY -eq 1 ]]; then
  say "DRY RUN — would write to $ENVF:"
  echo "   SMT_PROVIDER=signalmesh"
  echo "   SMT_SIGNALMESH_URL=http://$APP_SERVICE:8000"
  echo "   SMT_SIGNALMESH_API_KEY=<asked, hidden>"
  echo "   SMT_AUTH=$AUTH"
  echo "   SMT_SYMBOLS=$SYMS"
  echo "   SMT_ENV=production"
  echo "   SIGNALMESH_NETWORK=$NETWORK"
  echo "   public URL: ${TERM_URL_PUBLIC:-<manual>}  (mode: $([[ $SUBDOMAIN -eq 1 ]] && echo subdomain || echo path))"
  exit 0
fi

setv SMT_PROVIDER signalmesh
setv SMT_SIGNALMESH_URL "http://$APP_SERVICE:8000"
setv SMT_SIGNALMESH_API_KEY "$KEY"
setv SMT_AUTH "$AUTH"
setv SMT_ACCESS_TOKEN "$TOKEN"
setv SMT_SYMBOLS "$SYMS"
setv SMT_ENV production
setv SIGNALMESH_NETWORK "$NETWORK"
[[ -n "$APP_HOST" ]] && setv SMT_PUBLIC_SIGNALMESH_URL "https://$APP_HOST"
pub=$(getv SMT_PUBLIC_SIGNALMESH_URL); [[ -z "$pub" || "$pub" == http* ]] || sed -i '/^SMT_PUBLIC_SIGNALMESH_URL=/d' .env
sed -i '/^SMT_DASHBOARD_LOGIN=/d' .env
chmod 600 "$ENVF"
ok ".env written (chmod 600). Market watch: ${SYMS:-every instrument SignalMesh has candles for (discovered)}."

# ---------------------------------------------------------------- 4. build + start
say "Backing up the forecast journal before the rebuild"
scripts/journal_backup.sh || die "the forecast journal could not be backed up — nothing was rebuilt. Fix the line above, or paste it to me."
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
MW=$(curl -s --max-time 30 -H "X-Terminal-Key: $KEY" http://127.0.0.1:8090/api/terminal/market-watch || true)
if echo "$MW" | grep -q '"rows"'; then
  ok "API key accepted — market watch answered"
  MW="$MW" python3 - <<'PY'
import json, os
d = json.loads(os.environ["MW"])
for r in d["rows"]:
    print(f"      {r['symbol']:8} close1m={r['price']} fresh={r['freshness']['state']} source={r['source_kind']} {r.get('error', '')}")
kinds = {r["source_kind"] for r in d["rows"]}
print("      candle provenance:", "ALL MT5 REPORTER" if kinds == {"mt5_reporter"} else "NOT ALL BROKER DATA -> " + ", ".join(sorted(kinds)))
PY
else
  warn "market watch did not answer: $(echo "$MW" | head -c 200)"
  warn "if it says UNAUTHORIZED, the API key was refused by SignalMesh — create a new read key and run this script again"
fi

# ---------------------------------------------------------------- 5. HTTPS through the existing Caddy
echo
PROXY_TARGET=$([[ $CADDY_HOST -eq 1 ]] && echo "127.0.0.1:8090" || echo "signalmesh-terminal:8090")
caddy_restart() {
  if [[ $CADDY_HOST -eq 1 ]]; then sudo systemctl reload caddy
  elif [[ -n "$CADDY_ID" ]]; then docker restart "$CADDY_ID" >/dev/null
  elif [[ -n "$SM_DIR" ]]; then ( cd "$SM_DIR" && docker compose restart caddy ); fi
}
if [[ $NOCADDY -eq 1 ]]; then
  warn "--no-caddy: no proxy configuration was touched. Path mode needs the lines of nginx.terminal.snippet / Caddyfile.path.snippet inside the $APP_HOST site."
elif [[ -n "$NGINX_FILE" && $SUBDOMAIN -eq 0 ]]; then
  if grep -q "location /terminal/" "$NGINX_FILE"; then
    ok "$NGINX_FILE already routes /terminal/ to the terminal"
  else
    say "Inserting the /terminal/ route into the HTTPS server block of $NGINX_FILE and reloading nginx"
    sudo cp "$NGINX_FILE" "$NGINX_FILE.bak.$(date +%Y%m%d%H%M%S)"
    sudo python3 - "$NGINX_FILE" "$APP_HOST" <<'PY'
import re, sys
path, host = sys.argv[1], sys.argv[2]
text = open(path).read()
snippet = open("nginx.terminal.snippet").read().rstrip("\n")
# find server { ... } blocks; insert into the one(s) that listen on 443 (or the only one)
blocks = []
i = 0
while True:
    m = re.search(r"\bserver\s*\{", text[i:])
    if not m:
        break
    start = i + m.start(); depth = 0; j = i + m.end() - 1
    while j < len(text):
        if text[j] == "{": depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0: break
        j += 1
    blocks.append((start, j)); i = j + 1
targets = [b for b in blocks if re.search(r"listen[^;]*443", text[b[0]:b[1]])] or blocks[-1:]
if not targets:
    sys.exit(f"no server block found in {path}")
for start, end in reversed(targets):
    block = text[start:end]
    m = re.search(r"\n(\s*)server_name[^\n]*\n", block)
    pos = start + (m.end() if m else block.index("{") + 1)
    text = text[:pos] + snippet + "\n" + text[pos:]
open(path, "w").write(text)
print(f"inserted into {len(targets)} server block(s)")
PY
    if sudo nginx -t 2>&1 | tail -1 | grep -q successful; then
      sudo systemctl reload nginx; ok "nginx reloaded — open https://$APP_HOST/terminal/"
    else
      sudo nginx -t 2>&1 | tail -3
      latest=$(ls -t "$NGINX_FILE".bak.* | head -1); sudo cp "$latest" "$NGINX_FILE"
      die "nginx -t failed; $NGINX_FILE restored from $latest — paste the lines above to me"
    fi
  fi
elif [[ -z "$CADDYFILE" || -z "$APP_HOST" ]]; then
  warn "no Caddyfile/host detected — front http://127.0.0.1:8090 with your own reverse proxy (see Caddyfile.path.snippet)"
elif [[ $SUBDOMAIN -eq 1 ]]; then
  if grep -q "^$TERM_HOST" "$CADDYFILE"; then ok "$CADDYFILE already has a block for $TERM_HOST"; else
    say "Adding $TERM_HOST site block to $CADDYFILE and restarting caddy"
    SUDO=""; [[ -w "$CADDYFILE" ]] || SUDO=sudo
    sed "s/terminal.yourdomain.com/$TERM_HOST/; s/signalmesh-terminal:8090/$PROXY_TARGET/" Caddyfile.snippet | $SUDO tee -a "$CADDYFILE" >/dev/null
    caddy_restart; ok "Caddy restarted — open https://$TERM_HOST once the DNS A record for it exists"
  fi
else
  if grep -q "handle_path /terminal/\*" "$CADDYFILE"; then
    ok "$CADDYFILE already routes /terminal/ to the terminal"
  elif ! grep -qE "^$APP_HOST\s*\{" "$CADDYFILE"; then
    warn "$CADDYFILE has no site block for $APP_HOST (it still says app.yourdomain.com), so this Caddy is NOT what serves https://$APP_HOST."
    warn "Tell me how $APP_HOST reaches the app (another proxy, a tunnel?) — run:  sudo ss -ltnp | grep -E ':80 |:443 '; docker ps --format '{{.Names}} {{.Ports}}'; systemctl is-active caddy nginx cloudflared"
  else
    say "Inserting the /terminal/ route into the $APP_HOST block of $CADDYFILE and restarting caddy"
    SUDO=""; [[ -w "$CADDYFILE" ]] || SUDO=sudo
    $SUDO cp "$CADDYFILE" "$CADDYFILE.bak.$(date +%Y%m%d%H%M%S)"
    # insert the snippet's directive lines right after the site opener line (first "host {" line)
    $SUDO python3 - "$CADDYFILE" "$APP_HOST" "$PROXY_TARGET" <<'PY'
import re, sys
path, host = sys.argv[1], sys.argv[2]
lines = open(path).read().split("\n")
snippet = [l.replace("signalmesh-terminal:8090", sys.argv[3]) for l in open("Caddyfile.path.snippet").read().split("\n") if l.strip() and not l.lstrip().startswith("#")]
for i, l in enumerate(lines):
    if re.match(rf"^{re.escape(host)}\s*\{{", l):
        lines[i+1:i+1] = snippet
        break
else:
    sys.exit(f"site block for {host} not found in {path}")
open(path, "w").write("\n".join(lines))
PY
    if docker run --rm -v "$CADDYFILE:/etc/caddy/Caddyfile:ro" caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
      ok "Caddyfile validates"
    else
      warn "caddy validate could not confirm the file (image unavailable or warning); restarting anyway — revert with the .bak copy if the site fails"
    fi
    caddy_restart
    ok "Caddy restarted — open $TERM_URL_PUBLIC"
  fi
fi

echo
say "DONE"
if [[ "$AUTH" == "signalmesh" ]]; then
  echo "   Login: your normal SignalMesh username and password (log in to SignalMesh, then open the Terminal menu)."
elif [[ $NEW_TOKEN -eq 1 ]]; then
  echo "   Terminal access token (type it on the terminal's lock screen; it is also in .env): $TOKEN"
fi
echo "   Open:          ${TERM_URL_PUBLIC:-http://127.0.0.1:8090/}"
echo "   Local check:   curl -s http://127.0.0.1:8090/api/terminal/health | python3 -m json.tool | head -30"
echo "   Acceptance:    scripts/acceptance.sh   (runs inside the container; needs nothing)"
echo "   Update later:  git pull && scripts/update.sh      (stops at once when nothing new was pulled)"
