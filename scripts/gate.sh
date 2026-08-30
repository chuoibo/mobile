#!/usr/bin/env bash
#
# Run the gates that .github/workflows/*.yml run, on this machine, in one
# command.
#
# ## Why this exists
#
# GitHub Actions stopped starting jobs at 07:45Z on 2026-08-29: every run since
# ends in three to five seconds with "The job was not started because recent
# account payments have failed or your spending limit needs to be increased".
# Measured on 2026-08-29T12:0xZ: the last 100 runs are 100 failures and 0
# successes. Nothing is wrong with the code. `gh run view --log-failed` answers
# "log not found" and exits 0, so from the outside a dead account and a broken
# build look identical -- and nine pull requests merged that day under a red X
# that meant billing.
#
# `tests/test_workflow_gates_have_local_callers.py` (#148) already closed half
# of this: every gate that is a *script* must have a caller outside the
# workflows. It states the half it cannot close, in its own words:
#
#   "It also says nothing about workflow steps written inline rather than as a
#    script. Those cannot be detected this way."
#
# That is this file. The inline steps -- the offline DDL render, the image
# running as non-root, the container actually answering /healthz, the native
# bundle, and the one environment variable that turns three accessibility
# checks from decoration into a gate -- exist only inside YAML that currently
# cannot execute. Here they are, callable.
#
# ## The rule this file is built around
#
# A skip is not a pass. CLAUDE.md says it outright ("skip khong phai la xanh"),
# and the repository has been bitten by the other kind: a detector with no
# browser returning `[]` and exit 0, a postgres tier reporting 254 skips that
# read as green. So every stage here ends in exactly one of PASS, FAIL or SKIP;
# a SKIP must carry a reason; the summary prints the counts; and `--strict`
# turns every SKIP into a FAIL for use before a merge.
#
# The workflows' own distinction is kept too, because it is the right one:
# an absent directory is an absence and skipping is honest, but a directory
# that is present and has lost the file the stage runs is a defect, and
# skipping that would turn the stage green for the one reason it must not.
#
# ## What this does NOT prove
#
# It runs the same commands on a different machine. It does not prove the
# workflow YAML is well-formed, that the runner image still has what the jobs
# assume, or that the two will not drift apart -- nobody can check that while
# Actions is down. `tests/test_gate_covers_every_workflow_job.py` holds the
# narrower line that every job in the workflows is at least named here.
#
# Usage:
#   scripts/gate.sh                 every stage whose prerequisites are present
#   scripts/gate.sh api mobile      only those stages
#   scripts/gate.sh --strict        a SKIP is a failure (use before merging)
#   scripts/gate.sh --list          stage names and what each one runs
#
# Exit codes: 0 every stage that ran passed, 1 a stage failed,
# 2 the gate could not do its job -- bad arguments, or nothing ran at all.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

# MOBILE_GATE_IMAGE / MOBILE_GATE_CONTAINER: names no other worktree on this
# daemon can also address. Sourced here rather than inside `do_docker` so the
# id is one value for the whole run, and exported from there so
# `check_pinned_import.sh` builds the same tag instead of a second one.
# shellcheck source=scripts/gate_docker_names.sh
. "$REPO_ROOT/scripts/gate_docker_names.sh"

# Every stage, in run order: cheapest and most likely to fail first, so a
# broken tree is reported in seconds rather than after a docker build.
STAGES=(guard guard-range ruff contract client-routes server-routes screens cors api migration pinned-import demo-watch hero-walk shared mobile docker postgres e2e)

stage_help() {
  case "$1" in
    guard)     echo "repo_guard.py tree HEAD (repo-guard.yml)" ;;
    guard-range) echo "repo_guard.py range on every commit this branch adds (repo-guard.yml)" ;;
    ruff)      echo "ruff on the files this branch changes, uncommitted ones included (test.yml: lint)" ;;
    contract)  echo "every route wanting X-Actor-ID is called with it (test.yml: contract)" ;;
    client-routes) echo "every route apps/mobile calls exists in the API (test.yml: api, inline)" ;;
    server-routes) echo "every route the API declares is called by some screen -- the other direction" ;;
    screens)   echo "every screen under apps/mobile/src/screens is rendered by something the entry point reaches" ;;
    cors)      echo "every header and method apps/mobile sends survives the CORS preflight (test.yml: contract)" ;;
    api)       echo "pytest services/api/tests tests (test.yml: api)" ;;
    migration) echo "alembic upgrade head --sql, no database (test.yml: api, inline)" ;;
    pinned-import) echo "app imports under the fastapi version pinned in requirements-dev.txt, not the machine's (test.yml: docker, cheap half)" ;;
    demo-watch) echo "the demo box is still being watched, and its last verdict was about main (máy này thôi)" ;;
    hero-walk) echo "somebody walked ảnh->món->chia->trang khách on the demo box recently, and it worked (máy này thôi)" ;;
    shared)    echo "node packages/shared/money.test.mjs (test.yml: shared)" ;;
    mobile)    echo "tsc, npm test with MOBILE_REQUIRE_WEB_A11Y=1, expo export --platform all (test.yml: mobile)" ;;
    docker)    echo "image pinned, builds, non-root, no dev tooling, serves /healthz (test.yml: docker)" ;;
    postgres)  echo "every live case -- tests/postgres AND tests/qa -- against a real PostgreSQL it provisions itself (postgres-repository.yml)" ;;
    e2e)       echo "the vertical slice through src/api.ts against an API and database it provisions itself (test.yml: e2e)" ;;
  esac
}

STRICT=0
SELECTED=()

while [ $# -gt 0 ]; do
  case "$1" in
    --strict) STRICT=1 ;;
    --list)
      echo "Các chặng của cổng (thứ tự chạy):"
      for s in "${STAGES[@]}"; do printf '  %-14s %s\n' "$s" "$(stage_help "$s")"; done
      exit 0
      ;;
    -h|--help) sed -n '2,60p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Tham số lạ: $1 (xem scripts/gate.sh --help)" >&2; exit 2 ;;
    *)
      # An unknown stage name must not quietly select nothing and exit 0 --
      # that is the "green because it ran nothing" failure this file exists
      # to prevent, reproduced in its own argument parser.
      found=0
      for s in "${STAGES[@]}"; do [ "$s" = "$1" ] && found=1; done
      if [ "$found" -eq 0 ]; then
        echo "Không có chặng tên '$1'. Có: ${STAGES[*]}" >&2
        exit 2
      fi
      SELECTED+=("$1")
      ;;
  esac
  shift
done

