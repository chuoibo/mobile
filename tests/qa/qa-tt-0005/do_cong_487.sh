#!/usr/bin/env bash
# Re-runs the QA evidence for PR #487 without touching the repo tree or the
# live harness at ~/agent-harness. Everything it writes goes under /tmp.
#
# Run from the repo root, standing on PR #487's head (7ed5984):
#   bash tests/qa/qa-tt-0005/do_cong_487.sh
#
# Three blocks, in the order they were run:
#   A  drift gate  -- four states must each go red with exit 2 (positive controls)
#   B  selfcheck   -- six status branches, including the one that must go GREEN
#   C  clock gate  -- clean canary green, faithful dirty canary red; this is the
#                     mechanism behind the blocker: one edit OUTSIDE the repo
#                     flips a test INSIDE the repo.
set -u

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO" || exit 1
TMP=/tmp/qa-tt-0005
rm -rf "$TMP"; mkdir -p "$TMP"

echo "do tai   $(git rev-parse HEAD)"
echo "san      $(git rev-parse --short origin/main) la to tien: $(git merge-base --is-ancestor origin/main HEAD && echo CO || echo KHONG)"
echo

# ---------------------------------------------------------------- A
echo "=== A. cong lech trien khai: bon doi chung duong ==="
mkdir -p "$TMP"/ctl/{behind,diverged,missing,unmanaged}
OLD=$(git log --format=%H -n 6 -- scripts/agent_supervisor.py | tail -1)
git show "$OLD:scripts/agent_supervisor.py" > "$TMP/ctl/behind/agent_supervisor.py"
cp scripts/agent_checkpoint.py "$TMP/ctl/behind/"
cp scripts/agent_supervisor.py scripts/agent_checkpoint.py "$TMP/ctl/diverged/"
printf '\n# sua tay khong he co trong lich su\n' >> "$TMP/ctl/diverged/agent_supervisor.py"
cp scripts/agent_supervisor.py "$TMP/ctl/missing/"
cp scripts/agent_supervisor.py scripts/agent_checkpoint.py scripts/harness_selfcheck.py "$TMP/ctl/unmanaged/"
for c in behind diverged missing unmanaged; do
  python3 scripts/check_harness_deploy_drift.py --harness-root "$TMP/ctl/$c" --no-fetch >/dev/null 2>&1
  echo "  $c -> exit=$?  (mong doi 2)"
done
echo

# ---------------------------------------------------------------- B
echo "=== B. harness_selfcheck status: sau nhanh ==="
SC=scripts/harness_selfcheck.py
fp() { python3 -c "
import importlib.util as u, sys
from pathlib import Path
s=u.spec_from_file_location('sc','scripts/harness_selfcheck.py'); m=u.module_from_spec(s); s.loader.exec_module(m)
print(m.fingerprint(Path(sys.argv[1])))" "$1"; }
mk() { r="$TMP/sc/$1"; rm -rf "$r"; mkdir -p "$r/state" "$r/tests"; echo "x=1" > "$r/a.py"; }
NOW=$(date +%s)
mk a
mk b; echo '{ khong phai json' > "$TMP/sc/b/state/selfcheck.json"
mk c; printf '{"unix":1,"verdict":"XANH","ran_tests":6,"code_fingerprint":"x"}' > "$TMP/sc/c/state/selfcheck.json"
mk d; printf '{"unix":%s,"verdict":"XANH","ran_tests":6,"code_fingerprint":"%s"}' "$NOW" "$(fp "$TMP/sc/d")" > "$TMP/sc/d/state/selfcheck.json"
mk e; printf '{"unix":%s,"verdict":"XANH","ran_tests":6,"code_fingerprint":"sai"}' "$NOW" > "$TMP/sc/e/state/selfcheck.json"
touch -d "@$((NOW - 200000))" "$TMP/sc/e/a.py"   # sua "cu" hon max-age
mk f; printf '{"unix":%s,"verdict":"XANH","ran_tests":6,"code_fingerprint":"sai"}' "$NOW" > "$TMP/sc/f/state/selfcheck.json"
for c in a b c d e f; do
  out=$(python3 "$SC" --harness "$TMP/sc/$c" status 2>&1); rc=$?
  echo "  [$c] exit=$rc :: $(echo "$out" | head -1)"
done
echo "  mong doi: a,b,c,e -> 2   d -> 0 (XANH that su den duoc)   f -> 0 (an han)"
echo

# ---------------------------------------------------------------- C
echo "=== C. cong dong ho: canary sach vs canary hong ==="
if [ ! -d "$HOME/agent-harness" ]; then
  echo "  BO QUA: may nay khong co ~/agent-harness"; exit 0
fi
mkdir -p "$TMP/h"
cp "$HOME"/agent-harness/*.py "$TMP/h/" 2>/dev/null
cp -r "$HOME"/agent-harness/tests "$TMP/h/" 2>/dev/null
for c in sach hong; do
  rm -rf "$TMP/$c"; cp -r "$TMP/h" "$TMP/$c"
done
# Faithful to the real defect shape: BOTH ends of the subtraction produced in
# the same scope. A canary that passes `started` in as a parameter does NOT
# fire -- that is the detector's documented boundary, not a hole.
cat >> "$TMP/hong/agent_supervisor.py" <<'PY'


def _qa_do_khoang():
    started = time.time()
    time.sleep(0)
    return int(time.time() - started)
PY
for c in sach hong; do
  ( cd "$TMP/$c" && git init -q && git add -A )
  out=$(AGENT_HARNESS="$TMP/$c" python3 -m pytest tests/test_harness_deploy_dong_ho.py -q 2>&1 | tail -1)
  echo "  AGENT_HARNESS=$c -> $out"
done
echo "  mong doi: sach -> 3 passed   hong -> 1 failed"
echo
echo "Diem chan: khong dat bien nao thi ca thu ba doc thang ~/agent-harness,"
echo "mot thu muc NGOAI repo ma lane khac dang sua lien tuc."
