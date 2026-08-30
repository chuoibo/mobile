# Names for the Docker artifacts the gate builds. Sourced, never executed.
#
# ## Why this is not a tidiness question
#
# `scripts/gate.sh docker` used to build `mobile-api:gate` and run
# `mobile-api-gate`. Image tags and container names are global on a Docker
# daemon, and this machine runs five worktrees of one repository against one
# daemon. Measured 2026-08-30 (#291): a lane whose tree already carried the
# #288 fix got a red at the exact line #288 had fixed, because a second lane's
# `docker build -t mobile-api:gate` had moved the tag between this lane's build
# and its run. Opening the image showed another worktree's memories.py. The
# same log carried two `No such container: mobile-api-gate` lines -- the other
# lane's `docker rm -f` deleting a container mid-poll.
#
# The red was the lucky direction. Reverse the order and lane A builds a tree
# that boots while lane B reads that image and concludes ITS tree boots, with
# nothing in the stage output telling the two apart -- under a rule adopted the
# same day that a PR touching a route declaration does not merge until this
# stage is green.
#
# ## What the run id is made of
#
#   <leaf>   the worktree's directory name, so `docker images` during a run
#            says which lane is building rather than showing a hash.
#   <hash>   a checksum of the absolute path, because five worktrees named
#            after five lanes is the current layout, not a guarantee.
#   <pid>    the gate process, because one lane running the gate twice is the
#            same collision and a path-only key would not see it.
#
# ## Why the id is exported and the names are not
#
# `scripts/gate.sh` sources this once and `scripts/check_pinned_import.sh`
# sources it again as a child process. The child finds MOBILE_GATE_RUN_ID
# already set and reuses it, so both stages of one run name one image and the
# pinned-import build lands on the cache the docker stage filled -- which is
# what that script's header promises. Exporting the id rather than the names
# keeps one thing authoritative: derive, do not copy.
#
# MOBILE_GATE_NAMES_INHERITED tells a sourcing script whether it generated the
# id. Whoever generated it owns the cleanup; per-run names would otherwise
# trade a collision for one dangling image per run.

if [ -n "${MOBILE_GATE_RUN_ID:-}" ]; then
  MOBILE_GATE_NAMES_INHERITED=1
else
  MOBILE_GATE_NAMES_INHERITED=0
  _gdn_root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd -P)"
  # Docker tags allow [A-Za-z0-9_.-] after a leading alphanumeric; anything
  # else in a directory name becomes a dash rather than an invalid tag.
  _gdn_leaf="$(printf '%s' "$(basename "$_gdn_root")" | tr 'A-Z' 'a-z' |
    tr -c 'a-z0-9' '-' | sed -e 's/-\{2,\}/-/g' -e 's/^-//' -e 's/-$//')"
  _gdn_hash="$(printf '%s' "$_gdn_root" | cksum 2>/dev/null | cut -d' ' -f1)"
  MOBILE_GATE_RUN_ID="${_gdn_leaf:-tree}-${_gdn_hash:-0}-$$"
  export MOBILE_GATE_RUN_ID
  unset _gdn_root _gdn_leaf _gdn_hash
fi

MOBILE_GATE_IMAGE="mobile-api:gate-${MOBILE_GATE_RUN_ID}"
MOBILE_GATE_CONTAINER="mobile-api-gate-${MOBILE_GATE_RUN_ID}"