[ ${#SELECTED[@]} -eq 0 ] && SELECTED=("${STAGES[@]}")

PASSED=(); FAILED=(); SKIPPED=(); SKIP_WHY=()
# Stages that failed WITHOUT running, and why. They write no log, so the
# failure report at the end has nothing to print for them -- and printing
# nothing under a header promising evidence is the exact shape this file was
# written to stamp out. Recorded here so the report can say what happened.
NORAN=(); NORAN_WHY=()
LOG_DIR="$(mktemp -d)"

banner() { printf '\n\033[1m=== %s ===\033[0m %s\n' "$1" "$(stage_help "$1")"; }
pass() { PASSED+=("$1"); printf '\033[32mĐẠT\033[0m     %s (%ss)\n' "$1" "$2"; }
fail() { FAILED+=("$1"); printf '\033[31mHỎNG\033[0m    %s (%ss)\n' "$1" "$2"; }
skip() { SKIPPED+=("$1"); SKIP_WHY+=("$1: $2"); printf '\033[33mBỎ QUA\033[0m  %s -- %s\n' "$1" "$2"; }

# A failure that never started. The reason goes to stderr for the reader
# watching the run, and into NORAN_WHY for the report at the end -- once stdout
# and stderr are separated, the stderr copy is the one that goes missing.
fail_noran() {
  echo "$2" >&2
  NORAN+=("$1"); NORAN_WHY+=("$2")
  fail "$1" 0
}

# Empty for a stage that ran. Callers use that to choose between printing a log
# and explaining its absence.
noran_why() {
  local i=0
  while [ "$i" -lt "${#NORAN[@]}" ]; do
    [ "${NORAN[$i]}" = "$1" ] && { printf '%s' "${NORAN_WHY[$i]}"; return 0; }
    i=$((i + 1))
  done
}

# Stage output is teed to a file so a failure can be re-printed at the end: on
# an eight-stage run the thing that broke has otherwise scrolled off.
have() { command -v "$1" >/dev/null 2>&1; }

# A per-run tag is a new image every run, and this gate runs dozens of times a
# day on a shared machine -- the fixed name it replaced at least got reused.
# So the run that generated the name takes it back off, once, after its last
# stage. Untagging leaves the layers, so the next run's build is still a cache
# hit; what goes away is the dangling entry in `docker images`.
gate_docker_cleanup() {
  [ "${MOBILE_GATE_NAMES_INHERITED:-0}" = "1" ] && return 0
  have docker || return 0
  docker rm -f "$MOBILE_GATE_CONTAINER" >/dev/null 2>&1 || true
  docker image rm -f "$MOBILE_GATE_IMAGE" >/dev/null 2>&1 || true
}
trap gate_docker_cleanup EXIT

# --- stage bodies ---------------------------------------------------------

do_guard() { python3 scripts/repo_guard.py tree HEAD; }

# The merge base with origin/main, or empty. Shared with check_prereq so the
# "nothing to scan" case can be reported as a skip rather than discovered
# halfway through the stage body.
guard_range_base() {
  local base
  base="$(git merge-base origin/main HEAD 2>/dev/null)" || base=""
  if [ -z "$base" ]; then
    git fetch --no-tags --quiet origin main 2>/dev/null || true
    base="$(git merge-base origin/main HEAD 2>/dev/null)" || base=""
  fi
  printf '%s' "$base"
}

do_guard-range() {
  # `guard` scans the tree at HEAD. That is not the same question, and the gap
  # between them is the whole reason repo-guard.yml runs both.
  #
  # A secret committed and then deleted in a later commit on the same branch is
  # absent from the tree at HEAD and present forever in history. Measured on
  # 2026-08-29 against a branch built exactly that way: `tree HEAD` passed with
  # 632 file scans and exit 0, `scripts/gate.sh guard` printed DAT, and
  # `range` found it -- one finding across 1265 file scans, exit 1.
  #
  # Three things could catch that, and while Actions is down none of them do.
  # The pre-commit hook is bypassed by `--no-verify` and absent entirely until
  # somebody runs scripts/setup-hooks.sh, which CLAUDE.md already says is
  # discipline rather than enforcement. The workflow step cannot start. So the
  # range form ran nowhere, on a repository whose stated rule is that bill
  # photos, account numbers and real participant names never enter Git at all
  # -- and where .gitignore is explicitly not a safe place to put them.
  #
  # `history` is deliberately not what this runs. It fails on main today
  # (findings predating the guard, from the 12,629-file era scripts/setup-hooks.sh
  # describes), so wiring it here would produce a stage that is red for
  # everyone forever and gets switched off within a day.
  local base count
  base="$(guard_range_base)"
  if [ -z "$base" ]; then
    # Same choice `do_ruff` makes, for the same reason: without a base there is
    # no answer, and a stage that cannot answer must not report that it did.
    echo "không tìm được merge base với origin/main" >&2
    return 1
  fi
  count="$(git rev-list --count "$base"..HEAD)"
  echo "quét $count commit nhánh này thêm vào, so với merge base $base"
  python3 scripts/repo_guard.py range "$base" HEAD
}

# The `ruff` stage's scopeless half: an assertion that is true or false no
# matter which files this branch changed. test.yml's lint job does not install
# whatever ruff it finds -- it reads this pin and fails with "::error::no ruff==
# pin" when there is none, so CI always lints with the version everybody agreed
# on.
#
# It is a function of its own because `check_prereq ruff` has to consult it
# before it is allowed to turn this stage into a skip. It did not, and that is
# the hole the two changes opened between them: the prereq decides from the
# changed-Python-file list alone, and deleting the pin edits a .txt file. No
# Python moves, so the scope is empty, so the stage skipped -- so the assertion
# written to catch exactly that deletion never ran. Measured on main, the same
# edit both times:
#
#   @ 23455e7 (pin check in, empty-scope skip not yet)
#     không có dòng ruff== ...        HỎNG    ruff (0s)          exit 1
#   @ ae45575 (both in)
#     BỎ QUA  ruff -- nhánh không đổi file Python nào ...        exit 2
#
# Anything added to do_ruff that does not depend on the changed-file list
# belongs on this side of the line too, or the skip will swallow it the same
# way. tests/test_gate_ruff_empty_scope.py holds both halves.
ruff_pin() {
  grep -E '^ruff==' services/api/requirements-dev.txt 2>/dev/null || true
}

do_ruff() {
  local pin
  pin="$(ruff_pin)"
  if [ -z "$pin" ]; then
    echo "không có dòng ruff== trong services/api/requirements-dev.txt" >&2
    echo "CI cài ruff từ pin đó; mất pin thì mỗi máy lint bằng một bản khác nhau." >&2
    return 1
  fi

  # This used to stop at a CHÚ Ý when the machine's ruff differed from the pin,
  # and pass the stage anyway. The reasoning was that hard-failing on a
  # mismatch makes the stage red on every machine with a newer ruff -- true,
  # and still true. What it missed is that a warning on line three of a
  # thirteen-stage run, under a summary that ends "ĐẠT ruff", is a warning
  # nobody reads, and while Actions is down this gate is the only one there is.
  #
  # Measured 2026-08-30 at c811254 over the 320 tracked Python files: the pin
  # (0.9.2) reports 31 findings, this machine's ruff (0.15.15) reports 30. The
  # missing one is UP038 on services/api/app/domain/place_search.py:105 -- a
  # rule later ruff REMOVED, so the newer binary cannot report it at all.
  # Editing that file got ĐẠT here and HỎNG in CI.
  #
  # So `ruff_changed.sh` now resolves the pin through scripts/ruff_pinned.sh
  # and provisions it when this machine lacks it, the same way
  # scripts/postgres_tier.sh stopped being a permanent BỎ QUA by building its
  # own database instead of demanding one. Nobody has to downgrade their
  # editor's ruff, and the verdict is CI's verdict.
  echo "pin: $pin"

  # The one-argument form compares <base> against the WORKING TREE, so this
  # covers changes not yet committed. CI can only ever see pushed commits;
  # locally the useful moment is before the commit exists.
  #
  # Shared with check_prereq deliberately. The two have to agree on which base
  # they mean: the prereq check decides whether this stage runs at all from the
  # file list at that base, and if it computed a different one it could skip a
  # stage that had work to do.
  local base
  base="$(guard_range_base)"
  if [ -z "$base" ]; then
    echo "không tìm được merge base với origin/main" >&2
    return 1
  fi
  echo "so với merge base $base"
  scripts/ruff_changed.sh "$base"
}

do_contract() {
  # Runs before `api` on purpose. It is seconds, and it answers a question no
  # other stage here asks: the two sides of one HTTP contract are checked by
  # two suites that each mock the other, so a route that starts demanding a
  # header leaves both suites green and the screen dead. See the file header.
  echo "--- self-test: the checker has to be able to be red"
  python3 scripts/check_actor_headers.py --selftest || return 1
  echo "--- client vs OpenAPI"
  python3 scripts/check_actor_headers.py
}

# Deliberately NOT called `do_contract`. It was, until 2026-08-29: this check
# was written on a branch cut before the actor-header stage reached main, and
# both stages picked the name `contract` independently. Merging the two left
# two `do_contract()` bodies in this file, neither inside a conflict marker,
# `bash -n` clean, and bash keeps the last one -- so the actor-header gate
# stopped running while `gate.sh contract` still printed its description and
# exited 0. tests/test_gate_stage_bodies_are_unique.py now refuses that shape.
do_client-routes() {
  # Reads the rendered OpenAPI and the client source. No database, no server,
  # no npm -- the two halves of a request compared where nothing else compares
  # them. Proven on 2026-08-29: with `/batches/current/publish` back in
  # api.ts, `tsc --noEmit` exited 0 and `npm test` passed 493 of 493.
  #
  # The self-test runs first for the same reason `do_contract`'s does, and the
  # reason got sharper on 2026-08-30: this checker used to drop, in silence,
  # every call whose URL it could not follow. `call<void>(path, ...)` with the
  # path handed in as a parameter named a route that has never existed and
  # exited 0. Six canaries now hold both halves -- that it reddens on a missing
  # route, and that it reddens when it cannot read the path at all.
  echo "--- self-test: the checker has to be able to be red"
  python3 scripts/check_api_contract.py --selftest || return 1
  echo "--- client vs OpenAPI"
  python3 scripts/check_api_contract.py
}

do_server-routes() {
  # `client-routes` asks whether every path the app calls exists. This asks the
  # other direction, which nothing in this repository asked until 2026-08-30: a
  # route the API declares that no screen calls does not exist for a user. It
  # ships, it is tested, it is merged, and it is unreachable.
  #
  # Measured on main at 8b6f847: 70 routes declared, 48 called, 5 belonging to
  # the guest page, and 17 with no caller at all. It earned its place the first
  # time it ran on a main newer than the tree it was written against: #319
  # merged /contexts/{id}/widget that morning and no screen calls it.
  #
  # The self-test runs first for the reason the two stages above it do, and
  # with a sharper edge here: this question was attempted twice by hand the
  # same day and got a different wrong answer each time -- substring matching
  # called four dead routes alive, whole-string matching called 32 live routes
  # dead. Six canaries hold both sides, three that must be red and three that
  # must stay green.
  echo "--- self-test: the checker has to be able to be red, and to be green"
  python3 scripts/check_server_routes_called.py --selftest || return 1
  echo "--- OpenAPI vs client"
  python3 scripts/check_server_routes_called.py
}

do_screens() {
  # The third link in the same chain, and the one nothing asked until
  # 2026-08-31. `client-routes` asks whether a path the app calls exists;
  # `server-routes` asks whether a declared route has a screen calling it.
  # Neither asks whether that screen is itself rendered by anything -- so a
  # screen can call its routes correctly, typecheck, pass both stages above,
  # and be openable by nobody.
  #
  # It earned its place on the run that introduced it. A work item claimed
  # `ChiaSe` and `MaCuaToi` had no way in, from a count of how often each name
  # appears under `src/`. Both were wired -- `ChiaSe` behind two real buttons,
  # `MaCuaToi` inside `MaKetBan` on Cá nhân -- and the count had missed the one
  # screen that really is dead, `TheDeXuat`, because it never named it. 48/49
  # reachable, 1 pinned with a reason.
  #
  # The self-test runs first, and here it carries a bug of its own making. The
  # first draft let an entry file's plain imports carry the chain, which marked
  # every screen `App.tsx` merely imports as reachable; deleting the real
  # `<ChiaSe />` render left the gate GREEN. Three canaries now hold it -- a
  # dead screen that must be red, an imported-but-never-rendered screen that
  # must be red, and a live tree that must stay green.
  echo "--- self-test: the checker has to be able to be red, and to be green"
  python3 scripts/check_screens_reachable.py --selftest || return 1
  echo "--- every screen against the render graph from the entry point"
  python3 scripts/check_screens_reachable.py
}

do_cors() {
  # The third question about one request, and the one no suite here can ask.
  # `contract` asks whether a call sends X-Actor-ID; `client-routes` asks
  # whether the path exists. Both assume the request is delivered. In a
  # browser it is not: a header the allowlist does not name is cancelled at
  # the preflight, and nothing in this repository is a browser -- TestClient
  # speaks in-process, node's fetch does not enforce CORS, and expo export
  # never issues a request.
  #
  # Measured on 2026-08-30 by adding "X-Client-Version" to the Khám phá search
  # headers: tsc 0, npm test 645/646 (identical to the clean baseline),
  # test_cors.py 13 passed, check_actor_headers 0, check_api_contract 0 --
  # and this stage exit 1, naming tim-kiem.ts:223.
  echo "--- self-test: the checker has to be able to be red"
  python3 scripts/check_cors_contract.py --selftest || return 1
  echo "--- client headers vs the CORS allowlist"
  python3 scripts/check_cors_contract.py
}

do_api() { python3 -m pytest services/api/tests tests -q; }

do_migration() {
  # The inline step from test.yml's api job. No database: this is the check
  # that was missing when five foreign-key names ran past PostgreSQL's
  # 63-character limit and the migration could not compile at all.
  ( cd services/api && python3 - <<'PY'
import contextlib, io
from alembic import command
from alembic.config import Config
config = Config("alembic.ini")
config.set_main_option("sqlalchemy.url", "postgresql+psycopg://offline/offline")
with contextlib.redirect_stdout(io.StringIO()):
    command.upgrade(config, "head", sql=True)
print("migration renders")
PY
  )
}

# The demo box on 8099 is what the leader opens to decide whether the product
# runs. Twice now it has served an older main than the one it claims to:
# 58 routes against 62 for sixteen commits, then 65 against 69 for the four
# album and contextual-suggestion routes. Neither was a gate failing.
# `check_demo_matches_main.py` answered correctly both times -- it was simply
# never asked, because its only caller was `make demo-check`, which nobody
# types until they already suspect the answer.
#
# So this stage is the caller, and it is deliberately in the DEFAULT list.
# `make gate` is the one thing on this machine that gets run dozens of times a
# day; a check wired anywhere else is decoration with extra steps. It reads the
# recorded verdict rather than measuring live -- `run` builds a worktree and
# renders main's OpenAPI, which is far too slow to sit in every gate run, and
# duplicating it here would just be a second unscheduled call site.
#
# What it does NOT prove: nothing here calls a product route, so a demo serving
# every path of main and answering 500 to all of them passes this stage. It
# says nothing about the mobile bundle, which is built separately and can be
# older than the API on the same box. And `status` proves a check RAN, not that
# the box was reachable between two runs.
do_demo-watch() {
  # --expect-ref is the default, spelled out because this is the assertion the
  # stage exists to make: a verdict about somebody's open branch is not a
  # verdict about main, however fresh it is.
  python3 scripts/demo_watch.py status --expect-ref origin/main
}

# The scan seam -- `POST /receipts/scan` -> `readingFromWire()` -> `POST /bills`
# -- is the one joint of the hero path no other stage crosses. `e2e` runs
# `duong-bill.test.mjs`, which begins at a `reading` written by hand; the client
# unit tests replay a wire body frozen on 2026-08-29; the live model tier is
# opt-in behind a variable nothing sets. Two green halves, no path.
#
# Like `demo-watch`, this reads a RECORDED verdict instead of measuring live: a
# real walk costs a Gemini call, and a paid nondeterministic step in the list
# that runs dozens of times a day would be removed within the week. The live
# walk is `make hero-walk`; this asserts somebody ran it, recently, against this
# box, and that it worked.
#
# What it does NOT prove: nothing here is measured now. A demo that broke five
# minutes ago passes this stage until the verdict ages out.
do_hero-walk() {
  # --url spelled out for the same reason demo-watch spells out --expect-ref:
  # a verdict about another box is the failure that looks most like a pass.
  scripts/hero_walk.sh --status --url http://127.0.0.1:8099
}

do_shared() { node packages/shared/money.test.mjs; }

do_mobile() {
  cd apps/mobile || return 1
  echo "--- tsc --noEmit"
  npx --no-install tsc --noEmit || return 1
  echo "--- npm test (MOBILE_REQUIRE_WEB_A11Y=1)"
  # The flag is the whole point of running this here. Without it a machine
  # with no browser skips the three render checks in tests/vo-tab-web.test.mjs
  # and `npm test` still exits 0 -- which is the exact shape of the hole they
  # were added to close.
  MOBILE_REQUIRE_WEB_A11Y=1 npm test || return 1
  echo "--- expo export --platform all"
  # Lives only in the workflow otherwise, on purpose (so it cannot be removed
  # by editing one line of package.json). Web is about a third of the native
  # module graph, so a react-native module with no web counterpart leaves
  # `npm test` perfectly green. Export outside the checkout so no artifact
  # lands in the tree.
  EXPO_NO_TELEMETRY=1 npx --no-install expo export --platform all \
    --output-dir "$LOG_DIR/expo-export" >/dev/null || return 1
  echo "bundled for web, ios and android"
}

do_pinned-import() {
  # The cheap half of `docker`. That stage is the only one that has ever loaded
  # the app with the pinned fastapi, but it builds an image, starts a container
  # and waits on a HEALTHCHECK, so it got skipped on exactly the PRs that
  # needed it -- including the one that shipped an app which could not be
  # imported at all. Same proof, about two seconds, so there is no longer a
  # reason to skip it. `docker` still runs everything else it checks.
  scripts/check_pinned_import.sh
}

do_docker() {
  echo "--- base image pinned by digest"
  scripts/check_dockerfile_pinning.sh services/api/Dockerfile || return 1
  echo "--- build"
  ( cd services/api && docker build -t "$MOBILE_GATE_IMAGE" . ) || return 1
  echo "--- runs as a non-root user"
  local uid
  uid="$(docker run --rm --entrypoint id "$MOBILE_GATE_IMAGE" -u)"
  echo "container uid = $uid"
  [ "$uid" = "0" ] && { echo "ảnh chạy bằng root" >&2; return 1; }
  echo "--- no test tooling in the runtime image"
  if docker run --rm --entrypoint sh "$MOBILE_GATE_IMAGE" -c "ls /venv/bin" | grep -qE '^(pytest|ruff)$'; then
    echo "pytest hoặc ruff lọt vào ảnh chạy thật" >&2; return 1
  fi
  echo "--- the container actually serves /healthz"
  # No published host port, for the reason the workflow gives: curling the
  # host passes whenever *anything* answers on that port. Polling the
  # container's own HEALTHCHECK cannot be satisfied by a stranger.
  docker rm -f "$MOBILE_GATE_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$MOBILE_GATE_CONTAINER" "$MOBILE_GATE_IMAGE" >/dev/null || return 1
  local i status
  for i in $(seq 1 60); do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$MOBILE_GATE_CONTAINER" 2>/dev/null)"
    case "$status" in
      healthy) echo "container healthy sau ${i}s"; docker rm -f "$MOBILE_GATE_CONTAINER" >/dev/null; return 0 ;;
      unhealthy) echo "container unhealthy" >&2; docker logs "$MOBILE_GATE_CONTAINER"; docker rm -f "$MOBILE_GATE_CONTAINER" >/dev/null; return 1 ;;
    esac
    if [ "$(docker inspect --format '{{.State.Running}}' "$MOBILE_GATE_CONTAINER" 2>/dev/null)" != "true" ]; then
      echo "container thoát trước khi healthy" >&2; docker logs "$MOBILE_GATE_CONTAINER"; docker rm -f "$MOBILE_GATE_CONTAINER" >/dev/null; return 1
    fi
    sleep 1
  done
  echo "container không bao giờ healthy" >&2; docker logs "$MOBILE_GATE_CONTAINER"; docker rm -f "$MOBILE_GATE_CONTAINER" >/dev/null; return 1
}

