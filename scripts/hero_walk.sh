#!/usr/bin/env bash
#
# Walk the whole hero path against a running box, INCLUDING the scan seam that
# no other gate crosses.
#
# ## The hole this closes
#
# The hero path the product is being built to demonstrate is
#
#     ảnh bill -> Gemini đọc món -> gán món -> chia tiền -> đợt thu -> trang khách
#
# and on 2026-08-30 at d4f6f91 it was proven by two pieces that do not touch:
#
#   - `apps/mobile/tests/e2e/duong-bill.test.mjs` is gated (the `e2e` stage runs
#     it on a stack it provisions) but starts at `toBill()` -- a `reading`
#     written by hand in the test file. It never calls `scanReceipt`. Its case
#     names mention bills, so reading the list suggests the photo step is
#     covered; `grep -n scanReceipt apps/mobile/tests/e2e/*.test.mjs` returns
#     nothing.
#   - `apps/mobile/tests/receipt.test.mjs` exercises `readingFromWire` fifteen
#     times, all of them against `LIVE_SCAN` -- a wire body captured from a
#     server on 2026-08-29 and frozen into the file. A server that changed its
#     response shape today leaves every one of them green.
#   - `services/api/tests/live/test_gemini_receipt.py` does read real images
#     with the real model, and stops there: it never posts the result to
#     `/bills`. It is also opt-in behind `MOBILE_LIVE_GEMINI=1`, and
#     `grep -rn MOBILE_LIVE_GEMINI` over the whole tree finds only that file --
#     no `scripts/`, no `.github/`. Nothing schedules it.
#
# So the joint -- `POST /receipts/scan` -> `readingFromWire()` -> `POST /bills`
# -- had no caller in any gate. That is the exact shape that broke this product
# twice: #235 and #247 each tightened an active-membership rule, the backend
# suite stayed green, the client suite stayed green, and the two together
# answered 422 to everybody. Two green halves do not add up to a path.
#
# `tests/qa/qa-tt-0031/di-bo-hero-tren-demo.mjs` does walk the joint, end to
# end, through the compiled client. Measured before this script existed:
#
#     grep -rn "di-bo-hero-tren-demo" Makefile scripts .github services
#     -> no match
#
# It ran when somebody remembered. This script is the caller it never had.
#
# ## What it proves, and what it does not
#
# Proves: on the box named by --url, a photograph reaches the model, the lines
# come back in the shape the assignment screen consumes, and that same reading
# survives all the way to a guest page and a confirmed receipt -- driven by
# `dist-test/api.js`, the same compiled client the screens import.
#
# Does NOT prove:
#   - anything about THIS branch's server. The client is rebuilt from this tree
#     (see below), the server is whatever is running on --url. That pairing is
#     the point when --url is the demo box, and it is why the run prints both
#     sides' provenance instead of one SHA.
#   - that the model reads any particular wording. Assertions are on shape and
#     on integer money, never on the model's strings; a test that pins "Lẩu
#     Thái" tests the model, not the product.
#   - CORS. `node`'s fetch does not enforce it, same blind spot as every other
#     gate here.
#   - anything about a second image. One bill, one reading, one run.
#   - that the tree being gated still walks. `--status` binds the verdict to an
#     ANCESTOR of HEAD, so commits added after the walk are covered by nothing.
#     It rules out borrowed evidence, not staleness within the branch.
#   - that anything git does not track holds the same bytes here as where the
#     walk ran. `tree` is built from `git status`, so gitignored paths are
#     outside it by construction. What IS checked is the PRESENCE of the
#     out-of-git artifacts the walk cannot start without (`ngoai_git`), so a
#     verdict can no longer be lent to a tree that has never run `npm ci`.
#     Their CONTENT is not: two trees whose `node_modules` were installed from
#     different lockfiles read alike here. Hashing them would mean hashing
#     `node_modules` on every gate run and putting a real `.env` into a digest,
#     which repo rules forbid outright -- so this is a boundary chosen with the
#     cost named, not a corner nobody looked at.
#   - that a walk measured over uncommitted edits says anything about a commit.
#     It no longer PRETENDS to: the verdict records the tree state next to the
#     sha, and `--status` refuses to lend a dirty walk to any other tree. What
#     it still cannot do is tell you which of your edits carried the green.
#
# ## Why it pins the URL instead of letting the client default
#
# `BASE_URL` in `src/api.ts` falls back to `http://localhost:8099`, which is the
# shared demo stack every worktree on this machine can reach. A gate that
# reached it by *default* would report a colour about code nobody can attribute.
# This script sets `EXPO_PUBLIC_API_URL` explicitly and prints it, so the target
# is a decision on the record rather than a fallback.
#
# ## Why it rebuilds the client
#
# `dist-test/` is gitignored build output and can be older than `src/`. Walking
# with a stale `dist-test` measures a client that no longer exists in any tree
# -- the "bundle from a different SHA" mistake. The build here is the same one
# `npm run test:e2e` does.
#
# ## Why a run records a verdict, and why `--status` is the thing in the gate
#
# This walk costs a live Gemini call and about ten seconds. `make gate` runs
# dozens of times a day, so putting the live walk in the default list would
# either burn model quota all day or -- more likely -- get the stage deleted the
# first week. Leaving it OUT of the default list is worse: a gate nobody calls
# is decoration, which is the hole this file exists to close, reproduced.
#
# `scripts/demo_watch.py` already settled this shape here: run the expensive
# measurement on demand, RECORD the verdict, and have the cheap default stage
# assert the recording is recent and about the right target. A stale or missing
# verdict is red, so "nobody has walked the hero path today" is visible in every
# gate run instead of being nothing at all.
#
# "The right target" is two things, and the first cut of this file only checked
# one. `url` says which BOX was walked; `sha` says which CLIENT. The sha was
# recorded and printed on the pass line but compared to nothing, so a walk on
# any other branch -- or a sha this repo has never heard of -- vouched for
# whatever tree the gate stood in. With one verdict dir shared by every worktree
# on this machine, that is the ordinary case, not a contrived one. `--status`
# now requires the recorded sha to be an ANCESTOR of HEAD.
#
# Ancestor rather than equal on purpose: pinning to HEAD would spend a model
# call on every docs commit, and a stage that expensive gets deleted -- the
# outcome this whole section is arranged to avoid. So the check refuses a walk
# this tree does not contain, and does NOT claim the commits added since the
# walk keep the seam working. That weaker promise is written down below rather
# than left for a reader to assume the stronger one.
#
# ## Why `--ref` exists: HEAD is the wrong subject for the question people ask
#
# Everything above binds the verdict to HEAD -- the HEAD of whatever directory
# the command was typed in. That is right for a gate running on a branch, and it
# has one blind half. The person who walks the path is standing on their own
# branch, so they see green. Nobody is standing on `origin/main`, so nobody asks
# about it, and there was no way to ask: `--status` cannot be pointed anywhere.
#
# Measured 2026-08-31T20:35+0700, which is what prompted this:
#
#     scripts/gate.sh hero-walk            (branch devops, HEAD e069be1)
#       -> HỎNG  "client 7b8fed8, KHÔNG nằm trong HEAD e069be1"
#     git merge-base --is-ancestor 7b8fed8 origin/main
#       -> 1     (7b8fed8 is on backend/split-..., never merged)
#
# So the only hero-path evidence on this machine was about an unmerged branch,
# `origin/main` had none, and on the branch that DID walk it the gate read
# green. An asymmetric hole again, and asymmetric holes survive because the half
# that works reads as proof the whole thing works.
#
# `--ref <ref>` moves the subject from a directory to a commit. It skips the
# checks that read the current directory -- a commit does not acquire
# uncommitted edits, lose its `node_modules`, or stop existing when a temporary
# worktree is deleted -- and pays for them with a rule working-tree mode does
# not have: `tree` must be `clean`, because a walk over uncommitted edits ran
# code that lives in no commit and so vouches for none. The trade is stated at
# the check itself, not only here.
#
# Usage:
#   scripts/hero_walk.sh                      walk the demo box on 8099
#   scripts/hero_walk.sh --url http://h:1234  another box
#   scripts/hero_walk.sh --anh /tmp/x/ro.jpg  another bill image
#   scripts/hero_walk.sh --status             what did the last walk say
#   scripts/hero_walk.sh --status --ref origin/main
#                                             ...about THAT COMMIT rather than
#                                             about this directory. See below.
#   scripts/hero_walk.sh --van-tay            what this runner thinks the
#                                             working tree is right now
#   scripts/hero_walk.sh --ngoai-git          what the walk needs that git does
#                                             not track, and whether it is here
#
# Exit: 0 walk green · 1 a precondition is genuinely absent · 2 something that
# should be here is missing or broken (refuse to skip), or the walk failed.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

