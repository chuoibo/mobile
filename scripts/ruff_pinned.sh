#!/usr/bin/env bash
#
# Print the path to the ruff version `services/api/requirements-dev.txt` pins,
# provisioning it if this machine does not have it.
#
# ## Why this exists
#
# `scripts/ruff_changed.sh` used to call whatever `ruff` was first on PATH.
# `scripts/gate.sh` noticed the mismatch, printed a warning, and passed the
# stage anyway:
#
#     # Deliberately NOT a failure when the local version differs. [...]
#     CHÚ Ý: máy này lint bằng ruff 0.15.15, CI lint bằng ruff==0.9.2
#
# The reasoning was right and the conclusion left a hole. Hard-failing on a
# mismatch would make the stage red on every machine with a newer ruff, which
# is the kind of gate that gets switched off within a day. But a warning on
# line three of a thirteen-stage run, under a summary that ends "ĐẠT ruff", is
# not a warning anybody reads -- and while Actions is down this local gate is
# the ONLY gate, so its verdict is the whole verdict.
#
# Measured on 2026-08-30 at c811254, both versions over the same 320 tracked
# Python files:
#
#     ruff 0.9.2  (the pin, what CI installs)   31 findings
#     ruff 0.15.15 (this machine's PATH)        30 findings
#
#     only 0.9.2 sees:
#       services/api/app/domain/place_search.py:105:39: UP038
#         Use `X | Y` in `isinstance` call instead of `(X, Y)`
#
# UP038 was REMOVED in later ruff, so the newer binary cannot report it at all.
# Anyone touching `place_search.py` got ĐẠT from the local gate and would have
# got HỎNG from CI. That is "green because it ran the wrong thing" -- the exact
# shape scripts/gate.sh was written to stamp out -- reproduced inside gate.sh's
# own lint stage.
#
# The formatter half does NOT diverge on this tree (both versions name the same
# 134 files, and their output is byte-identical on the file measured), but that
# is a fact about today's tree, not a guarantee. The rule is the same either
# way: a verdict from the wrong tool is not the verdict.
#
# ## The fix, and why provisioning rather than failing
#
# `scripts/postgres_tier.sh` already set the precedent. That stage was a
# permanent BỎ QUA because it refused to start without a connection string;
# it stopped being one by building its own database instead of demanding one.
# Same move: build the pinned ruff instead of demanding it, so the stage runs
# the right tool on a machine that has the wrong one, and nobody has to
# downgrade their editor's ruff to get an honest gate.
#
# In CI this costs nothing. The lint job pip-installs the pin before calling
# `ruff_changed.sh`, so PATH's ruff already IS the pin and the first branch
# below returns immediately.
#
# Usage:
#   scripts/ruff_pinned.sh          print the path to the pinned ruff
#   scripts/ruff_pinned.sh --pin    print the pin line (ruff==X.Y.Z)
#
# Exit codes: 0 the printed path is a ruff whose version matches the pin,
# 2 could not produce one -- never a fallback to a different version, because
# that is the defect this file removes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REQUIREMENTS="$REPO_ROOT/services/api/requirements-dev.txt"

# Read from the file rather than repeating the version, for the reason
# test.yml's lint job already gives: two copies drift.
#
# Builtins only -- no `grep`, no `head`. tests/test_ruff_changed.py runs the
# gate with a PATH holding nothing but bash and git, and the first draft of this
# used `grep ... || true`: with grep unreachable the pin came back empty and
# this script announced "không có dòng ruff== trong requirements-dev.txt". That
# is a false reason, and it would send somebody editing a file that is perfectly
# correct. A gate is allowed to fail; it is not allowed to misname why.
pin_line() {
  local line
  [ -r "$REQUIREMENTS" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ruff==*) printf '%s' "$line"; return 0 ;;
    esac
  done < "$REQUIREMENTS"
  return 1
}

if [ ! -r "$REQUIREMENTS" ]; then
  echo "::error::không đọc được $REQUIREMENTS" >&2
  exit 2
fi
if ! PIN="$(pin_line)"; then
  echo "::error::không có dòng ruff== trong services/api/requirements-dev.txt" >&2
  echo "Cổng lint cài ruff từ pin đó; mất pin thì mỗi máy lint bằng một bản khác nhau." >&2
  exit 2
