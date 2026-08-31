"""Q1b: does a poisoned amount ever become SILENTLY WRONG MONEY (no exception)?
Q2 : does the model_construct bypass (qa2 #452) reach a check?

Both run identically on pre-patch and post-patch trees; only the tree changes.
"""

import copy
import sys
import uuid

sys.path.insert(0, ".")

from app.api.schemas import ExpenseInput  # noqa: E402
from app.api.service import _allocator_input  # noqa: E402
from app.domain.allocator import allocate  # noqa: E402
from app.domain.contract import AllocationError  # noqa: E402

print("=" * 78)
print("A. TIEN SAI IM LANG -- allocate() tra ve mot con so, khong nem gi")
print("=" * 78)
CASES = {
    "total=True, item=True (bool thanh 1 dong)": {
        "participants": ["a", "b"],
        "total_vnd": True,
        "items": [{"item_id": "i1", "amount_vnd": True, "shared_by": ["a", "b"]}],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    },
    "even-split total=True (khong co item)": {
        "participants": ["a", "b"],
        "total_vnd": True,
        "items": [],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    },
    "even-split total=300.5": {
        "participants": ["a", "b"],
        "total_vnd": 300.5,
        "items": [],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    },
    "even-split total=300.0": {
        "participants": ["a", "b"],
        "total_vnd": 300.0,
        "items": [],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    },
    "total=301, item=300.5 (mismatch that)": {
        "participants": ["a", "b"],
        "total_vnd": 301,
        "items": [{"item_id": "i1", "amount_vnd": 300.5, "shared_by": ["a", "b"]}],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    },
}
silent = 0
for label, exp in CASES.items():
    try:
        r = allocate(copy.deepcopy(exp))
        alloc = r["allocations"] if isinstance(r, dict) and "allocations" in r else r
        print(f"  {label:<44} -> TRA VE {alloc}   <== KHONG NEM GI")
        silent += 1
    except AllocationError as e:
        print(f"  {label:<44} -> AllocationError {e.code}")
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<44} -> {type(e).__name__} THOAT RA NGOAI: {str(e)[:40]}")
print(
    f"\n  So ca allocate() tra ve so tien tu mot dau vao phi-int: {silent}/{len(CASES)}"
)

print()
print("=" * 78)
print("B. DUONG VONG model_construct (dung cach qa2 do o #452)")
print("=" * 78)

CTX = uuid.uuid4()
A = uuid.uuid4()
B = uuid.uuid4()
for label, poison in (("total=82000.5", 82000.5), ("total=True", True)):
    proposal = ExpenseInput.model_construct(
        context_id=CTX,
        description="Bua toi",
        recorded_by_id=A,
        paid_by_id=A,
        verification_scope="totals_only",
        occurred_at=None,
        participants=[A, B],
        total_amount_vnd=poison,
        items=[],
        surcharges=[],
        discounts=[],
    )
    dom = _allocator_input(proposal)
    got = dom["total_vnd"]
    print(f"  {label}")
    print(
        f"    _allocator_input -> total_vnd={got!r} ({type(got).__name__})"
        f"   (rao ep kieu? {'CO' if type(got) is int else 'KHONG'})"
    )
    try:
        r = allocate(dom)
        alloc = r["allocations"] if isinstance(r, dict) and "allocations" in r else r
        print(f"    allocate()       -> TRA VE {alloc}   <== DUONG VONG CON HO")
    except AllocationError as e:
        print(
            f"    allocate()       -> AllocationError {e.code}   <== DUONG VONG BI DONG"
        )
    except Exception as e:  # noqa: BLE001
        print(
            f"    allocate()       -> {type(e).__name__} thoat ra ngoai (-> HTTP 500)"
        )
