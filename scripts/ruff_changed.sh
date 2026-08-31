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
RUFF_VERSION="${_v%% *}"
echo "ruff $RUFF_VERSION (bản ghim) tại $RUFF"
unset _v
echo "ruff over ${#files[@]} changed Python file(s):"
printf '  %s\n' "${files[@]}"

# ## Why the rest of this file is mostly a failure message
#
# This stage stopped five people in one night -- backend #372, devops #410,
# qa2 #411, frontend #397, backend #450 -- and each time a human had to explain
# the same four things by hand:
#
#   1. the red half is usually `ruff format --check`, not `ruff check`, and the
#      two are fixed by two different commands;
#   2. `scripts/ruff_pinned.sh` prints a PATH and lints nothing, so it has to be
#      wrapped in `$( )`; typed bare it exits 64 having checked nothing;
#   3. the verdict is the PINNED ruff's, not that of whatever is on PATH;
#   4. only the files this change touches -- `ruff format` over the tree makes a
#      27-file diff that buries the real change.
#
# All four were already written down: two of them in the headers of this file
# and of ruff_pinned.sh, the other two in CLAUDE.md. None of it was on screen at
# the moment the stage went red, and that is the only moment anybody reads. What
# was on screen was one line -- "::error::ruff rejected files this change
# touches" -- which is a verdict with no instruction in it.
#
# So the four explanations moved to where the failure is, and the exact command
# is printed with the file paths already substituted, fenced so it can be
# selected in one drag. A gate that only punishes teaches the next person
# nothing; five hand-holdings is enough evidence that this one was only
# punishing.
#
# Deliberately printed ONLY on failure. A lesson repeated on every green run is
# a banner, and banners are scrolled past -- which is how the CHÚ Ý this file's
# header describes went unread for a day.
# tests/test_ruff_failure_teaches_the_fix.py holds both halves of that.

# Both halves run even if the first fails, so one push surfaces both lists
# instead of hiding the formatting diff behind the lint errors.
#
# Output is captured as well as printed, because the block below has to name the
# files of the half that FAILED rather than the whole changed set -- telling
# somebody to reformat a file ruff is happy with is the whole-tree mistake in
# miniature. Measured on the pin 2026-08-31: both halves write their findings to
# stdout (`2>&1 >/dev/null` over a dirty file is empty), so stdout is the
# complete record and stderr is left to flow straight through.
status=0
check_out=""
format_out=""

echo "--- ruff check ---"
if check_out="$("$RUFF" check --no-cache "${files[@]}")"; then
  check_failed=0
else
  check_failed=1
  status=1
fi
if [ -n "$check_out" ]; then printf '%s\n' "$check_out"; fi

echo "--- ruff format --check ---"
if format_out="$("$RUFF" format --check --no-cache "${files[@]}")"; then
  format_failed=0
else
  format_failed=1
  status=1
fi
if [ -n "$format_out" ]; then printf '%s\n' "$format_out"; fi

if [ "$status" -eq 0 ]; then
  exit 0
fi

# Parsing ruff's output would be a second source of truth that drifts, so
# everything it yields is checked back against the file list this script already
# built. A name that is not in scope is a parse artefact, not a file: ruff's
# full output renders the offending source line, and a string literal like
# "a:1:2: x" inside it has the same shape as a finding header. Cross-checking
# makes the parse unable to invent a path even if ruff's format changes.
in_scope() {
  local candidate
  for candidate in "${files[@]}"; do
    if [ "$candidate" = "$1" ]; then return 0; fi
  done
  return 1
}

# `in_list <needle> [haystack...]`. One file usually carries several findings,
# and the same file can fail both halves.
in_list() {
  local needle="$1" candidate
  shift
  for candidate in "$@"; do
    if [ "$candidate" = "$needle" ]; then return 0; fi
  done
  return 1
}

# Point 3 is only persuasive if it is measured on the machine reading it. The
# three cases are genuinely different advice, and asserting the mismatch on a
# machine that does not have one would train people to disbelieve the message.
path_ruff_note() {
  local found version
  if ! found="$(command -v ruff 2>/dev/null)" || [ -z "$found" ]; then
    printf 'máy này không có ruff nào trên PATH cả'
    return 0
  fi
  version="$("$found" --version 2>/dev/null)"
  version="${version#* }"
  version="${version%% *}"
  if [ "$version" = "$RUFF_VERSION" ]; then
    printf 'PATH của máy NÀY tình cờ cũng là %s, nhưng máy khác thì không' "$version"
  else
    printf 'PATH của máy này đang là %s, KHÁC bản ghim' "${version:-không chạy được}"
  fi
}

# Builtins only, no grep/sed/awk, for the reason ruff_pinned.sh's pin_line()
# gives: tests/test_ruff_changed.py runs this gate with a PATH holding nothing
# but bash and git, and a failure message that cannot be printed on a bare
# runner is missing at the moment it is needed most.
lint_files=()
format_files=()

# Every `ruff check` finding opens with "<path>:<line>:<col>: <CODE> ...", in
# both the full and the concise output format.
while IFS= read -r line; do
  case "$line" in
    *:[0-9]*:[0-9]*:\ *) path="${line%%:*}" ;;
    *) continue ;;
  esac
  if in_scope "$path" && ! in_list "$path" ${lint_files[@]+"${lint_files[@]}"}; then
    lint_files+=("$path")
  fi