URL="http://127.0.0.1:8099"
ANH=""
WALK="$REPO_ROOT/tests/qa/qa-tt-0031/di-bo-hero-tren-demo.mjs"
GEN="$REPO_ROOT/tests/qa/rd-qa-37/tao-anh-bill.py"
ANH_DIR="${MOBILE_HERO_WALK_ANH_DIR:-/tmp/mobile-hero-walk-anh}"
VERDICT_DIR="${MOBILE_HERO_WALK_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/mobile-hero-walk}"
VERDICT="$VERDICT_DIR/verdict.json"
MODE="run"
# Empty = ask about THIS working tree, the only question this file could ask
# until 2026-08-31. Non-empty = ask about a commit the caller names, which is
# the question `origin/main` needs somebody to ask on its behalf.
REF=""
MAX_AGE_HOURS="${MOBILE_HERO_WALK_MAX_AGE_HOURS:-24}"

while [ $# -gt 0 ]; do
  case "$1" in
    --url)  URL="${2:?--url cần một địa chỉ}"; shift 2 ;;
    --anh)  ANH="${2:?--anh cần một đường dẫn}"; shift 2 ;;
    --walk) WALK="${2:?--walk cần một đường dẫn}"; shift 2 ;;
    --status) MODE="status"; shift ;;
    --van-tay) MODE="van-tay"; shift ;;
    --ngoai-git) MODE="ngoai-git"; shift ;;
    --ref)  REF="${2:?--ref cần một ref git}"; shift 2 ;;
    --max-age-hours) MAX_AGE_HOURS="${2:?--max-age-hours cần một số}"; shift 2 ;;
    # The header, all of it, however long it gets. The magic `2,95p` this
    # replaces was already cutting the Usage block off at line 95 before
    # --van-tay was added to it: the only part of the help a reader comes for
    # was the part that never printed, and nothing noticed because a truncated
    # help still exits 0 and still looks like help.
    -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; exit 0 ;;
    *) echo "Tham số lạ: $1 (xem scripts/hero_walk.sh --help)" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }

