# Deployment — beside SignalMesh, without touching it

Assumes SignalMesh runs with its Docker Compose stack in `/srv/brotherbot`
(app + db + redis + caddy) as in its own `docs/DEPLOYMENT.md`.

## Fast path — one command

```bash
sudo mkdir -p /srv/signalmesh-terminal && sudo chown $USER:$USER /srv/signalmesh-terminal
git clone --branch claude/vibrant-albattani-kxhfwv https://github.com/sabuj14eu/DESKTOPINTERFACE.git /srv/signalmesh-terminal
cd /srv/signalmesh-terminal && scripts/setup.sh bb_YOUR_READ_KEY
```

`scripts/setup.sh` detects the SignalMesh app container and its docker network,
the SignalMesh directory and domain (from its Caddyfile), generates the terminal
access token, writes `.env`, builds and starts the container, verifies the key
with a real read, prints the candle provenance verdict, and appends
`terminal.<your domain>` to the SignalMesh Caddyfile and restarts caddy. The
only input is the read-only API key (step 0 below). `--no-caddy` skips the
Caddyfile; `--dry-run` only prints what it found. The manual steps below do
the same thing by hand.

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

## 4. HTTPS hostname (one block added to the SignalMesh Caddyfile)

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

## 5. Verify (Phase 3 parity, from the server)

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
