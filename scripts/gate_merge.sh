#!/usr/bin/env bash
#
# Run the gate on the tree a merge would PRODUCE, not on the branch as it
# stands.
#
# ## The hole this fills
#
# Two things are true at once in this repository, and together they mean no
# merge result has ever been checked before becoming `main`.
#
# First, `test.yml` and `postgres-repository.yml` trigger only on
# `push: branches: [main]`. That was a deliberate trade -- repo-guard.yml says
# so in its own comment: "`test.yml` no longer runs on pull_request (Actions
# billing)". So while Actions was alive, a pull request was gated by the repo
# guard and nothing else; the suite, the postgres tier, docker and the mobile
# bundle all ran *after* the code was already on main. A detector, not a gate.
#
# Second, since 07:45Z on 2026-08-29 Actions does not start jobs at all
# (billing). Measured 2026-08-30: the last 100 runs are 100 failures, 0
# successes, every one of them 3-6 seconds with "The job was not started
# because recent account payments have failed". So the post-merge detector is
# gone too.
#
# `scripts/gate.sh` closed the "the gates cannot execute anywhere" half. It
# runs them on this machine. But it runs them on the tree you are standing in
# -- the branch. A green `make gate` proves "my branch is green", which is not
# the question anyone is actually asking before a merge. The question is
# "will main be green after you merge me", and those differ whenever main has
# moved, which it does constantly: main advanced twice while this file was
# being written.
#
# Git cannot answer it either. Git reports a conflict when two branches edit
# the same lines; it is silent when one branch removes what another branch
# started calling. That semantic conflict has landed on this repository's main
# before. Different files, clean merge, broken tree.
#
# ## What it does
#
#   1. fetches origin, so "main" means main and not a memory of main
#   2. builds merge(branch, base) in a throwaway worktree outside the repo
#   3. runs scripts/gate.sh there -- the MERGED gate on the MERGED tree, which
#      is what GitHub does for a pull_request event
#   4. removes the worktree, whatever happened
#
# A merge that conflicts is a FAIL with the conflicting paths named, not a
# skip. Refusing to answer and answering "fine" must not look alike; that
# confusion is most of what has gone wrong here.
#
# ## Usage
#
#   scripts/gate_merge.sh                  # current branch vs origin/main
#   scripts/gate_merge.sh 210              # pull request #210
#   scripts/gate_merge.sh some/branch      # a branch by name
#   scripts/gate_merge.sh --base other 210 # against something other than main
#   scripts/gate_merge.sh 210 -- api ruff  # only these gate stages
#
# `--base` exists because stacked pull requests do not merge into main -- they
# merge into the branch below them -- and because a gate that cannot be aimed
# at a synthetic base cannot be proven to catch anything.
#
# ## What this does NOT prove
#
# It proves the merge of these two commits is green. It says nothing about the
# merge of three, and main can move between this run and the click. Re-run it
# when main moves; that is the cost of having no CI.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

BASE_REF="origin/main"
TARGET=""
GATE_ARGS=()
NO_FETCH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --base)
      shift
      [ $# -gt 0 ] || { echo "--base cần một ref" >&2; exit 2; }
      BASE_REF="$1"
      ;;
    --no-fetch) NO_FETCH=1 ;;
    --) shift; GATE_ARGS=("$@"); break ;;
    -h|--help) sed -n '2,70p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "Tham số lạ: $1 (xem scripts/gate_merge.sh --help)" >&2; exit 2 ;;
    *)
      [ -n "$TARGET" ] && { echo "Chỉ nhận một nhánh/PR, đã có '$TARGET'" >&2; exit 2; }
      TARGET="$1"
      ;;
  esac
  shift
done

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
die() { printf '\033[31mHỎNG\033[0m  %s\n' "$*" >&2; exit 1; }

# --- resolve what to merge -------------------------------------------------

if [ "$NO_FETCH" -eq 0 ]; then
  # A stale origin/main is the failure this file exists to prevent, so it is
  # not optional by default. --no-fetch is for the offline case and says so.
  git fetch --quiet origin || die "git fetch origin thất bại — không thể biết main đang ở đâu."
fi

HEAD_DESC=""
if [ -z "$TARGET" ]; then
  TARGET="$(git rev-parse --abbrev-ref HEAD)"
  [ "$TARGET" = "HEAD" ] && die "Đang ở detached HEAD — nêu rõ nhánh hoặc số PR."
  HEAD_DESC="nhánh hiện tại $TARGET"
fi

if [ -z "$HEAD_DESC" ] && printf '%s' "$TARGET" | grep -qE '^#?[0-9]+$'; then
  PR_NUM="${TARGET#\#}"
  command -v gh >/dev/null 2>&1 || die "Cần gh để tra PR #$PR_NUM."
  # refs/pull/N/head is the pull request's own tip. Deliberately not
  # refs/pull/N/merge: GitHub computes that one, and it is exactly the thing
  # that is not being computed while Actions is down.
  git fetch --quiet origin "refs/pull/$PR_NUM/head:refs/gate-merge/pr-$PR_NUM" \
    || die "Không fetch được refs/pull/$PR_NUM/head — PR có tồn tại không?"
  TARGET="refs/gate-merge/pr-$PR_NUM"
  HEAD_DESC="PR #$PR_NUM"
fi

[ -n "$HEAD_DESC" ] || HEAD_DESC="ref $TARGET"

HEAD_SHA="$(git rev-parse --verify "$TARGET^{commit}" 2>/dev/null)" \
  || die "Không phân giải được '$TARGET' thành một commit."
