#!/usr/bin/env bash
# Load the API with the fastapi version that SHIPS, not the one on this machine.
#
# The gap this closes, measured: `services/api/app/api/routes/memories.py`
# declared a 204 route as `def f() -> None` in a module carrying
# `from __future__ import annotations`. With postponed annotations the return
# annotation resolves to the CLASS `NoneType`, which is truthy, not to the
# `None` singleton, which is not. fastapi 0.115.6 -- the version pinned in
# requirements-dev.txt and therefore the version inside the image -- does
#
#     if self.response_model:
#         assert is_body_allowed_for_status_code(status_code)
#
# at import time, so the app could not be imported at all. fastapi 0.135.3,
# which is what happens to be on the developer PATH here, normalises NoneType
# to None and never reaches the assert. Result: 2305 pytest cases green, and a
# container that exits before it is ever healthy.
#
# Nothing in the test suite could see this, because the test suite imports the
# app with the machine's fastapi. The docker stage could -- and did -- but it
# builds an image, starts a container and waits on a HEALTHCHECK, so in
# practice it was skipped on the PRs that most needed it. This script is the
# same proof at about two seconds: same image, same pins, no container.
#
# Exit codes, matching scripts/gate.sh:
#   0  the app imports under the pinned fastapi
#   1  the app does not import, or the image has drifted off the pin
#   2  the check could not be run at all (no docker) -- never a silent pass

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
REPO_ROOT="$PWD"

IMAGE="${MOBILE_PINNED_IMAGE:-mobile-api:gate}"

command -v docker >/dev/null 2>&1 || { echo "không có docker" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "docker daemon không chạy" >&2; exit 2; }

# The pin is read from the file rather than hardcoded, so bumping fastapi in
# requirements-dev.txt cannot leave this check asserting a version nobody uses.
PINNED="$(sed -nE 's/^fastapi==([^ ;#]+).*/\1/p' services/api/requirements-dev.txt | head -1)"
[ -n "$PINNED" ] || { echo "không đọc được pin fastapi trong requirements-dev.txt" >&2; exit 2; }

echo "--- build ảnh (dùng lại cache của chặng docker)"
( cd services/api && docker build -q -t "$IMAGE" . >/dev/null ) || {
  echo "docker build hỏng" >&2; exit 1; }

ACTUAL="$(docker run --rm --entrypoint /venv/bin/python "$IMAGE" \
            -c 'import fastapi; print(fastapi.__version__)' 2>/dev/null)"
echo "fastapi trong ảnh = ${ACTUAL:-?} (pin: $PINNED)"

# A known-bad canary, run first, every run. Comparing the image's version
# against the pin would prove nothing -- the build above installs the pin, so
# the two match by construction. The thing that can actually go quiet is the
# pin MOVING: fastapi 0.135.3 normalises the deferred `-> None` to None and
# never reaches the assert, so on that version this whole stage would go green
# forever while catching nothing.
#
# So the gate proves it still has teeth before it reports on the real app. The
# canary below is the defect in miniature. It must FAIL. If it imports, this
# check has stopped being able to see the bug it exists for, and that is
# reported as red -- a gate that has gone blind says so rather than passing.
CANARY_DIR="$(mktemp -d)"
trap 'rm -rf "$CANARY_DIR"' EXIT
# The image runs as uid 10001 and `mktemp -d` is mode 700 owned by the calling
# user, so without this the canary dies of ModuleNotFoundError before fastapi
# is ever consulted -- a non-zero exit that would have been misread as "the
# canary failed as intended". Measured: that is exactly what happened here
# once. Hence also the message match below rather than a bare exit-code test.
chmod 755 "$CANARY_DIR"
cat > "$CANARY_DIR/canary_bad.py" <<'PY'
from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter()


@router.delete("/canary", status_code=status.HTTP_204_NO_CONTENT)
def canary() -> None: ...
PY

chmod 644 "$CANARY_DIR/canary_bad.py"

echo "--- canary xấu (phải ĐỎ, và phải đỏ ĐÚNG LÝ DO)"
canary_out="$(docker run --rm -v "$CANARY_DIR:/canary:ro" -w /canary \
                --entrypoint /venv/bin/python "$IMAGE" -c 'import canary_bad' 2>&1)"
canary_rc=$?
if [ "$canary_rc" -eq 0 ]; then
  echo "canary xấu IMPORT ĐƯỢC với fastapi ${ACTUAL:-?} — bản này không còn bắt hình dạng" >&2
  echo "'204 + annotation hoãn lại', nên chặng pinned-import không còn thấy lỗi nó sinh ra" >&2
  echo "để bắt. Coi như ĐỎ." >&2
  echo "Nếu pin fastapi vừa được nâng có chủ ý, sửa hoặc gỡ chặng này cùng lúc." >&2
  exit 1
fi
# Red is not enough: an unreadable mount or a missing module is also red, and
# reading that as proof of teeth is how this check was wrong the first time.
case "$canary_out" in
  *"must not have a response body"*)
    echo "canary xấu đỏ đúng lý do (assert 204) — cổng còn răng" ;;
  *)
    echo "canary xấu đỏ NHƯNG SAI LÝ DO — không chứng minh được cổng còn răng:" >&2
    echo "$canary_out" | tail -3 >&2
    exit 1 ;;
esac

# The source comes from the working tree, not from the layer baked into the
# image: the point is to measure the code about to be pushed, uncommitted
# changes included, against the dependencies about to ship.
echo "--- nạp app.api.main bằng fastapi $PINNED"
docker run --rm \
  -v "$REPO_ROOT/services/api:/src:ro" \
  -w /src \
  --entrypoint /venv/bin/python "$IMAGE" \
  -c 'import sys; sys.path.insert(0, "/src"); from app.api.main import app; print("IMPORT OK,", len(app.openapi()["paths"]), "đường dẫn")' || {
    echo "app KHÔNG import được với fastapi $PINNED — container sẽ thoát trước khi healthy" >&2
    exit 1
  }
