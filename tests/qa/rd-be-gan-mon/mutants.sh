#!/usr/bin/env bash
# Does the assignment gate go red, and red for the RIGHT reason?
#
# `PUT /bills/{id}/assignments` is the second call site of the ownership rule
# that #235 closed at `confirm_expense`. A gate added is not a gate proven: this
# repo has shipped green gates that could not fail, so every mutation below is a
# way somebody could plausibly weaken the rule later, and each records which
# LAYER notices. "Some test went red" and "the right test went red" are
# different claims.
#
# Two disciplines learned the hard way and kept here on purpose:
#   * every anchor asserts `s.count(old) == 1` before replacing. A duplicated
#     anchor let `.replace(..., 1)` patch the wrong function once already, and
#     the run reported GREEN while the guard it named was untouched.
#   * no mutation renames or removes a constant. A mutant that dies of
#     NameError is red for a reason that has nothing to do with the property.
#
# Run from anywhere. Restores the tree after every mutant, so the fix has to be
# COMMITTED first -- `git checkout --` throws away the mutation and any
# uncommitted work with it.
set -uo pipefail

cd "$(dirname "$0")/../../../services/api" || exit 1
TARGET=app/api/service.py
FAKE="tests/api/test_bill_assignments_must_be_members.py"
LIVE="tests/postgres/test_expense_participant_membership_postgres.py"

if ! git diff --quiet -- "$TARGET"; then
  echo "REFUSING: $TARGET has uncommitted changes; commit first." >&2
  exit 1
fi

# A database of this lane's own. tests/postgres shares one schema per session,
# and other lanes' containers have stamped the shared `mobile` DB with their own
# alembic revisions before now.
PG_ENV=(
  "MOBILE_TEST_DATABASE_URL=${MOBILE_TEST_DATABASE_URL:-postgresql+psycopg://mobile:mobile-dev-only@localhost:5432/betasgan}"
  "MOBILE_REQUIRE_POSTGRES_TESTS=1"
)

restore() { git checkout -- "$TARGET"; }
trap restore EXIT

run_layer() { # <label> <paths...>
  local label=$1; shift
  local out rc
  out=$(env "${PG_ENV[@]}" python3 -m pytest "$@" -q 2>&1)
  rc=$?
  printf '    %-6s rc=%d  %s\n' "$label" "$rc" "$(printf '%s' "$out" | tail -n 1)"
  return $rc
}

mutant() { # <name> <python-patcher> <expect_fake:red|green> <expect_live:red|green>
  local name=$1 patcher=$2 want_fake=$3 want_live=$4
  echo "== $name"
  python3 - "$TARGET" <<PY || { echo "    PATCH FAILED"; restore; return 1; }
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

# 1. The gate deleted from the assignment path. This is the bug as it shipped
#    before this commit, reproduced exactly: both layers must notice.
mutant "gate removed from confirm_bill_assignments" '
old = """        self._require_participants_are_members(
            bill.context_id,
            [
                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
            ],
        )
"""
assert old in s, "call site not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, "", 1)
' red red

# 2. Only the first assignment inspected. A bill is many lines; the stranger
#    lands on whichever dish they were tapped onto, not reliably the first.
#    This is the mutation that found the blind spot in the first draft of the
#    fake tests, where every stranger sat in item i1 -- it left BOTH layers
#    green until `..._on_a_later_dish_not_only_the_first` was added.
#
#    Expected live=green, and that is an exclusion on purpose rather than an
#    unexamined gap: the live bill in `_bill_of_one_item` has a single line, so
#    `[:1]` cannot change its meaning. "Iterate the whole request" is plain
#    Python request handling with no SQL in it, and the fake is the layer that
#    can express it. tests/postgres earns its runtime on what the fake CANNOT
#    say -- that the real roster returns INVITED rows looking like members.
#    Widening the live bill to two lines here would buy a second copy of a
#    property already proven, at the cost of a slower live layer.
mutant "only the first assignment checked" '
old = """                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
"""
new = """                participant_id
                for assignment in request.assignments[:1]
                for participant_id in assignment.participant_ids
"""
assert old in s, "comprehension not found"
assert s.count(old) == 1, "anchor is not unique"
s = s.replace(old, new, 1)
' red green

# 3. Gate runs, but after the write. The refusal still reaches the caller with
#    the right code, so any test that only reads the response body stays green.
#    Only a test that reads the stored row back can tell these apart.
mutant "gate moved after the write" '
gate = """        self._require_participants_are_members(
            bill.context_id,
            [
                participant_id
                for assignment in request.assignments
                for participant_id in assignment.participant_ids
            ],
        )
"""
assert s.count(gate) == 1, "gate anchor is not unique"
s = s.replace(gate, "", 1)
tail = """        return _wire_bill(record)

    def split_bill("""
assert s.count(tail) == 1, "return anchor is not unique"
s = s.replace(tail, gate + tail, 1)
' red red
