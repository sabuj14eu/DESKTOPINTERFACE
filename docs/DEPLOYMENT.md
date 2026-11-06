# Deployment — beside SignalMesh, without touching it

Assumes SignalMesh runs with its Docker Compose stack in `/srv/brotherbot`
(app + db + redis + caddy) as in its own `docs/DEPLOYMENT.md`.

## Fast path — one command, one website, no new DNS

```bash
sudo mkdir -p /srv/signalmesh-terminal && sudo chown $USER:$USER /srv/signalmesh-terminal
git clone --branch claude/vibrant-albattani-kxhfwv https://github.com/sabuj14eu/DESKTOPINTERFACE.git /srv/signalmesh-terminal
cd /srv/signalmesh-terminal && scripts/setup.sh bb_YOUR_READ_KEY
```

The terminal is then at **`https://<your SignalMesh host>/terminal/`** (path mode,
the default). `scripts/setup.sh` detects the SignalMesh app container and its
docker network, finds the SignalMesh Caddyfile through the caddy container's
mount and reads the public host from it, generates the terminal access token,
writes `.env`, builds and starts the container, verifies the key with a real
read, prints the candle provenance verdict, and inserts a `/terminal/` route
into the existing site block of the SignalMesh Caddyfile (one `redir` and one
`handle_path`, see `Caddyfile.path.snippet`; a `.bak` copy is kept) and
restarts caddy. Nothing else in that file changes. The only input is the
read-only API key (step 0 below).

Flags: `--no-caddy` leaves the Caddyfile alone · `--subdomain` uses
`terminal.<domain>` instead (needs a DNS A record) · `--dry-run` only prints
what it found. Re-running is safe: it reuses the key and token in `.env` and
skips the Caddy insert when the route is already there.

Refreshing `/terminal/` keeps working because Caddy routes the whole
`/terminal/*` prefix to the terminal container before the request can reach
the SignalMesh app. **Login is SignalMesh's own**: the browser sends its
`bb_session` cookie to `/terminal/` too, and the adapter asks SignalMesh (a
read-only session-protected JSON route, no redirects followed, cached 60 s)
whether that session is live. Not logged in → the terminal sends you to
SignalMesh's login page and back. No token, no second password.
`scripts/setup.sh --token` switches to a standalone lock-screen token instead.

### The one dashboard change: the "Terminal" menu item
SignalMesh gains a single navigation link to `/terminal/` (opens in a new tab).
It is a four-line template change in `app/templates/dash/_base.html` of
`sabuj14eu/Sniper-System`, delivered as its own pull request. Deploy it with
SignalMesh's normal ceremony after merging:

```bash
cd /srv/brotherbot && ./scripts/backup.sh && git pull && docker compose up -d --build app && docker compose logs --tail 20 app
```

## 0. One-time: a READ-ONLY API key in SignalMesh

Log in to SignalMesh → Dashboard → **API** → new key, label `terminal`,
permissions **read** (not write). Copy the `bb_…` value once; it is shown once.
This is the only thing the terminal ever holds of SignalMesh.

## 1. Get the code

```bash
sudo mkdir -p /srv && cd /srv
git clone https://github.com/sabuj14eu/DESKTOPINTERFACE.git signalmesh-terminal
cd signalmesh-terminal
```

## 2. Configure (its own .env, SMT_ prefix)

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # -> SMT_ACCESS_TOKEN
docker network ls | grep brotherbot                               # -> SIGNALMESH_NETWORK (usually brotherbot_default)
nano .env
chmod 600 .env
```

Set: `SMT_SIGNALMESH_API_KEY` (the read key), `SMT_ACCESS_TOKEN` (generated),
`SMT_SYMBOLS` (e.g. `GOLD,SILVER,BTC`), `SIGNALMESH_NETWORK`. Leave
`SMT_SIGNALMESH_URL=http://app:8000` — the terminal reaches SignalMesh over the
docker network, so no new port is opened on the platform.

## 3. Launch

```bash
docker compose up -d --build
docker compose logs --tail 30 terminal
curl -s http://127.0.0.1:8090/api/terminal/health | python3 -m json.tool | head -40
```

`provider.configured` must be `true`, `upstream.reachable` and `upstream.ok` must be `true`,
`execution.can_place` must be `false`.

## 4. HTTPS — path mode (default) or subdomain

`scripts/setup.sh` finds whatever serves the SignalMesh site and adds the
`/terminal/` route there: **nginx on the host** (the site file that proxies to
the app container's published port; two location blocks from
`nginx.terminal.snippet`, `nginx -t`, reload, with a `.bak` copy and automatic
restore if the test fails), a Caddy container, or a host Caddy.

**Path mode (default, no DNS):** `scripts/setup.sh` inserts the lines of
`Caddyfile.path.snippet` into the existing SignalMesh site block. By hand:

```bash
sudo nano /srv/brotherbot/Caddyfile     # paste the snippet lines right after "app.yourdomain.com {"
```

```bash
cd /srv/brotherbot && docker compose restart caddy
```

**Subdomain mode (`--subdomain`):** one block added to the SignalMesh Caddyfile

DNS: an A record `terminal.yourdomain.com` → the VPS IP. Then append the block
from `Caddyfile.snippet` to `/srv/brotherbot/Caddyfile` and reload Caddy:

```bash
cat /srv/signalmesh-terminal/Caddyfile.snippet | sed 's/yourdomain.com/YOURDOMAIN/' | sudo tee -a /srv/brotherbot/Caddyfile
```

```bash
cd /srv/brotherbot && docker compose restart caddy
```

Open `https://terminal.yourdomain.com`, enter the `SMT_ACCESS_TOKEN`.
This adds a hostname only; the `app.yourdomain.com` block and the SignalMesh
containers are untouched.

## 5. Verify (Phase 3 parity, from the server) — nothing to retype

```bash
cd /srv/signalmesh-terminal && scripts/acceptance.sh
```

reads the read key and the symbols from `.env`, finds the SignalMesh address
(`.env`, else SignalMesh's own `BB_BASE_URL`), authenticates to the terminal
with the read key (`X-Terminal-Key`), and prints only FAIL lines and totals.
Nothing is asked. The optional old-dashboard comparison is in
`scripts/verify_parity.py` (`SM_LOGIN=<email>`, password asked hidden).

### Long form

```bash
cd /srv/signalmesh-terminal
SM_URL=https://app.yourdomain.com SM_KEY=bb_... TERM_URL=http://127.0.0.1:8090 TERM_TOKEN=... \
  SM_SESSION_COOKIE=<bb_session cookie of your logged-in dashboard> \
  python3 scripts/verify_parity.py GOLD SILVER BTC
```

`N checks, 0 FAIL` is the pass. Any FAIL prints both values. The source audit must
say the candles are `mt5` reporter feeds; `NOT ALL BROKER DATA` on the terminal's
Data Sources tab means the platform is storing non-reporter candles and the
terminal is right to refuse the MT5 label.

## 6. Update ceremony

```bash
cd /srv/signalmesh-terminal
git pull
docker compose up -d --build
docker compose logs --tail 30 terminal
curl -s http://127.0.0.1:8090/api/terminal/health | head -c 400
```

## 7. Remove

```bash
cd /srv/signalmesh-terminal && docker compose down
```
then delete the `terminal.yourdomain.com` block from the Caddyfile, restart Caddy,
and revoke the `terminal` API key in SignalMesh → Dashboard → API.

## Alternative: not on the SignalMesh docker network

Set `SMT_SIGNALMESH_URL=https://app.yourdomain.com`, delete the two `networks`
blocks from `docker-compose.yml`, and front port 8090 with any reverse proxy.