# The one question the recorded sha cannot answer: is the client that was walked
# the client that commit contains? `git rev-parse HEAD` prints the same string
# for a clean checkout and for that checkout plus edits living in no commit, and
# the verdict dir is shared by every worktree on this machine -- so a walk done
# over a local fix vouched for the broken commit underneath it, in every other
# lane's `make gate` too.
#
# Measured before this existed, on 69938b7: break the scan seam, COMMIT the
# break (e845ced), patch it back in the working tree only, walk. The walk is
# green 16/16 and records sha=e845ced. Restore the tree to the committed state
# and `--status` says "ĐI ĐƯỢC 16/16 chặng, client e845ced (nằm trong HEAD
# e845ced)", exit 0 -- while a real walk on that same clean tree exits 1, ĐỨT at
# the scan step. One field, two meanings, and the dangerous one silent.
#
# So the walk records WHICH TREE, not only which commit. `clean` keeps the cheap
# ancestor rule below untouched -- no clean walk changes behaviour. Anything else
# is code no commit contains, and may vouch only for the worktree that produced
# it, and only while that worktree still holds those exact edits.
#
# Untracked files count: a new .ts under apps/mobile/src is compiled into the
# client the walk drives, and `git diff HEAD` alone never sees it.
cay_van_tay() {
  python3 - "$REPO_ROOT" <<'PY'
import hashlib
import os
import subprocess
import sys

repo = sys.argv[1]


def git(*args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True)


head = git("rev-parse", "--verify", "HEAD")
status = git("status", "--porcelain", "-z")
if head.returncode != 0 or status.returncode != 0:
    # Not a git checkout, or git cannot answer. "I could not tell" must not be
    # spelled the same as "clean" -- that is the whole failure this field exists
    # to separate, so it gets its own value and the reader refuses on it.
    print("?")
    raise SystemExit(0)

# Git can be TOLD NOT TO LOOK at a tracked file: `assume-unchanged` (lowercase
# flag letter) and `skip-worktree` ("S"). Under either bit `status` and `diff`
# stay silent while the file on disk differs from HEAD -- so the checks above
# report a clean tree for edits that are really there. "Git was told not to
# look" is not "there is nothing to see", and it gets its own value for the same
# reason "?" does: spelling an unknown as "clean" is the failure this whole
# field exists to separate. Priority over clean/dirty is deliberate -- once a
# path is hidden, neither answer can be trusted, so neither may be printed.
flags = git("ls-files", "-v")
if flags.returncode != 0:
    print("?")
    raise SystemExit(0)
bi_che = [
    ln
    for ln in flags.stdout.decode("utf-8", "replace").splitlines()
    if ln and ln[0] != "H"
]
if bi_che:
    print("blind")
    raise SystemExit(0)

if not status.stdout.strip():
    print("clean")
    raise SystemExit(0)

h = hashlib.sha256()
h.update(status.stdout)  # which paths changed, and how
h.update(git("diff", "HEAD").stdout)  # what the tracked edits actually say
# Untracked paths carry no diff, and `--porcelain` names an untracked DIRECTORY
# rather than the files inside it. `ls-files --others` enumerates the files, so
# a new source file cannot slip in under an unchanged fingerprint.
others = git("ls-files", "--others", "--exclude-standard", "-z").stdout
for rel in sorted(p for p in others.decode("utf-8", "replace").split("\0") if p):
    h.update(rel.encode("utf-8"))
    try:
        with open(os.path.join(repo, rel), "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        h.update(b"<doc khong duoc>")

print("dirty:" + h.hexdigest()[:16])
PY
}

# `cay_van_tay` above answers "which tracked bytes". This answers the question
# that one cannot: is the stuff git DOES NOT TRACK, and the walk cannot run
# without, actually here?
#
# The comment guarding the `worktree` check used to justify itself with
#
#     "a clean tree at a given commit is the same bytes in every worktree"
#
# which is true of tracked files and false of what this walk depends on.
# `apps/mobile/node_modules` is a hard precondition of this very script (`exit
# 1` if absent), it is gitignored, and it is built per worktree. So "clean at
# commit X" in two directories can mean "walks" in one and "cannot start" in
# the other, and `git status` is silent about the difference by construction.
#
# Measured on 5cfcefa in a throwaway repo with no apps/ at all:
#     --status            -> "ĐI ĐƯỢC 16/16 chặng"   exit 0
#     a real walk, same tree -> exit 2
#
# PRESENCE only, never content. Hashing these would mean hashing node_modules
# on every gate run (slow, and red forever the moment a package updates) and
# putting a real `.env` into a digest, which repo rules forbid outright. The
# weaker promise is written down in KHÔNG chứng minh rather than implied.
ngoai_git_van_tay() {
  python3 - "$REPO_ROOT" <<'PY'
import os
import sys

repo = sys.argv[1]

# Kept deliberately short: every entry must be something the walk genuinely
# cannot run without, or this turns into a second, slower `git status` that
# goes red for reasons nobody can act on.
CAN = ["apps/mobile/node_modules"]

if not CAN:
    # An empty list would make every tree produce the same string, every
    # comparison below succeed, and the whole check disarm itself in silence --
    # while still printing a value that reads like an answer. Same law as "?".
    print("?")
    raise SystemExit(0)

print(",".join(
    f"{p}={'1' if os.path.exists(os.path.join(repo, p)) else '0'}" for p in CAN
))
PY
}

# Printing the fingerprint is not a debug convenience bolted on for tests: a
# refusal that says "cây đã khác" and gives the reader no way to see WHAT the
# runner thinks the tree is turns a correct red into an unexplainable one, and
# unexplainable reds are the ones people route around. It also lets the tests
# ask the runner for its own answer instead of reimplementing the digest, which
# would only grade a copy of the logic.
if [ "$MODE" = "van-tay" ]; then
  cay_van_tay
  exit 0
fi

if [ "$MODE" = "ngoai-git" ]; then
  ngoai_git_van_tay
  exit 0
fi

# --- status ---------------------------------------------------------------

if [ "$MODE" = "status" ]; then
  # Absence of a verdict is NOT a pass. The whole point of recording one is that
  # "nobody has walked it" and "it was walked and it worked" must not look alike.
  [ -f "$VERDICT" ] || {
    say "hero_walk: CHƯA CÓ PHÁN QUYẾT NÀO — không ai đi bộ đường hero trên máy này."
    say "  Chạy: make hero-walk    (mất ~10s, có gọi model thật)"
    exit 2
  }
  MOBILE_HERO_WALK_EXPECT_URL="$URL" \
  MOBILE_HERO_WALK_MAX_AGE_HOURS="$MAX_AGE_HOURS" \
  MOBILE_HERO_WALK_REPO="$REPO_ROOT" \
  MOBILE_HERO_WALK_REF="$REF" \
  MOBILE_HERO_WALK_TREE_NOW="$(cay_van_tay)" \
  MOBILE_HERO_WALK_NGOAI_GIT_NOW="$(ngoai_git_van_tay)" \
  python3 - "$VERDICT" <<'PY'
import json, os, subprocess, sys, time

path = sys.argv[1]
want_url = os.environ["MOBILE_HERO_WALK_EXPECT_URL"]
max_age = float(os.environ["MOBILE_HERO_WALK_MAX_AGE_HOURS"]) * 3600.0
repo = os.environ["MOBILE_HERO_WALK_REPO"]
# Which question is being asked. Empty -> "does this working tree have a proven
# hero path", the only one that existed before. Non-empty -> "does THAT COMMIT
# have one", which is what a reader of `origin/main` needs and could not ask.
ref = (os.environ.get("MOBILE_HERO_WALK_REF") or "").strip()
che_do_ref = bool(ref)


def git(*args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True
    )

try:
    v = json.load(open(path, encoding="utf-8"))
except Exception as exc:  # a corrupt verdict is not a pass either
    print(f"hero_walk: KHÔNG ĐỌC ĐƯỢC phán quyết ({exc}) — từ chối báo xanh.")
    raise SystemExit(2)

age = time.time() - float(v.get("ts", 0))
hours = age / 3600.0
when = f"{hours:.1f} giờ trước" if hours >= 1 else f"{age/60:.0f} phút trước"

# A verdict about another box is not a verdict about this one. Same rule as
# demo_watch's --expect-ref, and for the same reason: it is the failure that
# looks most like a pass.
if v.get("url") != want_url:
    print(f"hero_walk: phán quyết gần nhất nói về {v.get('url')}, KHÔNG phải {want_url}.")
    raise SystemExit(2)

# ...and a verdict about other CODE is not a verdict about this tree. `url`
# above answers "which box"; this answers "which client", and until now nothing
# did. The field was recorded and PRINTED on the pass line but never checked,
# so a walk on any other branch -- or a sha this repo has never heard of --
# vouched for whatever tree the gate happened to be standing in. The verdict
# dir is shared across every worktree on this machine, so that was not a
# hypothetical: it is the normal case with two lanes working at once.
sha = v.get("sha") or "?"
if sha == "?":
    print("hero_walk: phán quyết KHÔNG GHI ĐƯỢC sha client — không buộc được vào cây nào.")
    print("  Chạy lại trong một checkout git: make hero-walk")
    raise SystemExit(2)

head = git("rev-parse", "--short", "HEAD").stdout.strip() or "?"
if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
    # A different clone, a rewritten branch, or a hand-edited verdict. Cannot be
    # placed relative to HEAD at all, so it cannot vouch for HEAD.
    print(f"hero_walk: phán quyết nói về client {sha}, cây này KHÔNG CÓ commit đó (HEAD {head}).")
    print("  Chạy lại trên chính cây đang gác: make hero-walk")
    raise SystemExit(2)

# The commit the verdict has to be bound to. In working-tree mode that is HEAD,
# unchanged. In `--ref` mode the caller names it, and a name git cannot resolve
# must be red: answering "yes" to a question about a ref that does not exist is
# a gate that disarms itself on a typo.
if che_do_ref:
    r = git("rev-parse", "--verify", "--short", f"{ref}^{{commit}}")
    if r.returncode != 0 or not r.stdout.strip():
        print(f"hero_walk: KHÔNG GIẢI ĐƯỢC ref `{ref}` trong {repo}.")
        print("  Không có mốc thì không buộc phán quyết vào đâu được — từ chối báo xanh.")
        raise SystemExit(2)
    moc, moc_ten = r.stdout.strip(), f"`{ref}` ({r.stdout.strip()})"
else:
    moc, moc_ten = "HEAD", f"HEAD {head}"

if git("merge-base", "--is-ancestor", sha, moc).returncode != 0:
    # Ancestor, not equality: requiring an exact match would burn a model call
    # on every docs commit, and a stage that expensive gets deleted. Ancestry
    # still refuses the thing that was broken -- a walk on a branch this tree
    # does not contain. It does NOT prove the commits added since the walk keep
    # the seam working; that is stated in KHÔNG chứng minh, not papered over.
    print(f"hero_walk: lượt đi bộ chạy ở client {sha}, KHÔNG nằm trong {moc_ten} — nhánh khác.")
    if che_do_ref:
        print(f"  Phán quyết đó không nói gì về `{ref}`. Đi bộ từ một checkout của nó:")
        print(f"  git worktree add --detach <thư mục> {ref} && cd <thư mục> && make hero-walk")
    else:
        print("  Phán quyết đó không nói gì về cây này. Chạy: make hero-walk")
    raise SystemExit(2)

# The sha above answers "which COMMIT". This answers "which TREE", and until now
# nothing did: a walk driven by uncommitted edits recorded the untouched sha
# underneath them, so it vouched for code it never ran. See `cay_van_tay`.
#
# Deliberately BEFORE the rc check, like `url` and `sha`: provenance first, then
# content. A verdict that belongs to another tree must be refused rather than
# reported as "ĐỨT ở chặng X" -- borrowed evidence in the red direction still
# sends the wrong lane hunting a bug that is not in their tree, and this repo has
# already spent turns on exactly that.
tree = v.get("tree")
now = os.environ["MOBILE_HERO_WALK_TREE_NOW"]
if tree is None:
    # An older runner could not tell a clean walk from a dirty one. A missing
    # field is "unknown", never "clean": reading absence as the safe value is the
    # bug this whole block exists to close.
    print("hero_walk: phán quyết KHÔNG GHI trạng thái cây làm việc — bản của bộ chạy cũ,")
    print("  vốn không phân biệt được cây sạch với cây có sửa chưa commit.")
    print("  Thiếu trường đó KHÔNG đọc được là 'cây sạch'. Chạy: make hero-walk")
    raise SystemExit(2)

if tree == "?":
    print("hero_walk: lượt đi bộ KHÔNG ĐỌC ĐƯỢC trạng thái cây làm việc của chính nó.")
    print("  Chạy lại trong một checkout git: make hero-walk")
    raise SystemExit(2)

if tree == "blind":
    # Distinct wording from "?" on purpose: there git could not answer at all,
    # here it answered exactly what it was told to answer. The reader needs to
    # know which index bit to clear, not to go looking for a broken checkout.
    print("hero_walk: lượt đi bộ chạy trên cây có file bị ĐÁNH DẤU KHÔNG THEO DÕI")
    print("  (assume-unchanged / skip-worktree), nên trạng thái cây lúc đó không")
    print("  đo được. Gỡ bằng: git update-index --no-assume-unchanged --no-skip-worktree <file>")
    print("  rồi chạy: make hero-walk")
    raise SystemExit(2)

where = v.get("worktree")
muon = where != repo

# Everything from here down to the `tree != now` comparison answers one
# question: is this verdict still true of THIS DIRECTORY? Every one of those
# checks reads the directory the command was typed in.
#
# `--ref` asks a different question, about a commit. A commit does not acquire
# uncommitted edits, does not lose its `node_modules`, and does not stop
# existing because a temporary worktree was deleted -- so answering the ref
# question out of this directory's state would be measuring the wrong thing in
# both directions: red for a main that is fine, green for a main that is not.
#
# It is not a loosening. `--ref` pays for the skipped checks immediately below,
# with a rule working-tree mode does not have: a walk over uncommitted edits
# ran code that lives in NO commit, so it vouches for no commit at all -- not
# even the one underneath it. Working-tree mode may accept such a walk (it can
# re-verify the edits are still there, and does). Ref mode can never accept it.
kiem_thu_muc = not che_do_ref
if che_do_ref and tree != "clean":
    print(f"hero_walk: lượt đi bộ chạy trên CÂY CÓ SỬA CHƯA COMMIT ({where}).")
    print("  Mã nó đo không nằm trong commit nào, nên nó không bảo lãnh được cho")
    print(f"  `{ref}`. Đi bộ lại trên một checkout sạch của `{ref}`.")
    raise SystemExit(2)

if tree != "clean" and muon:
    # Uncommitted edits exist in exactly one directory, so a dirty walk can
    # never be lent -- no further question to ask.
    print(f"hero_walk: lượt đi bộ chạy trên cây CÓ SỬA CHƯA COMMIT ở {where},")
    print(f"  không phải {repo}. Mã nó đo không nằm trong commit nào,")
    print("  nên nó không bảo lãnh được cho cây này. Chạy: make hero-walk")
    raise SystemExit(2)

# A clean verdict MAY still be lent to another worktree -- that sharing is the
# design, not an accident, and forbidding it would make ten worktrees each burn
# a model call, which is how this stage gets deleted. But it was lent
# UNCONDITIONALLY, on a justification that only covers tracked files:
#
#     "a clean tree at a given commit is the same bytes in every worktree"
#
# The two things below are what that sentence leaves out. Both are cheap.
#
# First: the verdict has to name a tree that is still there. A green pointing
# at a directory nothing can reach is evidence about nothing -- the same
# "bằng chứng gọi tên một thứ không phải thứ đã được kiểm" this file was
# extended twice to stop, one axis over.
if kiem_thu_muc and muon and not os.path.isdir(where or ""):
    print(f"hero_walk: phán quyết nói nó đo ở {where}, thư mục đó KHÔNG CÓ trên máy này.")
    print("  Không kiểm lại được nó đo trên cái gì, nên nó không bảo lãnh được")
    print(f"  cho {repo}. Chạy: make hero-walk")
    raise SystemExit(2)

# Second: the things the walk needs that git does not track. See
# `ngoai_git_van_tay`. Checked for EVERY verdict, borrowed or not -- deleting
# `node_modules` in the same directory that produced the green leaves `git
# status` silent and the walk unable to start, and that hole is not about
# borrowing at all.
ngoai = v.get("ngoai_git")
ngoai_now = os.environ["MOBILE_HERO_WALK_NGOAI_GIT_NOW"]
if kiem_thu_muc and ngoai is None:
    # Same law as `tree` above: a field an older runner never wrote is
    # "unknown", and reading unknown as the safe value is the failure this whole
    # file exists to separate.
    print("hero_walk: phán quyết KHÔNG GHI những thứ ngoài git mà lượt đi bộ cần")
    print("  (node_modules...) — bản của bộ chạy cũ, vốn không phân biệt được")
    print("  một cây đi bộ được với một cây chưa hề 'npm ci'.")
    print("  Thiếu trường đó KHÔNG đọc được là 'đủ'. Chạy: make hero-walk")
    raise SystemExit(2)

if kiem_thu_muc and (ngoai == "?" or ngoai_now == "?"):
    print("hero_walk: KHÔNG ĐỌC ĐƯỢC danh sách thứ ngoài git mà lượt đi bộ cần.")
    print("  'Không đọc được' KHÔNG phải 'đủ'. Chạy: make hero-walk")
    raise SystemExit(2)

if kiem_thu_muc and ngoai != ngoai_now:
    def _tach(s):
        return dict(p.split("=", 1) for p in s.split(",") if "=" in p)

    luc_do, bay_gio = _tach(ngoai), _tach(ngoai_now)
    khac = sorted(k for k in set(luc_do) | set(bay_gio) if luc_do.get(k) != bay_gio.get(k))
    # Name the paths. A refusal that says only "khác nhau" sends the reader to
    # read this script instead of to the one directory they need to fix, and
    # unexplainable reds are the ones people route around.
    for k in khac or ["(danh sách đã đổi)"]:
        print(f"hero_walk: {k} — lúc đi bộ: {luc_do.get(k, 'không có trong phán quyết')},"
              f" bây giờ: {bay_gio.get(k, 'không có')}")
    o_dau = f"ở {where}" if muon else "ở chính cây này"
    print(f"  Lượt đi bộ chạy {o_dau} với những thứ đó KHÁC bây giờ, mà git không")
    print("  theo dõi chúng nên trạng thái 'cây sạch' không nói gì về chúng.")
    print("  Chạy: make hero-walk")
    raise SystemExit(2)

# OUTSIDE the branch above, and that placement is the whole fix. This comparison
# used to sit INSIDE `if tree != "clean":`, so it only ever ran when the RECORDED
# tree was dirty. A verdict saying `clean` was therefore never compared to
# anything: it was accepted unconditionally for MAX_AGE_HOURS.
#
# That left the gate blind in the one direction every lane travels daily -- walk
# a clean main, then start typing. From the first keystroke the verdict vouches
# for a tree nobody walked, which is verbatim what this block was added to stop:
# "it vouched for code it never ran". The dirty->dirty direction was closed, so
# the hole was an ASYMMETRY, not a dead gate, and asymmetric holes survive
# precisely because the half that works reads as proof the whole thing works.
if kiem_thu_muc and tree != now:
    if now == "?":
        # Reachable while every sha check above still passes: a corrupt or
        # locked index (and `.git` is SHARED between this repo's worktrees) makes
        # `git status` exit 128 while `rev-parse` answers fine. Must not be
        # phrased as "you have uncommitted edits" -- that is a true red with a
        # false reason, and it sends the reader hunting a change they never made.
        print("hero_walk: KHÔNG ĐỌC ĐƯỢC trạng thái cây làm việc BÂY GIỜ,")
        print("  nên không xác nhận lại được phán quyết còn nói về cây này.")
        print("  'Không đọc được' KHÔNG phải 'cây vẫn thế'. Chạy: make hero-walk")
    elif now == "blind":
        # Same trap as `now == "?"`: a true red carrying a false reason. Falling
        # through to the "clean" branch below would tell the reader they have
        # uncommitted edits, and they would hunt a diff `git status` refuses to
        # show them -- because they themselves told it not to.
        print("hero_walk: cây BÂY GIỜ có file bị ĐÁNH DẤU KHÔNG THEO DÕI")
        print("  (assume-unchanged / skip-worktree), nên không xác nhận lại được")
        print("  phán quyết còn nói về cây này. Gỡ dấu rồi chạy: make hero-walk")
    elif tree == "clean":
        print("hero_walk: lượt đi bộ chạy trên CÂY SẠCH, còn cây bây giờ CÓ SỬA")
        print("  CHƯA COMMIT — client bây giờ không phải client đã đi bộ.")
        print("  Chạy: make hero-walk")
    else:
        print("hero_walk: lượt đi bộ chạy trên cây có sửa chưa commit, và những sửa đó")
        print("  ĐÃ KHÁC so với bây giờ — client bây giờ không phải client đã đi bộ.")
        print("  Chạy: make hero-walk")
    raise SystemExit(2)

if int(v.get("rc", 1)) != 0:
    print(f"hero_walk: lượt gần nhất ({when}) ĐỨT ở '{v.get('buoc_hong','?')}' trên {v['url']}.")
    raise SystemExit(2)

if age > max_age:
    print(f"hero_walk: phán quyết CŨ QUÁ — {when}, ngưỡng {max_age/3600:.0f} giờ. Chạy lại: make hero-walk")
    raise SystemExit(2)

# A green measured over uncommitted edits is still a green about THIS tree, but
# it is not a green about any commit -- and a pass line that reads the same for
# both is how the verdict got borrowed in the first place. Say it on the line
# people actually read.
ve_cay = "" if tree == "clean" else " — ĐO TRÊN CÂY CÓ SỬA CHƯA COMMIT, không phải trên commit nào"

# A borrowed green and a self-measured green must not read alike. Everything
# checkable about the loan has been checked above, and what is left over --
# the CONTENT of those out-of-git artifacts, and any commit added between the
# two trees -- is exactly what the reader needs to know they are trusting. Say
# it on the line people actually read, same rule as `ve_cay`.
ve_muon = "" if not muon else f" — MƯỢN từ cây {where}, không phải đo ở đây"

# Name what was answered ABOUT. A green reading "nằm trong HEAD <sha>" when the
# caller asked about `origin/main` is this file's recurring failure one axis
# over: evidence read as being about something it was never about. And in ref
# mode the directory is not the subject, so the loan note would only invite the
# reader to weigh the wrong thing.
if che_do_ref:
    print(
        f"hero_walk: ĐI ĐƯỢC {when} — {v.get('so_chang','?')} chặng, "
        f"{v['url']}, client {sha} (nằm trong {moc_ten}), "
        f"model đọc {v.get('so_mon','?')} món.{ve_cay}"
    )
    print(f"  Trả lời về `{ref}`, KHÔNG phải về thư mục {repo}.")
else:
    print(
        f"hero_walk: ĐI ĐƯỢC {when} — {v.get('so_chang','?')} chặng, "
        f"{v['url']}, client {sha} (nằm trong HEAD {head}), "
        f"model đọc {v.get('so_mon','?')} món.{ve_cay}{ve_muon}"
    )
PY
  exit $?
fi

# --- preconditions --------------------------------------------------------

# The walk itself is the subject. If it is gone, this stage must go red rather
# than pass with nothing to run: deleting the only file that crosses the scan
# seam is precisely the change that must not be reported as green.
[ -f "$WALK" ] || {
  say "KHÔNG CÓ bài đi bộ: $WALK"
  say "  Đây là file DUY NHẤT đi qua mối nối scan -> readingFromWire -> POST /bills."
  say "  Xoá nó không được biến chặng này thành xanh. Nếu nó đã dời chỗ, sửa --walk."
  exit 2
}

command -v node >/dev/null 2>&1 || { say "không có node"; exit 1; }
command -v npm  >/dev/null 2>&1 || { say "không có npm"; exit 1; }
[ -d "$REPO_ROOT/apps/mobile/node_modules" ] || {
  say "chưa 'npm ci' trong apps/mobile"; exit 1; }

# --- is there a box there, and does it have the seam? ---------------------

# Unreachable is an absence: on a CI runner or a fresh clone nothing serves
# 8099, and being red forever for that reason would get the stage deleted.
code="$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$URL/healthz" 2>/dev/null)"
if [ "$code" != "200" ]; then
  say "không có máy nào trả lời $URL/healthz (nhận '$code')"
  exit 1
