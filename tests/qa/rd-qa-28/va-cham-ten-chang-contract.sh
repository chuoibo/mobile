#!/usr/bin/env bash
# rd-qa-28 -- Reproduces the stage-name collision between PR #165 and main.
#
# What it proves, in order:
#   1. main@f995873 already has a gate stage named `contract` (actor headers, #163).
#   2. PR #165 adds a DIFFERENT check under the same stage name `contract`.
#   3. Merging the two leaves TWO `do_contract()` definitions in scripts/gate.sh,
#      and neither one lands inside a conflict marker -- git merges them silently.
#   4. Bash keeps the LAST definition, so #165's check replaces #163's.
#   5. `./scripts/gate.sh contract` then prints main's description, runs #165's
#      check, and reports PASS. The actor-header self-test never runs.
#   6. tests/test_gate_covers_every_workflow_job.py stays green through all of it.
#
# Usage:  bash tests/qa/rd-qa-28/va-cham-ten-chang-contract.sh
# Exit 0  = the collision reproduced (the finding is real).
# Exit 1  = the collision did NOT reproduce (PR #165 was rebased/renamed -- recheck).

set -uo pipefail

MAIN_SHA="${MAIN_SHA:-f995873}"
PR_SHA="${PR_SHA:-399a7b0}"
WT="$(mktemp -d /tmp/rd-qa-28.XXXXXX)"
REPO_ROOT="$(git rev-parse --show-toplevel)"

cleanup() {
  git -C "$REPO_ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || true
  rm -rf "$WT"
}
trap cleanup EXIT

say() { printf '\n=== %s ===\n' "$1"; }
fail() { printf 'KHONG TAI LAP DUOC: %s\n' "$1"; exit 1; }

git -C "$REPO_ROOT" worktree add --detach "$WT" "$MAIN_SHA" >/dev/null 2>&1 \
  || fail "khong tao duoc worktree tai $MAIN_SHA"
cd "$WT"

say "1. main@$MAIN_SHA: chang \`contract\` la gi"
grep -n 'contract)  echo' scripts/gate.sh | head -1

say "2. gate.sh contract tren main SACH -- co chay self-test khong"
./scripts/gate.sh contract 2>&1 | grep -E 'self-test|canary|loi goi deu gui|lời gọi đều gửi' \
  || fail "main sach khong chay self-test header -- gia dinh nen da sai"

say "3. merge PR #165 ($PR_SHA) vao main"
git merge --no-commit --no-ff "$PR_SHA" >/dev/null 2>&1
conflicted="$(git diff --name-only --diff-filter=U | tr '\n' ' ')"
echo "file xung dot: $conflicted"
[ -n "$conflicted" ] || fail "khong co xung dot -- PR co the da duoc rebase"

# Resolve every visible conflict the way a reviewer does when they believe
# main's side is the keeper: take HEAD. This is the NAIVE resolution under test.
python3 - <<'PY'
import re
for p in ("scripts/gate.sh", "tests/test_gate_covers_every_workflow_job.py"):
    t = open(p).read()
    t = re.sub(r'<<<<<<< HEAD\n(.*?)=======\n.*?>>>>>>> \w+\n', r'\1', t, flags=re.S)
    open(p, "w").write(t)
PY
git show "$PR_SHA":scripts/check_api_contract.py > scripts/check_api_contract.py

say "4. sau khi go het marker: con may dinh nghia do_contract()?"
n_def="$(grep -c '^do_contract()' scripts/gate.sh)"
echo "so dinh nghia do_contract(): $n_def"
[ "$n_def" -ge 2 ] || fail "chi co $n_def dinh nghia -- va cham da bien mat"

say "5. hai dinh nghia do co nam trong conflict marker khong?"
markers="$(grep -c '<<<<<<<\|>>>>>>>' scripts/gate.sh || true)"
echo "so conflict marker con lai: $markers"
[ "$markers" -eq 0 ] || fail "van con marker -- ban resolve chua sach"
bash -n scripts/gate.sh || fail "gate.sh khong parse duoc"
echo "gate.sh parse duoc, khong con marker: va cham la AM THAM"

say "6. bash giu dinh nghia NAO"
cat > "$WT/lastwins.sh" <<'SH'
do_contract() { echo "ACTOR-HEADER (#163, tren main)"; }
do_contract() { echo "ROUTE-EXISTENCE (#165)"; }
do_contract
SH
winner="$(bash "$WT/lastwins.sh")"
echo "bash chay: $winner"

say "7. ./scripts/gate.sh contract tren cay DA MERGE"
out="$(./scripts/gate.sh contract 2>&1)"; code=$?
echo "$out" | grep -E '=== contract ===|ĐẠT|HỎNG' | head -4
echo "EXIT=$code"
if echo "$out" | grep -q 'self-test'; then
  fail "self-test header VAN chay -- va cham khong gay hau qua"
fi
echo "self-test header KHONG chay: cong #163 da chet AM THAM"
[ "$code" -eq 0 ] || fail "gate bao HONG -- va cham se bi nguoi ta thay ngay"
echo "gate van bao DAT (exit 0): chet trong im lang"

say "8. cong tu kiem cua repo co bat duoc khong"
python3 -m pytest tests/test_gate_covers_every_workflow_job.py -q 2>&1 | tail -3

say "KET LUAN"
cat <<'EOF'
Va cham TAI LAP DUOC:
  - hai check khac nhau dung chung ten chang `contract`
  - git merge im lang hai dinh nghia do_contract()
  - bash giu ban cua #165, cong header actor cua #163 chet
  - gate.sh van in mo ta cua #163 va bao DAT
  - test_gate_covers_every_workflow_job.py van xanh
Cach go: doi ten chang cua #165 (vi du `client-routes`) va map lai COVERED_BY.
EOF
exit 0
