#!/usr/bin/env bash
# BACK UP THE FORECAST JOURNAL — nothing to type.   scripts/journal_backup.sh
# Copies the terminal's own journal (its Docker volume) to ./backups/journal-<UTC time>-v<version>.sqlite
# and keeps the newest 30. The copy is made by SQLite itself, so it is consistent while the
# terminal is running. scripts/setup.sh runs this before every rebuild.
# Touches only the terminal's own volume and this folder. Nothing of SignalMesh is read or written.
#   exit 0 = a copy was made, or there is no journal yet (first install)      exit 1 = a journal exists and could NOT be copied
set -euo pipefail
cd "$(dirname "$0")/.."
VOLUME=signalmesh_terminal_journal
KEEP=${JOURNAL_BACKUPS_KEEP:-30}
docker volume inspect "$VOLUME" >/dev/null 2>&1 || { echo "   no forecast journal yet (volume $VOLUME does not exist) — nothing to back up"; exit 0; }
mkdir -p backups
VER=$(docker compose exec -T terminal cat /srv/terminal/VERSION 2>/dev/null | tr -d ' \r\n' || true)
NAME="journal-$(date -u +%Y%m%dT%H%M%SZ)-v${VER:-unknown}.sqlite"
if docker compose exec -T terminal test -f /data/journal.sqlite 2>/dev/null; then
  # the running terminal makes the copy (SQLite's own backup call), then it is taken out of the container
  OUT=$(docker compose exec -T terminal sh -c 'cd /srv/terminal/adapter && python -m signalmesh_terminal.journal backup /data/journal.sqlite /tmp/journal-backup.sqlite') \
    || { echo "✖ the journal could not be copied: $OUT"; exit 1; }
  docker compose cp terminal:/tmp/journal-backup.sqlite "backups/$NAME" >/dev/null
  docker compose exec -T terminal rm -f /tmp/journal-backup.sqlite
  echo "   ✔ journal backed up: backups/$NAME ($OUT)"
else
  # the terminal is not running (or is an older version without a journal): copy the files straight from the volume
  IMG=$(docker compose images -q terminal 2>/dev/null | head -1); IMG=${IMG:-python:3.12-slim}
  if docker run --rm -v "$VOLUME:/data:ro" "$IMG" test -f /data/journal.sqlite 2>/dev/null; then
    docker run --rm --user 0 -v "$VOLUME:/data:ro" -v "$PWD/backups:/out" "$IMG" sh -c "cp /data/journal.sqlite /out/$NAME && for x in wal shm; do [ -f /data/journal.sqlite-\$x ] && cp /data/journal.sqlite-\$x /out/$NAME-\$x; done; chown -R $(id -u):$(id -g) /out" \
      || { echo "✖ the journal exists in volume $VOLUME and could not be copied"; exit 1; }
    echo "   ✔ journal backed up from the stopped volume: backups/$NAME"
  else
    echo "   no forecast journal file yet — nothing to back up"; exit 0
  fi
fi
[[ -s "backups/$NAME" ]] || { echo "✖ backup file backups/$NAME is empty"; exit 1; }
ls -1t backups/journal-*.sqlite 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old" "$old-wal" "$old-shm"; done
echo "   backups kept: $(ls -1 backups/journal-*.sqlite | wc -l) (newest $KEEP) in $PWD/backups — copy them off the box if you want a second place"
