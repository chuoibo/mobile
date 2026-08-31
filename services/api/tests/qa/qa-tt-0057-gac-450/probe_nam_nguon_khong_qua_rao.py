"""Does #450 stop the five sources that never meet the pydantic rail?

#460 counted money reaching ``allocate()`` by SOURCE and found nine, of which
five never pass ``MoneyVnd``: four read straight off a stored bill record and
one computed by the addition at ``app/domain/bill.py:104``. The rail lives on
``POST /expenses``; ``POST /bills/{id}/split`` carries no money field at all, so
those five values are never seen by pydantic in any request.

The question this probe answers is behavioural, not textual: drive a bad shape
in at each of the five sources through the real projection
(``allocator_input_from_bill``) into the real ``allocate()``, and record what
comes back. Run the same file at the commit before #450 to see what those same
five sources did then.

Verdict per cell:
    BLOCKED    AllocationError(AMOUNT_NOT_INTEGER) -- the shape gate fired
    OTHER_CODE AllocationError with a different code -- right refusal, wrong reason
    CRASH      a non-AllocationError escaped -- ADR-0004 7.2 property 10 violated
    WRONG      allocate() returned a result built from a non-integer amount
"""

from __future__ import annotations

import sys

from app.domain.allocator import allocate
from app.domain.bill import SHARE_CONFIRMED, allocator_input_from_bill
from app.domain.contract import AllocationError


def _share(participant_id: str) -> dict:
    return {"participant_id": participant_id, "source": SHARE_CONFIRMED}


def _bill(**overrides) -> dict:
    """The two-person meal from tests/domain/test_bill_projection.py."""
    bill = {
        "participants": ["an", "binh"],
        "printed_total_vnd": 135_000,
        "items": [
            {"item_key": "i1", "amount_vnd": 65_000, "shares": [_share("an")]},
            {"item_key": "i2", "amount_vnd": 70_000, "shares": [_share("binh")]},
        ],
        "surcharges": [],
        "discounts": [],
        "advancer_id": "an",
    }
    bill.update(overrides)
    return bill


# The four shapes a stored record can carry that pydantic would have refused.
# ``135_000.0`` matters on its own: it is numerically the right amount, so a
# gate that compared values instead of shapes would wave it through.
SHAPES = [
    ("float le", 0.5),
    ("float .0", 0.0),
    ("bool True", True),
    ("bool False", False),
]


def _item_slot(bad, base: int):
    """DB_RECORD 1: one line amount read off the record."""
    value = bad if isinstance(bad, bool) else base + bad
    return _bill(
        printed_total_vnd=None,
        items=[
            {"item_key": "i1", "amount_vnd": value, "shares": [_share("an")]},
            {"item_key": "i2", "amount_vnd": 70_000, "shares": [_share("binh")]},
        ],
    )


def _surcharge_slot(bad, base: int):
    """DB_RECORD 2: a surcharge amount read off the record."""
    value = bad if isinstance(bad, bool) else base + bad
    return _bill(
        printed_total_vnd=None,
        surcharges=[
            {
                "surcharge_id": "s1",
                "amount_vnd": value,
                "kind": "service",
                "mode": "proportional",
            }
        ],
    )


def _discount_slot(bad, base: int):
    """DB_RECORD 3: a discount amount read off the record."""
    value = bad if isinstance(bad, bool) else base + bad
    return _bill(
        printed_total_vnd=None,
        discounts=[
            {
                "discount_id": "d1",
                "amount_vnd": value,
                "scope": "global_proportional",
            },
        ],
    )


def _printed_total_slot(bad, base: int):
    """DB_RECORD 4: the total read off the paper and stored."""
    value = bad if isinstance(bad, bool) else base + bad
    return _bill(printed_total_vnd=value)


