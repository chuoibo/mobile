#!/usr/bin/env bash
# Does the membership gate actually go red, and red in the right place?
#
# A green suite proves nothing on its own -- this repo has shipped five green
# gates in one afternoon that could not fail. Each mutation below is a way
# somebody could plausibly weaken the rule later. For every one we record which
# LAYER notices, because "some test went red" and "the right test went red" are
# different claims.
#
# Mutation 2 is the one that matters most: it must leave the fake layer GREEN
# and turn the live layer RED. If both go red, the fake is lying about being
# able to see membership state; if neither does, tests/postgres is decoration.
#
# Run from services/api. Restores the tree after every mutant -- the commit has
# to exist first, or `git checkout --` throws the fix away with the mutation.
set -uo pipefail

cd "$(dirname "$0")/../../../services/api" || exit 1
TARGET=app/api/service.py
FAKE="tests/api/test_expense_participants_must_be_members.py"
LIVE="tests/postgres/test_expense_participant_membership_postgres.py"

if ! git diff --quiet -- "$TARGET"; then
  echo "REFUSING: $TARGET has uncommitted changes; commit first." >&2
  exit 1
fi

PG_ENV=(
  "MOBILE_TEST_DATABASE_URL=postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/mobile"
  "MOBILE_REQUIRE_POSTGRES_TESTS=1"
)

restore() { git checkout -- "$TARGET"; }
trap restore EXIT

run_layer() { # <label> <paths...>
  local label=$1; shift
  local out rc
  out=$(env "${PG_ENV[@]}" python -m pytest "$@" -q 2>&1)
  rc=$?
  printf '    %-6s rc=%d  %s\n' "$label" "$rc" "$(printf '%s' "$out" | tail -n 1)"
  return $rc
}

mutant() { # <name> <python-patcher> <expect_fake:red|green> <expect_live:red|green>
  local name=$1 patcher=$2 want_fake=$3 want_live=$4
  echo "== $name"
  python - "$TARGET" <<PY || { echo "    PATCH FAILED"; restore; return 1; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
$patcher
p.write_text(s)
PY
  if git diff --quiet -- "$TARGET"; then
    echo "    PATCH WAS A NO-OP -- the mutation never applied, so rc below means nothing"
    restore; return 1
  fi

  local fake_state live_state
  run_layer fake "$FAKE" && fake_state=green || fake_state=red
  run_layer live "$LIVE" && live_state=green || live_state=red
  restore

  if [[ $fake_state == "$want_fake" && $live_state == "$want_live" ]]; then
    echo "    OK   fake=$fake_state live=$live_state (wanted fake=$want_fake live=$want_live)"
  else
    echo "    MISS fake=$fake_state live=$live_state (wanted fake=$want_fake live=$want_live)"
  fi
}

echo "# baseline -- unmutated tree must be green on both layers"
run_layer fake "$FAKE"
run_layer live "$LIVE"
echo

# 1. The whole gate deleted from the confirm path. Everything must notice.
mutant "gate removed from confirm_expense" '
old = """        self._require_participants_are_members(
            identity.context_id, request.proposal.participants
        )
"""
assert old in s, "call site not found"
s = s.replace(old, "", 1)
' red red

# 2. Only the state filter dropped, roster read intact. This is the realistic
#    "simplification": the code still looks like it checks membership.
mutant "state==active filter dropped" '
old = """            for membership in self.repository.list_members(context_id)
            if membership.state == "active"
"""
new = """            for membership in self.repository.list_members(context_id)
"""
assert old in s, "state filter not found"
s = s.replace(old, new, 1)
' green red

# 3. Same violation, different shape: the filter stays but always answers yes.
#    Guards against a canary that only recognises one spelling of the bug.
#
#    The anchor has to include the `for` line. `if membership.state == "active"`
#    on its own appears TWICE in this file, and `.replace(..., 1)` took the
#    other one -- in `split_bill`. The mutant then reported green while the
#    guard it claimed to be testing was untouched, which is a passing mutation
#    run that proves nothing. The no-op check below does not catch that: a diff
#    existed, just in the wrong function.
mutant "state filter always true" '
old = """            for membership in self.repository.list_members(context_id)
            if membership.state == \"active\"
"""
new = """            for membership in self.repository.list_members(context_id)
            if membership.state in {\"active\", \"invited\", \"left\"}
"""
assert old in s, "guard state filter not found"
assert s.count(old) == 1, "anchor is not unique -- it would hit split_bill"
s = s.replace(old, new, 1)
' green red

# 6. The OTHER copy of the filter, in `split_bill`. Found by mutation 3 landing
#    on it by accident: before this run, widening it left 1128 fake cases and
#    299 live ones entirely green. The preview the group reads before pressing
#    confirm would have spread the bill across a person who never accepted.
mutant "split_bill state filter widened" '
old = """            for membership in memberships
            if membership.state == \"active\"
"""
new = """            for membership in memberships
            if membership.state in {\"active\", \"invited\", \"left\"}
"""
assert old in s, "split_bill state filter not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, new, 1)
' green red

# 4. Refusal computed but never raised.
mutant "strangers found but not raised" '
old = "        if strangers:\n"
new = "        if False:\n"
assert old in s, "raise guard not found"
s = s.replace(old, new, 1)
' red red

# 5. Only the first stranger named. Money is still refused, so this must be
#    caught by the enumeration case rather than by the main refusal case.
mutant "only the first stranger named" '
old = "        if strangers:\n"
new = "        strangers = strangers[:1]\n        if strangers:\n"
assert old in s, "raise guard not found"
s = s.replace(old, new, 1)
' red green
