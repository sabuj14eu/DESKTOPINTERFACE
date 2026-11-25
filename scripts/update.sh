#!/usr/bin/env bash
# UPDATE THE BOX, BUT ONLY WHEN THERE IS SOMETHING NEW — nothing to type.
#   cd /srv/signalmesh-terminal && git pull && scripts/update.sh            the update: setup, acceptance, screenshots
#   cd /srv/signalmesh-terminal && git pull && scripts/update.sh --history  the same, then the recorded-history check
#
# FIRST it compares the commit of this folder (what "git pull" just fetched) with the commit the running
# terminal was built from. The same commit = nothing new was pulled: it says so and stops in a second,
# instead of rebuilding and running a ten-minute acceptance for nothing. The usual reason is that the pull
# request is not merged yet.
# This script never runs git: the pull is yours. It reads the checkout's commit from the .git folder as a file.
set -euo pipefail
cd "$(dirname "$0")/.."
HISTORY=0; FORCE=0
for a in "$@"; do case "$a" in --history) HISTORY=1 ;; --force) FORCE=1 ;; *) echo "unknown option $a (use --history or --force)"; exit 2 ;; esac; done

# the checkout's commit, read from the .git folder as plain files
head_commit() {
  local h ref
  h=$(cat .git/HEAD 2>/dev/null) || return 1
  if [[ "$h" == ref:* ]]; then
    ref=${h#ref: }
    if [[ -f ".git/$ref" ]]; then cat ".git/$ref"; else awk -v r="$ref" '$2 == r { print $1 }' .git/packed-refs 2>/dev/null; fi
  else echo "$h"; fi
}
HERE=$(head_commit | head -c 7 || true)
WANT=$(tr -d ' \n' < VERSION)
RUN=$(curl -s --max-time 5 http://127.0.0.1:8090/api/terminal/health 2>/dev/null \
  | python3 -c 'import json,sys; b=json.load(sys.stdin)["build"]; print(b.get("version",""), (b.get("commit") or "")[:7])' 2>/dev/null || true)
RUN_V=${RUN%% *}; RUN_C=${RUN##* }
echo "▶ this folder: version $WANT, commit ${HERE:-unknown}   ·   running terminal: version ${RUN_V:-not answering}, commit ${RUN_C:-unknown}"
if [[ $FORCE -eq 0 && -n "$HERE" && -n "$RUN_C" && "$HERE" == "$RUN_C" ]]; then
  echo "✔ NOTHING NEW: the running terminal is already built from this commit (V$RUN_V). Nothing was rebuilt, nothing was restarted."
  echo "  If you expected a newer version, the pull request is not merged yet — tell Claude \"merge it\", then run this line again."
  exit 0
fi
echo "▶ new commit — updating to V$WANT (10 to 15 minutes; asks for no password)"
scripts/setup.sh
# The checks after the rebuild ALL run, whatever the one before them said: a FAIL in acceptance must not hide the
# restore rehearsal, the chart checks or the history check (seen on the box, 2.7.1: one FAIL stopped the rest).
BAD=()
scripts/acceptance.sh || BAD+=("acceptance")
scripts/journal_restore_test.sh || BAD+=("journal restore rehearsal")
scripts/screenshots.sh || BAD+=("screenshots / chart checks")
if [[ $HISTORY -eq 1 ]]; then scripts/export_history.sh || BAD+=("history check"); fi
echo
if [[ ${#BAD[@]} -eq 0 ]]; then
  echo "✔ update finished: the toolbar should read V$WANT — every step ended without a failure"
else
  echo "✖ the terminal was updated to V$WANT and is running, but these steps reported a failure: ${BAD[*]}"
  echo "  Paste their FAIL lines to Claude. Do not run the whole line again: each step can be run on its own."
  exit 1
fi
