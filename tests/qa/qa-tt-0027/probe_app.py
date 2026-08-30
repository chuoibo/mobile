"""QA probe for #297: count REAL model calls made by a REAL uvicorn server.

Only the network boundary is stubbed. `CachedReasonWriter` (the code under
test), `gemini_reasons`, `parse_reasons` and `ungrounded_numbers` all run
unmodified: this counts calls, it does not make anything pass.

`QA_REFUSED_PLACE` names one place whose canned reason carries an ungrounded
figure, so `parse_reasons` drops it exactly as it drops a real ungrounded
answer. That row is the "hang bi tu choi" the ticket is about.
"""

import json
import os
import threading
import time

from app.places import reasons as R
from app.places.catalog import PLACES

DELAY = float(os.environ.get("QA_POST_DELAY", "0.8"))
REFUSED = os.environ.get("QA_REFUSED_PLACE", PLACES[0]["id"])

_state = {"post": 0}
_lock = threading.Lock()

# A reason with no digits at all is grounded by construction. The refused row
# gets a figure that appears nowhere in its record, which is what
# `ungrounded_numbers` exists to catch.
_CANNED = json.dumps(
    [
        {
            "id": p["id"],
            "verdict": "hop",
            "reason": (
                "Quan nay hop gu ca nhom, gia tien 1234567 dong moi nguoi."
                if p["id"] == REFUSED
                else "Quan nay hop gu ca nhom, khong gian de ngoi lau."
            ),
        }
        for p in PLACES
    ],
    ensure_ascii=False,
)


def _counting_post(prompt, api_key):
    with _lock:
        _state["post"] += 1
    # A real Gemini round trip is seconds. Without latency here the "twenty at
    # the same time" case would not actually overlap and the pre-fix tree
    # would look fixed.
    time.sleep(DELAY)
    return _CANNED


R._post = _counting_post

from app.api.main import create_app  # noqa: E402

app = create_app()


@app.get("/__qa_probe/count")
def _qa_count():
    with _lock:
        return {"post": _state["post"], "refused_place": REFUSED, "delay": DELAY}