fi

# Reachable but without the route is a DEFECT, not an absence, and it is the
# case worth spending a curl on. A container built before the bill path existed
# answers 200 on /healthz and 404 on /receipts/scan -- from the outside that is
# indistinguishable from a feature that is broken, and this repo has already
# lost two measurements to exactly that confusion.
paths_json="$(curl -s -m 15 "$URL/openapi.json" 2>/dev/null)"
seam_report="$(printf '%s' "$paths_json" | python3 -c "
import json, sys
try:
    paths = json.load(sys.stdin).get('paths', {})
except Exception:
    print('KHONG_DOC_DUOC 0'); raise SystemExit
need = ['/receipts/scan', '/bills', '/expenses', '/batches']
missing = [r for r in need if r not in paths]
print(('THIEU ' + ','.join(missing)) if missing else 'DU', len(paths))
" 2>/dev/null)"
seam_state="${seam_report%% *}"
route_count="${seam_report##* }"

if [ "$seam_state" = "KHONG_DOC_DUOC" ]; then
  say "máy ở $URL trả lời /healthz nhưng không đọc được /openapi.json"
  say "  Không xác nhận được nó có mối nối bill hay không -- từ chối báo xanh."
  exit 2
fi
if [ "$seam_state" = "THIEU" ]; then
  say "máy ở $URL KHÔNG có đủ route của đường bill: ${seam_report#THIEU }"
  say "  Nó trả lời /healthz nên nhìn từ ngoài giống một máy khoẻ."
  say "  Đây là máy cũ hơn tính năng, không phải tính năng hỏng."
  exit 2