BASE_SHA="$(git rev-parse --verify "$BASE_REF^{commit}" 2>/dev/null)" \
  || die "Không phân giải được base '$BASE_REF' thành một commit."

say "=== cái sắp được gộp ==="
printf 'nhánh   %s\n        %s\n' "$HEAD_DESC" "$HEAD_SHA"
printf 'base    %s\n        %s\n' "$BASE_REF" "$BASE_SHA"

if git merge-base --is-ancestor "$HEAD_SHA" "$BASE_SHA"; then
  # Not a pass and not a failure of the tree: there is no merge to check. Say
  # which, because "nothing to do" reported as ĐẠT is how an empty scope came
  # to look like a clean one.
  printf '\n\033[33mKHÔNG CÓ GÌ ĐỂ GỘP\033[0m  %s đã nằm trong %s.\n' "$HEAD_DESC" "$BASE_REF"
  echo "Cổng không chạy. Đây không phải ĐẠT."
  exit 3
fi

BEHIND="$(git rev-list --count "$HEAD_SHA..$BASE_SHA")"
AHEAD="$(git rev-list --count "$BASE_SHA..$HEAD_SHA")"
printf 'nhánh thêm %s commit; base đi trước nhánh %s commit\n' "$AHEAD" "$BEHIND"
if [ "$BEHIND" -eq 0 ]; then
  echo "Base chưa đi trước — kết quả gộp trùng chính nhánh, cổng này bằng scripts/gate.sh."
fi

# --- build the merge in a throwaway worktree -------------------------------

# Outside the repository on purpose: the repo guard scans the tree it is
# standing in, and a second checkout nested inside would be scanned as content.
WT="$(mktemp -d -t gate-merge-XXXXXX)"
cleanup() {
  cd "$REPO_ROOT" || return
  git worktree remove --force "$WT" >/dev/null 2>&1
  rm -rf "$WT"
  git worktree prune >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

rm -rf "$WT"
git worktree add --detach "$WT" "$HEAD_SHA" >/dev/null 2>&1 \
  || die "Không dựng được worktree tạm tại $WT."

say "=== dựng kết quả gộp ==="
MERGE_OUT="$(cd "$WT" && git -c user.name=gate -c user.email=gate@local \
  merge --no-ff --no-edit "$BASE_SHA" 2>&1)"
MERGE_RC=$?

if [ "$MERGE_RC" -ne 0 ]; then
  echo "$MERGE_OUT"
  CONFLICTS="$(cd "$WT" && git diff --name-only --diff-filter=U)"
  printf '\n\033[31mHỎNG\033[0m  gộp xung đột — cổng không chạy được.\n'
  echo "File xung đột:"
  printf '%s\n' "$CONFLICTS" | sed 's/^/  /'
  echo
  echo "Đây là HỎNG chứ không phải bỏ qua: nhánh này chưa gộp được vào $BASE_REF."
  exit 1
fi

MERGE_SHA="$(cd "$WT" && git rev-parse HEAD)"
echo "gộp sạch, không xung đột"
printf 'cây được kiểm  %s  (merge %s ⊕ %s)\n' \
  "${MERGE_SHA:0:12}" "${HEAD_SHA:0:12}" "${BASE_SHA:0:12}"

# The mobile stage runs `npx --no-install`, so it needs the dependency tree. A
# symlink breaks `expo export` (it resolves through the link and walks out of
# the checkout); a hardlink farm is cheap and behaves like a real directory.
if [ -d "$REPO_ROOT/apps/mobile/node_modules" ] && [ -d "$WT/apps/mobile" ]; then
  if cp -al "$REPO_ROOT/apps/mobile/node_modules" "$WT/apps/mobile/node_modules" 2>/dev/null; then
    echo "node_modules: nối cứng từ cây gọi lệnh"
  else
    echo "node_modules: KHÔNG nối được — chặng mobile sẽ tự báo, đừng đọc nó thành sạch" >&2
  fi
fi

# --- run the gate on the merged tree ---------------------------------------

say "=== chạy cổng trên cây đã gộp ==="
echo "(scripts/gate.sh của chính cây đã gộp — bản vá cổng nằm trong nhánh cũng được tính)"

( cd "$WT" && ./scripts/gate.sh "${GATE_ARGS[@]+"${GATE_ARGS[@]}"}" )
GATE_RC=$?

say "=== kết luận ==="
printf 'đo tại   %s  (kết quả gộp, không tồn tại trên remote)\n' "${MERGE_SHA:0:12}"
printf 'gồm      %s = %s\n' "$HEAD_DESC" "${HEAD_SHA:0:12}"
printf '         %s = %s\n' "$BASE_REF" "${BASE_SHA:0:12}"
if [ "$GATE_RC" -eq 0 ]; then
  printf '\033[32mĐẠT\033[0m  gộp %s vào %s cho cây xanh.\n' "$HEAD_DESC" "$BASE_REF"
  echo "Có giá trị cho đúng $BASE_REF ở trên. Base nhích một commit là phải chạy lại."
else
  printf '\033[31mHỎNG\033[0m  gộp %s vào %s cho cây ĐỎ (gate.sh thoát %s).\n' \
    "$HEAD_DESC" "$BASE_REF" "$GATE_RC"
  echo "Nhánh có thể vẫn xanh khi đứng một mình — chênh lệch đó chính là lý do file này tồn tại."
fi
exit "$GATE_RC"
