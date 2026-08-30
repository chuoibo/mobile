#!/usr/bin/env bash
#
# Run ruff over the Python files a change actually touches -- and only those.
#
# Why a ratchet and not `ruff check app tests`:
#
# Ruff has been configured in services/api/pyproject.toml for a long time while
# gating nothing, and the debt grew the whole time. Turning on a whole-tree gate
# now would be red on the commit that adds it, so the only ways to land it are
# to reformat the tree or to disable the gate -- and reformatting 76 files
# drowns every real diff underneath it, which is exactly what CLAUDE.md tells
# people not to do. A gate that cannot be landed green is not a gate.
#
# So this checks the files in the diff. Legacy debt stays visible to anyone who
# runs ruff by hand, but it cannot grow: the moment you edit a dirty file, that
# file has to come out clean. That is the same discipline CLAUDE.md already
# asks of humans ("chay ruff tren file minh dang sua"), moved off the honour
# system and onto CI.
#
# Usage:
#   scripts/ruff_changed.sh <base>           compare <base> against the working tree
#   scripts/ruff_changed.sh <base> <head>    compare the merge base against <head>
#   scripts/ruff_changed.sh --list <base>    print what it would check, check nothing
#
# Exit codes: 0 clean (or nothing to check), 1 ruff found problems,
# 2 the script could not determine what to check -- which is a failure, never
# a silent pass.

set -euo pipefail

# `--list` exists so a caller can ask "would you check anything?" before running
# the stage. scripts/gate.sh needs that to tell BỎ QUA from ĐẠT: exiting 0 on an
# empty scope is right for this script and wrong for a gate summary that then
# says every stage passed. It is answered here rather than recomputed by the
# caller because a second copy of the enumeration below -- diff, plus untracked,
# minus paths no longer on disk -- is a copy that drifts.
list_only=0
if [ "${1:-}" = "--list" ]; then
  list_only=1
  shift
fi

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 [--list] <base> [head]" >&2
  exit 2
fi

base="$1"
head="${2:-}"

# A gate that cannot find its tools must say so. Skipping here would report
# green for a check that never ran, which is the failure mode this file exists
# to remove -- not one to reproduce.
#
# And the tool has to be the RIGHT one. This used to take whatever `ruff` was
# first on PATH, which on a developer machine is whatever their editor
# installed. Measured 2026-08-30 over the 320 tracked Python files: the pinned
# ruff 0.9.2 reports 31 findings, this machine's 0.15.15 reports 30, and the
# one it cannot see is UP038 -- a rule later ruff REMOVED -- on
# services/api/app/domain/place_search.py:105. So editing that file got ĐẠT
# locally and would get HỎNG from CI. `scripts/ruff_pinned.sh` resolves the pin
# and provisions it when absent; it exits 2 rather than hand back a different
# version, because a verdict from the wrong tool is not the verdict.
#
# Resolved below rather than here, after the two early exits: `--list` answers
# a question about files and a docs-only change has nothing to lint, and
# neither should have to build a linter first.
# Parameter expansion and two builtins, deliberately: `dirname` is an external
# command, and tests/test_ruff_changed.py runs this with a PATH holding nothing
# but bash and git to prove a toolless runner goes red. Calling `dirname` there
# made this line silently produce the wrong directory instead of the honest
# "cannot get the pinned ruff" -- a resolution bug hiding inside the very check
# meant to catch missing tools. `cd` and `pwd` are builtins and need no PATH.
_here="${BASH_SOURCE[0]%/*}"
[ "$_here" = "${BASH_SOURCE[0]}" ] && _here="."
RUFF_PINNED="$(cd "$_here" && pwd)/ruff_pinned.sh"
unset _here

if ! git rev-parse --verify --quiet "${base}^{commit}" >/dev/null; then
  echo "::error::cannot resolve base ref '${base}'" >&2
  exit 2
fi

# --diff-filter=ACMR drops Deleted. Passing a path that is no longer on disk
# makes ruff exit non-zero for a file the change removed, which would fail the
# gate for doing the right thing.
if [ -n "$head" ]; then
  if ! git rev-parse --verify --quiet "${head}^{commit}" >/dev/null; then
    echo "::error::cannot resolve head ref '${head}'" >&2
    exit 2
  fi
  # Three dots: the files this branch changed, not the ones main moved on to.
  # Two dots would drag in everything merged into main since the branch started
  # and fail the author for other people's files.
  mapfile -t candidates < <(git diff --name-only --diff-filter=ACMR "${base}...${head}" -- '*.py')
else
  # Compare against the merge base, not against the ref itself. Once main has
  # moved ahead of the branch, `git diff main` also reports main's own commits
  # -- inverted, because the working tree does not have them yet. This script
  # caught itself doing exactly that: a backend pull request landed on main
  # mid-session and the gate demanded its author clean up five files they had
  # never opened. The head form below gets this free from `...`; here it has to
  # be spelled out.
  if ! merge_base="$(git merge-base "${base}" HEAD 2>/dev/null)" || [ -z "$merge_base" ]; then
    echo "::error::no merge base between '${base}' and HEAD" >&2
    exit 2
  fi

  # `git diff <ref>` reports tracked files only, so a brand-new file -- the
  # single most likely place for new lint errors -- is invisible to it. An
  # earlier version stopped here and told a developer who had just written a
  # dirty new module that there was nothing to check. Untracked files that git
  # is not ignoring are part of what "changed" means locally.
  mapfile -t candidates < <(
    git diff --name-only --diff-filter=ACMR "${merge_base}" -- '*.py'
    git ls-files --others --exclude-standard -- '*.py'
  )
fi

# Renames and case changes can leave a path in the diff that is not on disk.
files=()
for path in "${candidates[@]}"; do
  [ -n "$path" ] || continue
  [ -f "$path" ] || continue
  files+=("$path")
done

if [ "$list_only" -eq 1 ]; then
  # Empty output and exit 0 is the "nothing in scope" answer. The array guard is
  # for `set -u`, under which expanding an empty array is itself an error.
  [ "${#files[@]}" -eq 0 ] || printf '%s\n' "${files[@]}"
  exit 0
fi

# The trap this early exit exists for: `ruff check` with no path arguments
# checks the ENTIRE tree. Falling through to ruff with an empty array would
# turn every docs-only or TypeScript-only change into a full-tree scan and fail
# it on 76 files the author never opened. Exit before that can happen.
if [ "${#files[@]}" -eq 0 ]; then
  echo "no Python files changed -- nothing for ruff to check"
  exit 0
fi

if ! RUFF="$("$RUFF_PINNED")"; then
  echo "::error::không lấy được bản ruff đã ghim -- từ chối chấm bằng bản khác" >&2
  exit 2
fi

# Named out loud on every run. The previous version printed the mismatch as a
# CHÚ Ý inside gate.sh and passed anyway; saying which binary produced the
# verdict is what makes the verdict checkable after the fact.
_v="$("$RUFF" --version)"; _v="${_v#* }"
echo "ruff ${_v%% *} (bản ghim) tại $RUFF"
unset _v
echo "ruff over ${#files[@]} changed Python file(s):"
printf '  %s\n' "${files[@]}"

# Both halves run even if the first fails, so one push surfaces both lists
# instead of hiding the formatting diff behind the lint errors.
status=0

echo "--- ruff check ---"
"$RUFF" check --no-cache "${files[@]}" || status=1

echo "--- ruff format --check ---"
"$RUFF" format --check --no-cache "${files[@]}" || status=1

if [ "$status" -ne 0 ]; then
  echo "::error::ruff rejected files this change touches -- fix them, or narrow the change"
fi

exit "$status"