def _computed_slot(bad, base: int):
    """COMPUTED: bill.py:104 adds the lines when no printed total was stored.

    This is the addition the lead asked about by name: int + int stays int,
    int + float becomes float. The bill carries NO printed total, so the sum
    at line 104 is the value that reaches ``allocate()`` as ``total_vnd``.
    """
    value = bad if isinstance(bad, bool) else base + bad
    return _bill(
        printed_total_vnd=None,
        items=[
            {"item_key": "i1", "amount_vnd": value, "shares": [_share("an")]},
            {"item_key": "i2", "amount_vnd": 70_000, "shares": [_share("binh")]},
        ],
    )


SLOTS = [
    ("DB_RECORD item.amount_vnd", _item_slot, 65_000),
    ("DB_RECORD surcharge.amount_vnd", _surcharge_slot, 10_000),
    ("DB_RECORD discount.amount_vnd", _discount_slot, 5_000),
    ("DB_RECORD printed_total_vnd", _printed_total_slot, 135_000),
    ("COMPUTED bill.py:104 sum", _computed_slot, 65_000),
]


def _run(bill: dict) -> tuple[str, str]:
    """Return (verdict, detail) for one bad-shape bill."""
    try:
        projected = allocator_input_from_bill(bill)
    except Exception as exc:  # noqa: BLE001 - projection refusal is a result too
        return "PROJ_" + type(exc).__name__, str(exc)

    total = projected["expense"]["total_vnd"]
    carried = f"total_vnd={total!r} ({type(total).__name__})"

    try:
        result = allocate(projected["expense"])
    except AllocationError as exc:
        verdict = "BLOCKED" if exc.code == "AMOUNT_NOT_INTEGER" else "OTHER_CODE"
        return verdict, f"{exc.code} | {carried}"
    except Exception as exc:  # noqa: BLE001 - a crash is the finding
        return "CRASH", f"{type(exc).__name__}: {exc} | {carried}"
    return "WRONG", f"allocations={result['allocations']} | {carried}"


def main() -> int:
    print("=" * 78)
    print("NAM NGUON KHONG QUA RAO MoneyVnd -- do qua allocator_input_from_bill")
    print("=" * 78)

    # Positive control first. Without it a table of refusals cannot be told
    # apart from an import that never reached the allocator at all.
    baseline = allocate(allocator_input_from_bill(_bill())["expense"])
    ok = baseline["allocations"] == {"an": 65_000, "binh": 70_000}
    print(f"\n[doi chung duong] bill sach -> {baseline['allocations']}  {'OK' if ok else 'HONG'}")
    if not ok:
        print("!! doi chung duong HONG -- moi so duoi day vo nghia")
        return 3

    tally: dict[str, int] = {}
    for slot_name, builder, base in SLOTS:
        print(f"\n--- {slot_name}")
        for shape_name, bad in SHAPES:
            verdict, detail = _run(builder(bad, base))
            tally[verdict] = tally.get(verdict, 0) + 1
            print(f"    {shape_name:<12} {verdict:<11} {detail}")

    # The laundering case the lead named: bool + int is int, so the addition at
    # line 104 DESTROYS the evidence. A gate that only checked the computed
    # total would see a clean integer here.
    print("\n--- COMPUTED lam SACH bang chung (True + 70000 = 70001, kieu int)")
    laundered = _bill(
        printed_total_vnd=None,
        items=[
            {"item_key": "i1", "amount_vnd": True, "shares": [_share("an")]},
            {"item_key": "i2", "amount_vnd": 70_000, "shares": [_share("binh")]},
        ],
    )
    projected = allocator_input_from_bill(laundered)
    total = projected["expense"]["total_vnd"]
    print(f"    tong sau phep cong: {total!r} ({type(total).__name__}) <- SACH")
    verdict, detail = _run(laundered)
    tally[verdict] = tally.get(verdict, 0) + 1
    print(f"    ket qua allocate(): {verdict:<11} {detail}")

    print("\n" + "=" * 78)
    print("TONG: " + " · ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print("=" * 78)

    leaked = tally.get("WRONG", 0) + tally.get("CRASH", 0)
    return 0 if leaked == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
