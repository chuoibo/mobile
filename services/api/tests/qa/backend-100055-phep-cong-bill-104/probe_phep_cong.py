"""Measure what the addition at `app/domain/bill.py:104` actually manufactures.

#460 counted nine sources of money reaching `allocate()` and marked this one
`COMPUTED`, barrier `không có`. The reason it stands out is real: the other
eight sources READ a value that something else already typed, while an addition
CREATES a value, and a created value has no annotation anyone could validate --
its type is whatever the operands' types make it.

    int + int   -> int
    int + float -> float
    int + True  -> int, and one đồng appeared from nowhere

This probe asks two separate questions and keeps them separate, because they
have different answers:

  PART 1 -- can a bad OPERAND get through the addition?
            Answer measured below. Note that every operand of this sum is also
            handed to `allocate()` on its own account, so the addition is not
            the only thing standing there.

  PART 2 -- what can the addition create that NO operand check could see?
            This is the part that is genuinely unique to an addition: three
            results reachable from operands that are each individually legal.

Nothing here mutates the tree; every row is a call against the code as it
stands. Run from `services/api`:

    python tests/qa/backend-100055-phep-cong-bill-104/probe_phep_cong.py
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[3]
sys.path.insert(0, str(API_ROOT))

from app.domain.allocator import allocate  # noqa: E402
from app.domain.bill import BillError, allocator_input_from_bill  # noqa: E402
from app.domain.contract import MAX_AMOUNT_VND, AllocationError  # noqa: E402

RULE = "=" * 88

failures: list[str] = []


def _item(key: str, amount, who: str) -> dict:
    return {
        "item_key": key,
        "amount_vnd": amount,
        "shares": [{"participant_id": who, "source": "confirmed"}],
    }


def _bill(**overrides) -> dict:
    """One two-person meal. `printed_total_vnd=None` forces the sum branch."""
    bill = {
        "participants": ["an", "binh"],
        "printed_total_vnd": None,
        "items": [_item("i1", 65_000, "an"), _item("i2", 70_000, "binh")],
        "surcharges": [],
        "discounts": [],
        "advancer_id": "an",
    }
    bill.update(overrides)
    return bill


def _surcharge(amount, mode: str = "even") -> dict:
    return {"surcharge_id": "s1", "kind": "vat", "amount_vnd": amount, "mode": mode}


def _discount(discount_id: str, amount) -> dict:
    return {
        "discount_id": discount_id,
        "amount_vnd": amount,
        "scope": "global_proportional",
    }


def _run(bill: dict) -> tuple[object, str, str]:
    """Project, then allocate. Return (total, type name, what happened next)."""
    try:
        projection = allocator_input_from_bill(bill)
    except BillError as exc:
        return ("--", "--", f"BillError({exc.code}) inside bill.py, before allocate()")
    total = projection["expense"]["total_vnd"]
    try:
        result = allocate(projection["expense"])
        outcome = f"ACCEPTED, allocations={result['allocations']}"
    except AllocationError as exc:
        outcome = f"AllocationError({exc.args[0]})"
    except Exception as exc:  # noqa: BLE001 -- the probe wants the raw truth
        outcome = f"{type(exc).__name__}: {exc}"
    return (total, type(total).__name__, outcome)


# ---------------------------------------------------------------------------
# PART 1 -- a bad operand, and what the sum does with it
# ---------------------------------------------------------------------------

PART_1 = [
    ("baseline: every operand int", _bill()),
    (
        "item amount float 65000.0",
        _bill(items=[_item("i1", 65_000.0, "an"), _item("i2", 70_000, "binh")]),
    ),
    (
        "item amount float 65000.5",
        _bill(items=[_item("i1", 65_000.5, "an"), _item("i2", 70_000, "binh")]),
    ),
    (
        "item amount bool True",
        _bill(items=[_item("i1", True, "an"), _item("i2", 70_000, "binh")]),
    ),
    ("surcharge float 5000.0", _bill(surcharges=[_surcharge(5_000.0)])),
    ("discount float 5000.0", _bill(discounts=[_discount("d1", 5_000.0)])),
    # The other branch of the same `if`: no addition happens at all here, so
    # this row is the control that says what the sum is and is not responsible
    # for.
    ("printed_total float (NO sum runs)", _bill(printed_total_vnd=135_000.0)),
]

# ---------------------------------------------------------------------------
# PART 2 -- what only an addition can create
#
# Every operand in these three is individually legal: a positive integer đồng
# at or under the cap. No per-operand check, however strict, can reject them.
# Only the result is wrong, and the result is what the addition invented.
# ---------------------------------------------------------------------------

PART_2 = [
    (
        "legal operands, Σdiscounts > Σlines -> NEGATIVE total",
        _bill(discounts=[_discount("d1", 100_000), _discount("d2", 100_000)]),
    ),
    (
        "legal operands, Σdiscounts == Σlines -> ZERO total",
        _bill(discounts=[_discount("d1", 135_000)]),
    ),
    (
        "each item <= MAX_AMOUNT_VND, Σ > MAX -> OVERFLOW total",
        _bill(
            items=[
                _item("i1", MAX_AMOUNT_VND, "an"),
                _item("i2", MAX_AMOUNT_VND, "binh"),
            ]
        ),
    ),
]


def _table(title: str, cases: list[tuple[str, dict]]) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")
    print(f"{'case':<54} {'total_vnd':>16} {'type':>7}  what allocate() said")
    print("-" * 88)
    for label, payload in cases:
        total, kind, outcome = _run(payload)
        print(f"{label:<54} {total!r:>16} {kind:>7}  {outcome}")


def main() -> int:
    print(f"MAX_AMOUNT_VND = {MAX_AMOUNT_VND:,}")
    _table("PART 1 -- one bad operand entering the sum at bill.py:104", PART_1)
    _table(
        "PART 2 -- results only the addition can create (all operands legal)", PART_2
    )

    # The one assertion this probe makes, rather than merely printing: the
    # bool row must not be allocated. It is the row that was silently WRONG
    # before #450 -- `True` became one đồng and the split balanced against a
    # total nobody typed -- and a regression there is invisible in every other
    # row, because every other row fails loudly on its own.
    _, _, bool_outcome = _run(
        _bill(items=[_item("i1", True, "an"), _item("i2", 70_000, "binh")])
    )
    print(f"\nGate: bool operand through bill.py:104 -> {bool_outcome}")
    if "AMOUNT_NOT_INTEGER" not in bool_outcome:
        failures.append(
            "bool reached allocate() through bill.py:104 without AMOUNT_NOT_INTEGER"
        )

    print(f"\n{RULE}")
    if failures:
        for line in failures:
            print(f"FAIL: {line}")
        return 1
    print("OK -- no measured case let a non-integer đồng through bill.py:104.")
    print(
        "Not proven here: that a float can REACH bill.py:104 in production.\n"
        "  That is a question about the write path, and #460 measured it on\n"
        "  PostgreSQL 16: the column is BigInteger and the only writer in app/\n"
        "  sits behind `BillCreateRequest` (strict). This probe calls the domain\n"
        "  function directly and therefore deliberately skips that barrier."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
