"""Probe a pre-fix-seeded DB against the post-fix server, in the order that matters."""

import json
import pathlib
import sys
import urllib.error
import urllib.request

# repo root is four levels up: tests/qa/rd-qa-12/<this file>
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts"))
from seed_demo_data import MINH, OWNER_ROLES, GROUP_NAME, idempotency_key

API = "http://127.0.0.1:8713"
KEY = idempotency_key("context")

# The two encoders, byte for byte.
PY_BYTES = json.dumps({"display_name": GROUP_NAME}).encode(
    "utf-8"
)  # seed / thanNhuSeed
JS_BYTES = json.dumps(
    {"display_name": GROUP_NAME}, separators=(",", ":"), ensure_ascii=False
).encode("utf-8")  # JSON.stringify


def post(label, raw):
    req = urllib.request.Request(
        f"{API}/contexts",
        data=raw,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Actor-ID": str(MINH),
            "X-Actor-Roles": OWNER_ROLES,
            "Idempotency-Key": KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
            print(
                f"{label:<34} -> {r.status}  id={body.get('id')}  replayed={r.headers.get('Idempotency-Replayed')}"
            )
            return r.status
    except urllib.error.HTTPError as e:
        print(f"{label:<34} -> {e.code}  {e.read().decode()[:90]}")
        return e.code


print("key      =", KEY)
print("py bytes =", PY_BYTES)
print("js bytes =", JS_BYTES)
print()
print("PROBE 1 — app WITHOUT the thanNhuSeed workaround (plain JSON.stringify):")
r1 = post("  JSON.stringify", JS_BYTES)
print()
print("PROBE 2 — app AS SHIPPED today (thanNhuSeed = python bytes):")
r2 = post("  thanNhuSeed", PY_BYTES)
print()
print("PROBE 3 — JSON.stringify again, after the row healed:")
r3 = post("  JSON.stringify", JS_BYTES)
print()
print(f"RESULT  probe1={r1}  probe2={r2}  probe3={r3}")
