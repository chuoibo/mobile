#!/usr/bin/env bash
#
# Fix the ruff findings on the files this branch changes -- and nothing else.
#
# ## Why this exists
#
# `scripts/ruff_changed.sh` going red stopped five people in one night (backend
# #372, devops #410, qa2 #411, frontend #397, backend #450). That gate now
# prints the exact command to paste, which removes most of the problem. This
# removes the rest: the paste is four lines with file paths in it, and every one
# of the five got stuck on one of the same four details -- `ruff check` versus
# `ruff format`, `$( )` around `ruff_pinned.sh`, the pin versus PATH, and only
# the touched files. This target gets all four right by construction, so the
# answer to "what do I type" is one token that cannot be mistyped into
# something that silently does nothing.
#
# ## Why it does not enumerate the files itself
#
# The scope comes from `ruff_changed.sh --list`, the same enumeration the gate
# grades with. A second copy of "diff against merge base, plus untracked, minus
# paths no longer on disk" is a copy that drifts, and a fixer whose idea of
# scope is wider than the gate's is a fixer that reformats files the author
# never opened -- the exact thing CLAUDE.md forbids and the gate's own message
# warns against.
#
# ## What it will not do
#
# `ruff check --fix` only fixes rules ruff marks `[*]`. Anything else is left
# for a human, and this script exits non-zero when that happens rather than
# reporting success on a tree the gate will still reject. A fix command that
# exits 0 while the gate stays red is worse than no fix command.
#
# Usage:
#   scripts/ruff_fix.sh              fix the files this branch changes
#   scripts/ruff_fix.sh --dry-run    print what it would run, change nothing
#
# Exit codes: 0 the touched files are now clean, 1 findings remain that need a
# human, 2 could not work out what to fix -- never a silent pass.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

dry_run=0
case "${1:-}" in
  "") ;;
  --dry-run) dry_run=1 ;;
  *)
    echo "usage: $0 [--dry-run]" >&2
    exit 2
    ;;
esac

# Same base as `scripts/gate.sh guard_range_base` and the same fallback: fetch
# once if origin/main is not there yet, then give up loudly. Guessing a base
# would silently change which files get rewritten.
base="$(git merge-base origin/main HEAD 2>/dev/null)" || base=""
if [ -z "$base" ]; then
  git fetch --no-tags --quiet origin main 2>/dev/null || true
  base="$(git merge-base origin/main HEAD 2>/dev/null)" || base=""
fi
if [ -z "$base" ]; then
  echo "::error::không tìm được merge base với origin/main -- không biết file nào là của nhánh này" >&2
  echo "Thử: git fetch origin main" >&2
  exit 2
fi

mapfile -t files < <(scripts/ruff_changed.sh --list "$base")
# The array can hold one empty string when the list is empty.
filtered=()
for path in "${files[@]}"; do
  if [ -n "$path" ]; then filtered+=("$path"); fi
done
files=("${filtered[@]+"${filtered[@]}"}")

if [ "${#files[@]}" -eq 0 ]; then
  echo "nhánh này không đổi file Python nào so với origin/main -- không có gì để sửa"
  exit 0
fi

if ! RUFF="$(scripts/ruff_pinned.sh)"; then
  echo "::error::không lấy được bản ruff đã ghim -- từ chối sửa bằng bản khác" >&2
  echo "Sửa bằng bản khác còn tệ hơn không sửa: nó ghi đè file bằng cách format của" >&2
  echo "một bản mà CI không dùng, và cổng sẽ đỏ vì đúng những dòng vừa 'sửa'." >&2
  exit 2
fi

_v="$("$RUFF" --version)"; _v="${_v#* }"
echo "ruff ${_v%% *} (bản ghim) tại $RUFF"
unset _v
echo "so với merge base $base -- ${#files[@]} file nhánh này chạm:"
printf '  %s\n' "${files[@]}"

if [ "$dry_run" -eq 1 ]; then
  echo "--- --dry-run: sẽ chạy, nhưng không ghi gì ---"
  printf '%s check --fix --no-cache' "$RUFF"
  printf ' %q' "${files[@]}"
  printf '\n'
  printf '%s format --no-cache' "$RUFF"
  printf ' %q' "${files[@]}"
  printf '\n'
  exit 0
fi

# `check --fix` first, then `format`: ruff's own documented order. Fixing can
# leave code the formatter wants to rewrite, and doing it the other way round
# ends with a tree the format half of the gate still rejects.
echo "--- ruff check --fix ---"
"$RUFF" check --fix --no-cache "${files[@]}" || true

echo "--- ruff format ---"
"$RUFF" format --no-cache "${files[@]}"

# The verdict comes from the gate, not from this script. Asking the same
# question a second way here would let the two disagree, and the one that
# matters is the one that blocks the merge.
echo "--- chạy lại chính cổng để chấm ---"
if scripts/ruff_changed.sh "$base"; then
  echo "ĐẠT -- các file nhánh này chạm đã sạch với bản ghim"
  exit 0
fi

echo "::error::vẫn còn findings mà ruff không tự sửa được -- phải sửa tay, xem danh sách ngay trên" >&2
exit 1