do_postgres() {
  # Delegates so the provisioning has a caller outside this file and can be
  # tested on its own (tests/test_postgres_tier_runner.py). The script builds
  # its own throwaway database when no URL is given, which is what stops this
  # stage from being the permanent BO QUA it had been: 147 skips and 0 runs in
  # CI, and a skip locally every time nobody exported a connection string.
  #
  # The runner covers `tests/qa` as well as `tests/postgres` since bug-082455.
  # The two trees looked like one because the stage reported a single number:
  # 306 passing cases, which is exactly what `tests/postgres` collects alone,
  # so the sixteen live QA cases were absent from a green nobody could read as
  # incomplete. The runner now prints a verdict per tree.
  scripts/postgres_tier.sh -q
}

do_e2e() {
  # Delegates for the same reason `do_postgres` does: the provisioning gets a
  # caller outside this file and can be tested on its own
  # (tests/test_e2e_slice_runner.py).
  #
  # This is the only stage where the client and the server are both real. Every
  # other one holds one side fixed and fakes the other: `api` runs on a fake
  # repository, `mobile` runs on a fake API, `client-routes` and `contract`
  # compare two files without executing either. A defect that lives in the seam
  # -- a body key the client spells differently from the server, a field the
  # server stopped returning -- is invisible to all of them and green in all of
  # them.
  #
  # Measured 2026-08-30 at 1649c16: nothing ran it. `npm test` prunes
  # `tests/e2e` by construction, the mobile job runs that same `npm test`, and
  # `grep -rn test:e2e` over every .yml, .sh, .py, .json and .md found one
  # definition in package.json and no caller at all.
  scripts/e2e_slice.sh
}