fi

# --- the bill image -------------------------------------------------------

# Generated, never photographed: repo rules forbid bill images in git, so the
# fixture is built into /tmp at run time. Regenerating when absent is what lets
# this run on a machine that has just been rebooted, rather than depending on a
# file somebody left behind.
if [ -z "$ANH" ]; then
  ANH="$ANH_DIR/ro.jpg"
  if [ ! -f "$ANH" ]; then
    [ -f "$GEN" ] || {
      say "thiếu cả ảnh bill lẫn bộ sinh ảnh ($GEN)"; exit 2; }
    python3 -c "import PIL" 2>/dev/null || {
      say "chưa có Pillow, không sinh được ảnh bill (pip install pillow)"; exit 1; }
    say "--- sinh ảnh bill tổng hợp vào $ANH_DIR"
    python3 "$GEN" "$ANH_DIR" >/dev/null || {
      say "bộ sinh ảnh bill chạy hỏng"; exit 2; }
  fi
fi
[ -f "$ANH" ] || { say "không có ảnh bill tại $ANH"; exit 2; }

# --- rebuild the client under test ---------------------------------------

say "--- dựng lại dist-test từ src/ của cây này"
(
  cd "$REPO_ROOT/apps/mobile" || exit 2
  npx --no-install tsc -p tsconfig.test.json && node tools/fixup-esm.mjs
) || { say "không dựng được client (tsc/fixup-esm hỏng)"; exit 2; }

