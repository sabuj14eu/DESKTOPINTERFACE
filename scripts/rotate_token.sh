#!/usr/bin/env bash
# Replace the terminal access token (SMT_ACCESS_TOKEN) with a fresh one and restart the container.
set -euo pipefail
cd "$(dirname "$0")/.."
NEW=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
sed -i "s|^SMT_ACCESS_TOKEN=.*|SMT_ACCESS_TOKEN=$NEW|" .env
docker compose up -d
echo "new terminal token (also in .env): $NEW"