# --- prerequisites --------------------------------------------------------
#
# Answers exactly one of: run it, skip it with a reason, or fail because the
# thing is present but broken. The third case is the workflows' rule and it
# matters most: `apps/mobile` with no lockfile is a defect, not an absence.

check_prereq() {
  case "$1" in
    ruff)
      git rev-parse --git-dir >/dev/null 2>&1 || { echo "không phải git repo"; return 1; }
      # `ruff_changed.sh` is a ratchet, so an empty scope makes it print
      # "nothing for ruff to check" and exit 0 -- correct for the script, and a
      # lie once this file renders it as ĐẠT. `guard-range` refuses the
      # identical empty-range condition one stage above; this is the same
      # refusal for the same reason.
      #
      # It hid a real defect. Measured 2026-08-30 on main at 15b0e5c: standing
      # on origin/main the scope is empty, so this stage said ĐẠT, while the
      # same commit in a clone whose merge base was one commit back said HỎNG
      # over three files `ruff format` rejects. The moment you most want to ask
      # "is main clean?" was the moment the stage could not answer.
      #
      # Only a confident empty answer skips. No base, or the script erroring,
      # falls through and runs the body -- which reports the real problem far
      # more loudly than a skip line. A prereq check may turn a run into a skip
      # only when it is certain there is nothing to do.
      local rbase rlist
      rbase="$(guard_range_base)"
      [ -n "$rbase" ] || return 0
      rlist="$(scripts/ruff_changed.sh --list "$rbase" 2>/dev/null)" || return 0
      [ -n "$rlist" ] && return 0
      # An empty scope means ruff itself has nothing to lint. It does NOT mean
      # the stage has nothing to do: `do_ruff` opens with an assertion that has
      # no file list in it at all, and skipping here hid it for a whole day --
      # see ruff_pin() above for the measurement. So the last question before
      # skipping is the scopeless one, and a missing pin sends the run into the
      # body, where it fails with the name of the file that is actually wrong.
      #
      # Deliberately not answered here with `return 1`: a prereq failure is a
      # skip line and no log. The pin deserves a HỎNG with its reason printed,
      # which only the stage body can produce.
      [ -n "$(ruff_pin)" ] || return 0
      echo "nhánh không đổi file Python nào so với origin/main -- ruff không kiểm được gì"
      return 1 ;;
    guard-range)
      git rev-parse --git-dir >/dev/null 2>&1 || { echo "không phải git repo"; return 1; }
      # No base: let the body fail loudly rather than skipping quietly here.
      # An unanswerable question is a failure, not an absence.
      local base; base="$(guard_range_base)"
      [ -n "$base" ] || return 0
      # An empty range scans zero files and exits 0 -- "passed commit range: 0
      # file scan(s)". That is a pass this file must never hand out: it is the
      # green-because-nothing-ran shape, reproduced inside the stage meant to
      # stop it. On `main` itself there genuinely is nothing to scan, so the
      # honest answer is a skip with a reason, and --strict makes it loud.
      [ "$(git rev-list --count "$base"..HEAD)" -gt 0 ] || {
        echo "nhánh không thêm commit nào trên origin/main -- không có gì để quét"; return 1; } ;;
    contract)
      # Needs both sides of the contract. Without `apps/mobile` there is no
      # client to check and skipping is the honest answer; with it present but
      # no `src`, the checker itself would find nothing and report green, so
      # that case is a defect and refuses to skip.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -d apps/mobile/src ] || return 2
      python3 -c "import fastapi" 2>/dev/null || {
        echo "chưa cài fastapi (pip install -r services/api/requirements-dev.txt)"; return 1; } ;;
    client-routes)
      # Same two halves as `contract`, same reasoning for each outcome. The
      # question asked of them is different: `contract` asks whether a call
      # sends X-Actor-ID, this one asks whether the path it calls exists.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -d apps/mobile/src ] || return 2
      python3 -c "import fastapi" 2>/dev/null || {
        echo "chưa cài fastapi (pip install -r services/api/requirements-dev.txt)"; return 1; } ;;
    server-routes)
      # Same two halves as `client-routes`, asked the other way round. The
      # "present but no src" case is a defect here for a sharper reason than
      # elsewhere: with no client source to read, EVERY route on the server
      # looks uncalled, so a reader that skipped would be replaced by one that
      # reports 69 findings. The checker refuses that itself by exiting 2 when
      # it can read no path at all, and this refuses to skip past it.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -d apps/mobile/src ] || return 2
      python3 -c "import fastapi" 2>/dev/null || {
        echo "chưa cài fastapi (pip install -r services/api/requirements-dev.txt)"; return 1; } ;;
    screens)
      # Same two halves as the three stages above, and no fastapi: this one
      # reads client source only, so the API side is irrelevant to it.
      #
      # "Present but no screens" is a defect rather than a skip, and for the
      # sharpest version of the reason given above: with no screen file to
      # read, every screen is vacuously reachable and the run prints 0/0 and
      # exits 0 -- the green-because-nothing-ran shape, inside the stage that
      # exists to catch unreachable code. The checker refuses it itself by
      # exiting 2 on an empty read; this refuses to skip past it.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -d apps/mobile/src/screens ] || return 2 ;;
    cors)
      # Same two halves again, third question. `apps/mobile` absent is an
      # absence; present with no `src` is a defect, because a reader that
      # finds no header at all is the shape this gate exists to refuse -- and
      # the checker says so itself by exiting 2 rather than 0.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -d apps/mobile/src ] || return 2
      python3 -c "import fastapi" 2>/dev/null || {
        echo "chưa cài fastapi (pip install -r services/api/requirements-dev.txt)"; return 1; } ;;
    demo-watch)
      # Only this machine hosts the demo. On a CI runner or a fresh clone there
      # is no box on 8099 and no crontab of ours, so the question is meaningless
      # and the stage says so out loud instead of being red for everyone forever
      # -- which is how the `guard history` variant would have died.
      #
      # Two signals, either one enough, because they fail in opposite
      # directions. The crontab block says "this machine took on the job of
      # watching"; that alone must keep the stage running even while the box is
      # down, since a demo that stopped answering is exactly what wants
      # reporting. The live port says "there is a demo here"; that alone keeps
      # the stage running on a host that has one but never installed the
      # schedule -- the state this repo was in when 8099 drifted twice.
      #
      # The hole left: kill the container AND clear the crontab and this skips.
      # It is a skip with a printed reason, and --strict turns it into a
      # failure, which is the most this file can honestly claim.
      [ -f scripts/demo_watch.py ] || return 2
      if ! crontab -l 2>/dev/null | grep -q 'mobile-demo-watch'; then
        (exec 3<>/dev/tcp/127.0.0.1/8099) 2>/dev/null || {
          echo "máy này không dựng demo: không có khối cron canh gác, và 8099 không trả lời"
          return 1
        }
      fi ;;
    hero-walk)
      # Only this machine hosts the demo, so on a CI runner or a fresh clone the
      # question is meaningless and the stage says so rather than being red for
      # everyone forever. Deleting the runner is a different matter: that is the
      # one edit that must not turn this green.
      [ -f scripts/hero_walk.sh ] || return 2
      (exec 3<>/dev/tcp/127.0.0.1/8099) 2>/dev/null || {
        echo "máy này không dựng demo: 8099 không trả lời"
        return 1
      } ;;
    shared)
      have node || { echo "không có node"; return 1; }
      [ -d packages/shared ] || { echo "packages/shared không có trên nhánh này"; return 1; }
      [ -f packages/shared/money.test.mjs ] || return 2 ;;
    mobile)
      have npx || { echo "không có npx"; return 1; }
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      [ -f apps/mobile/package-lock.json ] || return 2
      [ -d apps/mobile/node_modules ] || { echo "chưa 'npm ci' trong apps/mobile"; return 1; } ;;
    pinned-import|docker)
      have docker || { echo "không có docker"; return 1; }
      docker info >/dev/null 2>&1 || { echo "docker daemon không chạy"; return 1; } ;;
    postgres)
      # An explicitly given URL still wins: somebody who aimed this at a
      # database on purpose is not to be second-guessed.
      #
      # Otherwise `scripts/postgres_tier.sh` makes one. The old rule here was
      # "only an explicitly given URL", and its reason was right -- guessing a
      # connection string would have pointed the tier at the shared
      # `mobile-local` database that every worktree on this machine uses. But
      # the conclusion cost more than it saved: the stage skipped on every run,
      # so 224 cases that are the only proof of any SQL, index, view or trigger
      # in this repository never executed. Provisioning has nothing to guess --
      # a container of its own, on a random loopback port, deleted on the way
      # out -- so the collision that rule protected against cannot happen.
      [ -n "${MOBILE_TEST_DATABASE_URL:-}" ] && return 0
      have docker || {
        echo "không có docker và chưa đặt MOBILE_TEST_DATABASE_URL"; return 1; }
      docker info >/dev/null 2>&1 || {
        echo "docker daemon không chạy và chưa đặt MOBILE_TEST_DATABASE_URL"; return 1; }
      docker image inspect "${MOBILE_TEST_POSTGRES_IMAGE:-postgres:16-alpine}" >/dev/null 2>&1 || {
        echo "chưa có ảnh postgres tại máy (docker pull postgres:16-alpine)"; return 1; } ;;
    e2e)
      # Needs both sides for real, so it asks for more than any other stage:
      # the client to drive, a Python that can serve the API, and Docker for
      # the database. Each missing piece is an absence and skips honestly.
      [ -d apps/mobile ] || { echo "apps/mobile không có trên nhánh này"; return 1; }
      # Present but missing the slice itself is a defect, not an absence.
      # Deleting the one file that proves client and server connect must never
      # be the thing that turns this stage green.
      [ -f apps/mobile/tests/e2e/vertical-slice.test.mjs ] || return 2
      have npm || { echo "không có npm"; return 1; }
      [ -d apps/mobile/node_modules ] || { echo "chưa 'npm ci' trong apps/mobile"; return 1; }
      python3 -c "import fastapi, uvicorn, alembic" 2>/dev/null || {
        echo "chưa cài fastapi/uvicorn/alembic (pip install -r services/api/requirements-dev.txt)"; return 1; }
      have docker || { echo "không có docker"; return 1; }
      docker info >/dev/null 2>&1 || { echo "docker daemon không chạy"; return 1; }
      docker image inspect "${MOBILE_TEST_POSTGRES_IMAGE:-postgres:16-alpine}" >/dev/null 2>&1 || {
        echo "chưa có ảnh postgres tại máy (docker pull postgres:16-alpine)"; return 1; } ;;
  esac
  return 0
}