# --- provenance -----------------------------------------------------------

say ""
say "client  dựng từ $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo '?')$(git -C "$REPO_ROOT" diff --quiet 2>/dev/null || echo ' (cây có sửa chưa commit)')"
say "máy chủ $URL — $route_count route, có đủ /receipts/scan /bills /expenses /batches"
say "ảnh     $ANH (tổng hợp)"
say ""

# --- walk -----------------------------------------------------------------

OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT
EXPO_PUBLIC_API_URL="$URL" node "$WALK" "$ANH" 2>&1 | tee "$OUT"
rc=${PIPESTATUS[0]}

# --- record the verdict ---------------------------------------------------

# Written on failure too. A stage that only records its wins reports "no
# verdict" for a broken path, which reads as "nobody ran it" rather than "it is
# broken" -- the two states this file spends a whole section separating.
mkdir -p "$VERDICT_DIR"
MOBILE_HERO_WALK_RC="$rc" \
MOBILE_HERO_WALK_URL="$URL" \
MOBILE_HERO_WALK_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo '?')" \
MOBILE_HERO_WALK_TREE="$(cay_van_tay)" \
MOBILE_HERO_WALK_WORKTREE="$REPO_ROOT" \
MOBILE_HERO_WALK_NGOAI_GIT="$(ngoai_git_van_tay)" \
MOBILE_HERO_WALK_ROUTES="$route_count" \
MOBILE_HERO_WALK_ANH="$ANH" \
python3 - "$OUT" "$VERDICT" <<'PY'
import json, os, re, time