fi
WANT="${PIN#ruff==}"

if [ "${1:-}" = "--pin" ]; then
  printf '%s\n' "$PIN"
  exit 0
fi

# `ruff --version` prints "ruff X.Y.Z". Empty when the binary is missing or
# refuses to run, which the caller treats as "not this one".
#
# Parameter expansion rather than `awk`, for the reason pin_line() gives: this
# has to be able to answer honestly on a runner with almost no PATH.
version_of() {
  local out
  out="$("$1" --version 2>/dev/null)" || return 0
  out="${out#* }"
  printf '%s' "${out%% *}"
}

# 1. Already on PATH at the right version. This is CI's case, and the case on a
#    developer machine that installed requirements-dev.txt.
if command -v ruff >/dev/null 2>&1 && [ "$(version_of ruff)" = "$WANT" ]; then
  command -v ruff
  exit 0
fi

CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/mobile-gate/ruff"
VENV="$CACHE_ROOT/$WANT"
CACHED="$VENV/bin/ruff"

# 2. Provisioned earlier. The version is re-checked rather than trusted from
#    the directory name: a half-written cache from an interrupted install would
#    otherwise be handed out as if it were the pin.
if [ -x "$CACHED" ] && [ "$(version_of "$CACHED")" = "$WANT" ]; then
  printf '%s\n' "$CACHED"
  exit 0
fi

# 3. Build it. Into a temporary directory and then renamed into place, because
#    several lanes run gates on this machine at the same time and a half-built
#    venv visible at the final path is the failure mode step 2 is guarding
#    against. `mv` onto an existing directory would nest, so a loser of the
#    race cleans up after itself and re-checks.
echo "ruff $WANT chưa có trên máy -- đang dựng vào $VENV (chỉ lần đầu)" >&2
if ! mkdir -p "$CACHE_ROOT" 2>/dev/null; then
  echo "::error::không tạo được thư mục cache $CACHE_ROOT" >&2
  exit 2
fi
if ! STAGING="$(mktemp -d "$CACHE_ROOT/.building-$WANT.XXXXXX" 2>/dev/null)"; then
  echo "::error::không tạo được thư mục tạm trong $CACHE_ROOT (thiếu mktemp?)" >&2
  exit 2
fi
cleanup() { rm -rf "$STAGING"; }
trap cleanup EXIT

if ! python3 -m venv "$STAGING/venv" >&2; then
  echo "::error::không tạo được venv để cài ruff $WANT" >&2
  exit 2
fi
if ! "$STAGING/venv/bin/pip" install --quiet --disable-pip-version-check "$PIN" >&2; then
  echo "::error::không cài được $PIN (mạng? bản này còn trên PyPI không?)" >&2
  echo "Cổng lint từ chối chấm bằng một bản ruff khác: verdict của bản khác không phải verdict của CI." >&2
  echo "Gỡ tay: python3 -m venv $VENV && $VENV/bin/pip install $PIN" >&2
  exit 2
fi

BUILT="$STAGING/venv/bin/ruff"
GOT="$(version_of "$BUILT")"
if [ "$GOT" != "$WANT" ]; then
  # pip resolved something else -- a yanked release, a local wheel, a proxy.
  # Reporting this as the pin would be the original defect with extra steps.
  echo "::error::cài xong nhưng ra ruff '${GOT:-không chạy được}', không phải $WANT" >&2
  exit 2
fi

if mv "$STAGING/venv" "$VENV" 2>/dev/null; then
  :
else
  # Another process won the race and the path already holds a venv. Use theirs
  # if it is the right version; otherwise this machine's cache is wrong and
  # saying so is better than shipping an unknown binary.
  if [ -x "$CACHED" ] && [ "$(version_of "$CACHED")" = "$WANT" ]; then
    printf '%s\n' "$CACHED"
    exit 0
  fi
  echo "::error::không chuyển được venv vào $VENV và chỗ đó cũng không phải ruff $WANT" >&2
  exit 2
fi

printf '%s\n' "$CACHED"