# The "present but broken" message, kept next to the rule it enforces.
broken_why() {
  case "$1" in
    contract|client-routes|server-routes) echo "apps/mobile có mặt nhưng thiếu src/ -- từ chối bỏ qua" ;;
    screens) echo "apps/mobile có mặt nhưng thiếu src/screens -- 0/0 màn không phải ĐẠT" ;;
    shared) echo "packages/shared có mặt nhưng thiếu money.test.mjs -- từ chối bỏ qua" ;;
    mobile) echo "apps/mobile có mặt nhưng thiếu package-lock.json -- từ chối bỏ qua" ;;
    e2e) echo "apps/mobile có mặt nhưng thiếu tests/e2e/vertical-slice.test.mjs -- từ chối bỏ qua" ;;
    demo-watch) echo "thiếu scripts/demo_watch.py -- xoá canh gác không được biến chặng này thành xanh" ;;
    hero-walk) echo "thiếu scripts/hero_walk.sh -- xoá bài đi bộ không được biến chặng này thành xanh" ;;
    *) echo "thiếu file mà chặng này cần -- từ chối bỏ qua" ;;
  esac
}

# --- run ------------------------------------------------------------------

echo "Cổng chạy tại máy — cùng các lệnh mà .github/workflows chạy."
echo "HEAD $(git rev-parse --short HEAD 2>/dev/null || echo '?')  chặng: ${SELECTED[*]}$([ "$STRICT" -eq 1 ] && echo '  [strict]')"

