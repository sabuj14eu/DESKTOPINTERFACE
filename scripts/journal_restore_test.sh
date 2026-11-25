#!/usr/bin/env bash
# REHEARSE A JOURNAL RESTORE — nothing to type.   scripts/journal_restore_test.sh
# Takes a fresh backup, then opens the NEWEST backup file exactly as the terminal would open a restored journal:
# integrity check, every backed-up forecast and outcome present and unchanged in the live journal, readable
# through the terminal's own code, edits and deletions refused. Also compares the OLDEST kept backup, which
# shows that what was recorded before earlier deployments is still in the live journal, unchanged.
# The live journal is only read. Nothing is replaced, nothing of SignalMesh is touched.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T terminal true 2>/dev/null || { echo "✖ the terminal container is not running (scripts/setup.sh first)"; exit 1; }
echo "▶ journal restore rehearsal (read-only toward the live journal)"
scripts/journal_backup.sh
NEW=$(ls -1t backups/journal-*.sqlite 2>/dev/null | head -1 || true)
OLD=$(ls -1t backups/journal-*.sqlite 2>/dev/null | tail -1 || true)
[[ -n "$NEW" ]] || { echo "   NOT TESTED journal restore rehearsal: there is no backup file yet"; exit 0; }
BAD=0
for f in "$NEW" "$OLD"; do
  docker compose cp "$f" terminal:/tmp/restore-rehearsal.sqlite >/dev/null
  echo "   file $f"
  docker compose exec -T terminal sh -c 'cd /srv/terminal/adapter && python -m signalmesh_terminal.journal restore-check /data/journal.sqlite /tmp/restore-rehearsal.sqlite' | sed 's/^/   /' || BAD=1
  docker compose exec -T --user 0 terminal rm -f /tmp/restore-rehearsal.sqlite 2>/dev/null || docker compose exec -T terminal rm -f /tmp/restore-rehearsal.sqlite || true
  [[ "$NEW" == "$OLD" ]] && break
done
echo "   journal restore rehearsal: $([[ $BAD -eq 0 ]] && echo 'all OK' || echo 'FAIL — see the lines above')"
[[ $BAD -eq 0 ]]