done <<<"$check_out"

# `ruff format --check` prints one "Would reformat: <path>" per file.
while IFS= read -r line; do
  case "$line" in
    "Would reformat: "*) path="${line#Would reformat: }" ;;
    *) continue ;;
  esac
  if in_scope "$path" && ! in_list "$path" ${format_files[@]+"${format_files[@]}"}; then
    format_files+=("$path")
  fi
done <<<"$format_out"

# A half that failed and yielded no filename means the parse missed. Falling
# back to the full changed list keeps the printed command CORRECT -- ruff is a
# no-op on files it is already happy with -- at the cost of being wider than
# necessary, and the widening is said out loud rather than hidden.
narrowed=1
if [ "$check_failed" -eq 1 ] && [ "${#lint_files[@]}" -eq 0 ]; then
  lint_files=("${files[@]}")
  narrowed=0
fi
if [ "$format_failed" -eq 1 ] && [ "${#format_files[@]}" -eq 0 ]; then
  format_files=("${files[@]}")
  narrowed=0
fi

# `ruff check --fix` can leave code that the formatter then wants to rewrite, so
# anything the first command edits goes through the second as well. That is
# ruff's own documented order, and getting it wrong here would print a block
# that leaves the gate red -- the one outcome worse than printing nothing.
if [ "$check_failed" -eq 1 ]; then
  for path in "${lint_files[@]}"; do
    if ! in_list "$path" ${format_files[@]+"${format_files[@]}"}; then
      format_files+=("$path")
    fi
  done
fi

verdict() {
  if [ "$1" -eq 1 ]; then printf 'HỎNG'; else printf 'ĐẠT'; fi
}

{
  echo
  echo "::error::ruff HỎNG trên file nhánh này chạm -- lệnh sửa nằm ngay dưới, dán được luôn"
  echo
  printf '  nửa `ruff check`          : %s\n' "$(verdict "$check_failed")"
  printf '  nửa `ruff format --check` : %s\n' "$(verdict "$format_failed")"
  echo
  echo "=== DÁN TỪ ĐÂY (đứng ở gốc repo) ==="
  echo 'RUFF="$(scripts/ruff_pinned.sh)"'
  if [ "$check_failed" -eq 1 ]; then
    printf '"$RUFF" check --fix'
    printf ' %q' "${lint_files[@]}"
    printf '\n'
  fi
  if [ "${#format_files[@]}" -gt 0 ]; then
    printf '"$RUFF" format'
    printf ' %q' "${format_files[@]}"
    printf '\n'
  fi
  echo "=== ĐẾN ĐÂY ==="
  echo
  echo "Hoặc một lệnh, không cần chép đường dẫn:   make ruff-fix"
  if [ "$narrowed" -eq 0 ]; then
    echo
    echo "(không tách được file nào hỏng từ output của ruff, nên khối trên lấy CẢ" \
      "danh sách file nhánh này đổi. Chạy vẫn đúng -- ruff là no-op trên file nó" \
      "đã hài lòng -- chỉ là rộng hơn mức cần.)"
  fi
  echo
  echo "Bốn điều tối nay đã phải giải thích năm lần. Để sẵn đây cho khỏi phải hỏi:"
  echo
  echo " 1. HAI NỬA, HAI LỆNH. \`ruff check\` bắt lỗi lint; \`ruff format --check\`"
  echo "    bắt cách xuống dòng / nháy / dấu phẩy. Nửa hay đỏ là format, và nó KHÔNG"
  echo "    sửa bằng \`--fix\` -- sửa bằng \`ruff format <file>\` (bỏ \`--check\`)."
  echo "    Xem hai dòng verdict ở trên để biết nửa nào của bạn đang đỏ."
  echo
  echo " 2. \`scripts/ruff_pinned.sh\` IN RA MỘT ĐƯỜNG DẪN, nó không lint gì cả."
  echo "    Phải bọc trong \$( ) đúng như khối trên. Gõ thẳng"
  echo "    \`scripts/ruff_pinned.sh check <file>\` thì nó thoát 64 và KHÔNG kiểm gì --"
  echo "    một dòng ra, không finding, trông y hệt một lượt sạch."
  echo
  printf ' 3. BẢN CHẤM LÀ BẢN GHIM: ruff==%s, ghim ở\n' "$RUFF_VERSION"
  echo "    services/api/requirements-dev.txt -- KHÔNG phải bản trên PATH của bạn"
  printf '    (%s).\n' "$(path_ruff_note)"
  echo "    Hai bản formatter khác nhau cho ra hai kết quả khác nhau, nên \`ruff format\`"
  echo "    gõ trần có thể làm chính cổng này đỏ thêm. Khối trên đã lấy đúng bản ghim."
  echo
  echo " 4. CHỈ FILE BẠN CHẠM, đúng danh sách trong khối trên. ĐỪNG chạy"
  echo "    \`ruff format app tests\`: CLAUDE.md đo cả cây ra 27 file phải sửa, diff đó"
  echo "    nhấn chìm thay đổi thật và làm PR không review được."
  echo
  echo "Còn đỏ sau khi dán? \`check --fix\` chỉ tự sửa được rule có dấu [*] ở output"
  echo "phía trên; phần còn lại phải sửa tay. Chạy lại \`make gate ONLY=ruff\` để xem."
} >&2

exit "$status"