for stage in "${SELECTED[@]}"; do
  banner "$stage"
  why="$(check_prereq "$stage")"; prereq=$?
  if [ "$prereq" -eq 2 ]; then
    # Present but broken. Never a skip.
    fail_noran "$stage" "$(broken_why "$stage")"
    continue
  fi
  if [ "$prereq" -ne 0 ]; then
    if [ "$STRICT" -eq 1 ]; then
      fail_noran "$stage" "strict: bỏ qua bị tính là hỏng -- $why"
    else
      skip "$stage" "$why"
    fi
    continue
  fi
  # The subshell isolates cwd (`do_mobile` cd's into apps/mobile). PIPESTATUS
  # rather than `$?`: `$?` after a pipe is tee's status, which is 0 even when
  # the stage failed -- a gate that reads the wrong exit code is worse than no
  # gate, because it reports green with evidence scrolling past saying red.
  start=$SECONDS
  ( cd "$REPO_ROOT" && "do_$stage" ) 2>&1 | tee "$LOG_DIR/$stage.log"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 0 ]; then
    pass "$stage" "$((SECONDS - start))"
  else
    fail "$stage" "$((SECONDS - start))"
  fi
done

# --- summary --------------------------------------------------------------

echo
echo "================ TỔNG KẾT ================"
printf 'ĐẠT %d   HỎNG %d   BỎ QUA %d\n' "${#PASSED[@]}" "${#FAILED[@]}" "${#SKIPPED[@]}"
[ ${#PASSED[@]}  -gt 0 ] && echo "  đạt:     ${PASSED[*]}"
[ ${#FAILED[@]}  -gt 0 ] && echo "  hỏng:    ${FAILED[*]}"
if [ ${#SKIPPED[@]} -gt 0 ]; then
  echo "  bỏ qua:"
  for w in "${SKIP_WHY[@]}"; do echo "    $w"; done
  echo
  echo "BỎ QUA KHÔNG PHẢI ĐẠT. Trước khi merge chạy lại với --strict."
fi

# --- verdict: did this run test what actually ships? ----------------------
#
# Every stage above answers "did the thing I ran work". None of them answers
# "was the thing I ran the thing that ships", and on 2026-08-30 the difference
# cost the team a morning: 2305 pytest cases green on fastapi 0.135.3 while the
# image, on the pinned 0.115.6, could not import the app at all. The demo
# machine stayed dead for hours.
#
# The lead's response was a rule held in a person's head -- "a PR that changes a
# route declaration does not merge until the docker stage is green". That is the
# right rule and the wrong enforcement: it had already been skipped on nearly
# every backend PR for two days, by the person who wrote it, because `pytest`
# and the mutation table were green and there was no reason on screen to run
# anything more. This block is that rule with the person taken out of it.
#
# The shape it refuses: a green that was earned on different software. It fires
# only when the run actually claims something about the application code --
# `guard` alone says nothing about libraries and must stay green without docker.
#
# It is deliberately NOT a stage. A stage can be deselected, and the hole being
# closed here IS deselection: `scripts/gate.sh api` printed "ĐẠT 1 HỎNG 0" and
# exited 0 while the tree could not boot. So the check runs on every invocation
# that reaches a verdict, costs milliseconds, and needs nothing but python3.
in_list() {
  local needle="$1" x
  shift
  for x in "$@"; do [ "$x" = "$needle" ] && return 0; done
  return 1
}

# Stages whose green is read as "the application code works".
DRIFT_CODE_TIERS=(api migration postgres e2e)
# Stages that load the app under the versions the image installs, and are
# therefore the only ones whose green survives a drifted machine.
DRIFT_SHIPPING_PROOF=(pinned-import docker)

drift_ran_code_tier=0
drift_proved_shipping=0
for s in ${PASSED[@]+"${PASSED[@]}"}; do
  in_list "$s" "${DRIFT_CODE_TIERS[@]}" && drift_ran_code_tier=1
  in_list "$s" "${DRIFT_SHIPPING_PROOF[@]}" && drift_proved_shipping=1
done

DRIFT_STATE="not-applicable"
DRIFT_NAMES=""
if [ "$drift_ran_code_tier" -eq 1 ]; then
  DRIFT_NAMES="$(python3 scripts/check_pin_drift.py --names-only 2>/dev/null)"
  case $? in
    0) DRIFT_STATE="clean" ;;
    1) DRIFT_STATE="drift" ;;
    # Could not measure. Never a silent pass -- an unreadable requirements file
    # or a python3 that cannot import its own metadata is a broken gate, and a
    # broken gate reporting green is the thing this whole file exists against.
    *) DRIFT_STATE="unknown" ;;
  esac
fi

DRIFT_BLOCKS=0
if [ "$DRIFT_STATE" = "drift" ] && [ "$drift_proved_shipping" -eq 0 ]; then
  DRIFT_BLOCKS=1
fi
[ "$DRIFT_STATE" = "unknown" ] && DRIFT_BLOCKS=1

# The escape hatch exists because the alternative is worse. A machine with no
# docker cannot run `pinned-import` at all, and a gate that is red with no way
# out on such a machine gets deleted within a day -- `do_guard-range` says the
# same thing about `repo_guard.py history` a few hundred lines up. So the way
# past is explicit, printed, and recorded in the summary a merge reads. It is
# not silent, which is the only property that matters.
if [ "$DRIFT_BLOCKS" -eq 1 ] && [ "${MOBILE_GATE_ALLOW_DRIFT:-0}" = "1" ]; then
  DRIFT_BLOCKS=0
  DRIFT_STATE="drift-waived"
fi

# The same counts, for a program rather than a person.
#
# `scripts/gate_merge.sh` has to tell "every stage ran and passed" apart from
# "the stages that mattered most never ran", and until now the only channel it
# had was the block above -- coloured, localised, written for a reader. It did
# not parse it, so it could not tell, so it printed an unconditional green over
# the top of the "BỎ QUA KHÔNG PHẢI ĐẠT" line three lines above its own verdict.
# Measured 2026-08-30 at ef2f5e8: `gate_merge.sh -- guard postgres e2e` with the
# postgres image unresolvable ran one stage, skipped `e2e` and `postgres`, and
# ended "ĐẠT gộp ... cho cây xanh", exit 0.
#
# Making the caller grep this banner would have made a merge decision depend on
# the wording of a heading. So the counts get a second, stable channel, and the
# reader is required to treat an absent or unparseable file as "cannot tell"
# rather than as "nothing was skipped" -- a caller that reads silence as good
# news rebuilds the exact bug this closes.
#
# Written before the exits below so every path reports: the failure path, the
# all-passed path, and the "nothing ran at all" path, which is the one whose
# count of zero is most easily misread as calm.
if [ -n "${GATE_SUMMARY_FILE:-}" ]; then
  {
    printf 'passed=%d\n' "${#PASSED[@]}"
    printf 'failed=%d\n' "${#FAILED[@]}"
    printf 'skipped=%d\n' "${#SKIPPED[@]}"
    for s in ${PASSED[@]+"${PASSED[@]}"}; do printf 'passed-stage=%s\n' "$s"; done
    for s in ${FAILED[@]+"${FAILED[@]}"}; do printf 'failed-stage=%s\n' "$s"; done
    # The reason travels with the name. A caller that can only print "2 chặng
    # bỏ qua" sends the reader back here to find out which and why.
    for w in ${SKIP_WHY[@]+"${SKIP_WHY[@]}"}; do printf 'skipped-stage=%s\n' "$w"; done
    # A merge decision needs to know the run tested what ships, not only that
    # it was green. Absent key = old gate.sh; the reader must treat that as
    # "cannot tell" rather than "clean", the same rule as the counts above.
    printf 'pin-drift=%s\n' "$DRIFT_STATE"
    for n in $DRIFT_NAMES; do printf 'pin-drift-name=%s\n' "$n"; done
  } > "$GATE_SUMMARY_FILE"
fi

# Guard the guard. If every stage was filtered away, the run proved nothing,
# and exiting 0 here would be this file committing the sin it was written for.
if [ ${#PASSED[@]} -eq 0 ] && [ ${#FAILED[@]} -eq 0 ]; then
  echo "Không chặng nào CHẠY -- cổng này không chứng minh gì cả." >&2
  exit 2
fi

if [ ${#FAILED[@]} -gt 0 ]; then
  ran_and_logged=0
  for f in "${FAILED[@]}"; do
    echo
    why="$(noran_why "$f")"
    if [ -n "$why" ]; then
      # Never started, so there is no log and never will be. Say that, rather
      # than printing a header promising thirty lines and then nothing --
      # silence under a promise of evidence reads as "ran, said nothing", which
      # is the opposite of what happened.
      echo "---- chặng hỏng: $f -- KHÔNG CHẠY, nên không có log ----"
      echo "$why"
    elif [ -f "$LOG_DIR/$f.log" ]; then
      echo "---- 30 dòng cuối của chặng hỏng: $f ----"
      tail -30 "$LOG_DIR/$f.log"
      ran_and_logged=1
    else
      # Neither ran-with-a-log nor recorded as never-run: the bookkeeping above
      # missed a path. Better to admit the gap than to print an empty block.
      echo "---- chặng hỏng: $f -- KHÔNG CHẠY hay mất log, cổng không biết ----"
      echo "Không có $LOG_DIR/$f.log và cũng không ghi được lý do. Đây là lỗi của chính scripts/gate.sh."
    fi
  done
  echo
  # Only point at the directory when something is actually in it.
  if [ "$ran_and_logged" -eq 1 ]; then
    echo "Log đầy đủ: $LOG_DIR"
  else
    echo "Không chặng hỏng nào chạy tới mức ghi log, nên $LOG_DIR rỗng."
  fi
  exit 1
fi

if [ "$DRIFT_BLOCKS" -eq 1 ]; then
  echo
  echo "================================================================"
  if [ "$DRIFT_STATE" = "unknown" ]; then
    echo "KHÔNG ĐO ĐƯỢC bản thư viện đang chạy."
    echo
    echo "scripts/check_pin_drift.py không trả lời được, nên cổng này không biết"
    echo "bộ test vừa chạy trên bản nào. Không biết thì không được báo xanh."
    python3 scripts/check_pin_drift.py >&2 || true
  else
    echo "MỌI CHẶNG ĐẠT — NHƯNG KHÔNG PHẢI TRÊN BẢN SẼ SHIP."
    echo
    echo "Các chặng vừa xanh chạy bằng thư viện của MÁY NÀY. Những pin quan"
    echo "trọng dưới đây khác bản mà ảnh cài, và chúng quyết định hành vi ngay"
    echo "lúc import — trước khi một assertion nào kịp chạy:"
    echo
    for n in $DRIFT_NAMES; do echo "    $n"; done
    echo
    echo "Đây đúng là hình dạng đã giết máy demo ngày 30/08: 2305 ca xanh tại"
    echo "chỗ, container không import nổi app. Chặng chứng minh được điều còn"
    echo "thiếu mất khoảng 2 giây:"
    echo
    echo "    scripts/gate.sh ${SELECTED[*]} pinned-import"
    echo
    echo "Máy không có docker thì nói ra chứ đừng lờ đi:"
    echo "    MOBILE_GATE_ALLOW_DRIFT=1 scripts/gate.sh ${SELECTED[*]}"
  fi
  echo "================================================================"
  echo "Log đầy đủ: $LOG_DIR"
  exit 1
fi

rm -rf "$LOG_DIR"
echo "Tất cả chặng đã chạy đều ĐẠT."
if [ "$DRIFT_STATE" = "drift-waived" ]; then
  echo
  echo "LƯU Ý: MOBILE_GATE_ALLOW_DRIFT=1 — pin quan trọng đang lệch và lượt này"
  echo "KHÔNG chứng minh được ảnh sẽ ship chạy được. Đã bỏ qua theo yêu cầu:"
  for n in $DRIFT_NAMES; do echo "    $n"; done
elif [ "$DRIFT_STATE" = "clean" ]; then
  echo "Và đã chạy đúng bản thư viện mà ảnh sẽ cài."
fi
exit 0
