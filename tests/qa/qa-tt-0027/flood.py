"""The threat in the docstring: `while true; do curl; done` with -P 20, anonymous."""

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE, TOTAL, CONC = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])


def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r:
        return json.loads(r.read().decode())


ok = fail = 0
t0 = time.time()


def one(_):
    try:
        get("/places")
        return True
    except Exception:
        return False


with ThreadPoolExecutor(max_workers=CONC) as ex:
    res = list(ex.map(one, range(TOTAL)))
wall = time.time() - t0
c = get("/__qa_probe/count")["post"]
print(
    json.dumps(
        {
            "tong_request": TOTAL,
            "song_song": CONC,
            "http_ok": sum(res),
            "http_fail": TOTAL - sum(res),
            "MODEL_CALLS": c,
            "giay": round(wall, 1),
            "call_moi_request": round(c / TOTAL, 3),
        },
        ensure_ascii=False,
    )
)