text = open(os.sys.argv[1], encoding="utf-8", errors="replace").read()

def find(pattern, cast=str, default=None):
    m = re.search(pattern, text)
    return cast(m.group(1)) if m else default

# The failing step is the diagnosis a reader wants first, so it is stored rather
# than left in a log that gets overwritten by the next run.
hong = re.search(r"^\s*HONG\s+(.+?)\s+\(\d+ms\)", text, re.M)

verdict = {
    "ts": time.time(),
    "rc": int(os.environ["MOBILE_HERO_WALK_RC"]),
    "url": os.environ["MOBILE_HERO_WALK_URL"],
    "sha": os.environ["MOBILE_HERO_WALK_SHA"],
    # "clean" | "dirty:<digest>" | "?" -- which TREE, next to which COMMIT.
    # `--status` refuses a verdict missing this, so an old verdict cannot be
    # read as a clean one.
    "tree": os.environ["MOBILE_HERO_WALK_TREE"],
    "worktree": os.environ["MOBILE_HERO_WALK_WORKTREE"],
    # Presence of what git does not track and the walk cannot run without.
    # `tree` cannot see these by construction; a clean tree in a directory that
    # never ran `npm ci` reads identically to one that did.
    "ngoai_git": os.environ["MOBILE_HERO_WALK_NGOAI_GIT"],
    "routes": os.environ["MOBILE_HERO_WALK_ROUTES"],
    "anh": os.environ["MOBILE_HERO_WALK_ANH"],
    "so_chang": find(r"DAT (\d+/\d+) chang"),
    "so_mon": find(r"model doc (\d+) mon", int),
    "buoc_hong": hong.group(1) if hong else None,
}
with open(os.sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(verdict, fh, ensure_ascii=False, indent=2)
PY

say ""
if [ "$rc" -eq 0 ]; then
  say "Đường hero đi được hết trên $URL, kể cả chặng ảnh -> món."
else
  say "Đường hero ĐỨT trên $URL (mã $rc). Chặng HONG ở trên là chỗ đứt."
fi
say "phán quyết ghi vào $VERDICT"
exit "$rc"
