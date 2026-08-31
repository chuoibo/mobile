"""Q1: does allocate() reject float AND bool at EVERY money slot?

Base expense is taken from the frozen golden corpus (not hand-written), then
one money slot at a time is poisoned with four shapes. Measured by behaviour.
"""

import copy
import glob
import json
import sys

sys.path.insert(0, ".")

from app.domain.allocator import allocate  # noqa: E402
from app.domain.contract import AllocationError  # noqa: E402


# Pick the richest golden vector: most money slots in one input.
def slots_of(inp):
    n = 1
    for k in ("items", "surcharges", "discounts"):
        n += len(inp.get(k) or [])
    return n


best = None
for f in sorted(glob.glob("tests/domain/golden/*.json")):
    for v in json.load(open(f)):
        if v.get("expect", {}).get("allocations") is None:
            continue  # error vectors have no allocations
        if best is None or slots_of(v["input"]) > slots_of(best[1]["input"]):
            best = (f, v)
src, vec = best
BASE = vec["input"]
print(f"nen duong lay tu {src} vector {vec['id']} -- {slots_of(BASE)} slot tien")


def call(exp):
    try:
        allocate(exp)
        return ("OK", "-")
    except AllocationError as e:
        return ("AllocationError", e.code)
    except Exception as e:  # noqa: BLE001 - measuring escapes
        return (type(e).__name__, str(e)[:55])


kind, payload = call(copy.deepcopy(BASE))
print(f"NEN DUONG (tat ca int): {kind} {payload}")
assert kind == "OK", "nen duong hong -- dung doc bang duoi"

# Money slots derived from the vector itself, not typed out.
SLOTS = [("total_vnd", lambda e, v: e.__setitem__("total_vnd", v))]
for coll in ("items", "surcharges", "discounts"):
    for i in range(len(BASE.get(coll) or [])):
        SLOTS.append(
            (
                f"{coll}[{i}].amount_vnd",
                lambda e, v, c=coll, i=i: e[c][i].__setitem__("amount_vnd", v),
            )
        )
POISONS = [
    ("float", 300.5),
    ("float_whole", 300.0),
    ("bool_True", True),
    ("bool_False", False),
]

print(f"\n{'slot':<30}{'doc':<13}{'ket qua':<18}{'ma'}")
print("-" * 88)
bad = []
for name, setter in SLOTS:
    for pname, pval in POISONS:
        e = copy.deepcopy(BASE)
        setter(e, pval)
        kind, payload = call(e)
        ok = kind == "AllocationError" and payload == "AMOUNT_NOT_INTEGER"
        if not ok:
            bad.append((name, pname, kind, payload))
        print(
            f"{name:<30}{pname:<13}{kind:<18}{payload}"
            f"{'' if ok else '   <-- KHONG PHAI AMOUNT_NOT_INTEGER'}"
        )
print("-" * 88)
print(
    f"So o tra dung AMOUNT_NOT_INTEGER: {len(SLOTS) * len(POISONS) - len(bad)}/{len(SLOTS) * len(POISONS)}"
)
for b in bad:
    print("  LECH:", b)
