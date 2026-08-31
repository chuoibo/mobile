"""Law 1 on the way IN: no non-integer may be bound into a money column.

## The hole this closes, measured rather than assumed

Two sibling gates already stand on either side of storage:

* `test_money_columns_are_integer_postgres.py` (#486) proves every money
  *column* in the migrated schema is an exact integer type.
* `test_money_expressions_are_integer_postgres.py` (#488) proves every SQL
  *expression* handing money back to Python declares an exact integer type.

Both are about types the database declares. Neither says anything about the
Python value handed to an INSERT, and #486's own docstring is where the gap was
written down instead of guarded: *"the database is not the last line of
defence"*.

That sentence is easy to read as a caveat. It is not a caveat, it is the whole
defect, and the shape of it was measured on this repository's own PostgreSQL
16.14 against a `bigint` column before this file was written:

    int   300         ->  stored 300
    float 300.5       ->  stored 300     distorted, no error
    float 300.4       ->  stored 300     distorted, no error
    float 300.0       ->  stored 300
    Decimal("300.5")  ->  stored 301     distorted, no error
    Decimal("300")    ->  stored 300
    str   "300"       ->  stored 300     type laundered, no error
    bool  True        ->  REFUSED

Eight candidates, one refused, four silently changed. Two things in that table
are worth stating out loud because neither is what a reader expects:

1. **`bool` is the only shape a money column refuses.** Every other wrong type
   is accepted. So the reassuring mental model -- "it is a typed column, it
   will reject nonsense" -- is true for exactly the case that was never the
   risk, and false for every case that was.

2. **`float` and `Decimal` round in opposite directions.** The same half a
   đồng becomes 300 when a `float` carries it and 301 when a `Decimal` does.
   PostgreSQL rounds `float8` half-to-even and `numeric` half-away-from-zero,
   and the cast to `bigint` inherits whichever one applied. So the stored
   number depends on a Python type nobody chose deliberately.

The symptom of a float reaching money is therefore not a red test. It is a
wrong amount sitting quietly in the ledger with nothing raised anywhere, which
is Law 2 broken with no signal -- the failure mode this repository is least
equipped to notice, because every tier downstream reads the rounded value and
agrees with itself.

## What is checked, and what the unit of counting is

The rule is stated over *bind parameters*: every value bound to a money column
in an INSERT or UPDATE that actually ran must be exactly `int`, or `None`.

`type(value) is int`, never `isinstance`. `bool` subclasses `int` in Python, so
every `isinstance(x, int)` written to defend money says yes to `True` -- and
`True` is the one shape PostgreSQL would have caught for us. Checking it the
lazy way would blind the gate to the only case the database was covering.

The set of money columns is **read out of the schema Alembic migrated**, by
importing #486's own two helpers rather than restating them:

    from .test_money_columns_are_integer_postgres import _columns, _looks_like_money

That import is the point, not a convenience. Copying the derivation would
create two artifacts describing one thing, which is precisely the drift QA
caught in #488: a list and its driver disagreeing in silence. There is one
derivation, and if #486's notion of a money column changes, this gate's notion
changes with it in the same commit.

## What this gate does NOT prove -- read before quoting it

* **It does not cover a money column named outside the convention.** The money
  set comes from `_looks_like_money`, which reads names (`*_vnd`, `*amount*`).
  A `bigint` column holding đồng under some other name is invisible here.
  #486's type-side rule does not reach it either, since `bigint` is exactly
  what it wants to see. That column is unguarded by both gates.
* **It does not read inside `jsonb`.** Money nested in a JSON document is
  bound as one document-shaped parameter and is not inspected.
* **It only sees writes the driver reaches.** `MONEY_WRITE_SURFACE` is a
  hand-written map of named steps. Each step is forced to prove it still
  writes money (below), so a step cannot be gutted in silence -- but deleting
  a whole entry from the map still shrinks coverage, and nothing here stops
  that. `test_money_columns_never_written_by_the_driver` prints the columns
  nobody drove, so the blind spot has a visible boundary instead of a silent
  one.
* **It says nothing about whether the number is arithmetically right.** An
  `int` that is the wrong `int` passes every assertion in this file. The 41
  golden vectors are where that lives.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .test_money_columns_are_integer_postgres import _columns, _looks_like_money
from .test_person_finance_postgres import SHARE_VND, Slice

# `Slice` carries the fixture; it is imported rather than re-created so there is
# one description of the vertical slice. Guarding against it being hollowed out
# is `test_every_write_step_actually_binds_money` below, which is the reason a
# shared fixture is safe to lean on here.
pytestmark = pytest.mark.usefixtures("postgres_engine")


# INSERT INTO "schema"."table" / UPDATE schema.table -- the target of the write.
_WRITE_TARGET = re.compile(
    r'\b(?:INSERT\s+INTO|UPDATE)\s+(?:"?[\w$]+"?\.)?"?([\w$]+)"?',
    re.IGNORECASE,
)

# SQLAlchemy suffixes bind names when one column appears more than once in a
# statement: `total_vnd_m0` (insertmanyvalues), `total_vnd__1`, `total_vnd_1`.
_BIND_SUFFIX = re.compile(r"__?m?\d+$")


def _base_bind_name(name: str) -> str:
    """Strip the disambiguating suffixes back to the column name."""

    previous = None
    while previous != name:
        previous = name
        name = _BIND_SUFFIX.sub("", name)
    return name


@dataclass
class MoneyBinding:
    """One value bound to one money column by one statement that ran."""

    table: str
    column: str
    value: Any

    @property
    def is_lawful(self) -> bool:
        # `type(...) is int` on purpose: bool subclasses int, and bool is the
        # one wrong type the column itself would have refused.
        return self.value is None or type(self.value) is int

    def __str__(self) -> str:
        return (
            f"{self.table}.{self.column} <- {self.value!r} "
            f"({type(self.value).__name__})"
        )


@dataclass
class WriteRecorder:
    """Every money bind parameter of every INSERT/UPDATE that executed."""

    money_columns: dict[str, frozenset[str]]
    bindings: list[MoneyBinding] = field(default_factory=list)
    statements_seen: int = 0

    def unlawful(self) -> list[MoneyBinding]:
        return [binding for binding in self.bindings if not binding.is_lawful]

    def observe(self, statement: str, parameters: Any) -> None:
        match = _WRITE_TARGET.search(statement)
        if match is None:
            return
        self.statements_seen += 1
        columns = self.money_columns.get(match.group(1).lower())
        if not columns:
            return
        for row in self._rows(parameters):
            for name, value in row.items():
                column = _base_bind_name(str(name))
                if column in columns:
                    self.bindings.append(
                        MoneyBinding(match.group(1).lower(), column, value)
                    )

    @staticmethod
    def _rows(parameters: Any) -> Iterator[dict]:
        """`executemany` hands a sequence of dicts; `execute` hands one."""

        if isinstance(parameters, dict):
            yield parameters
        elif isinstance(parameters, list | tuple):
            for row in parameters:
                if isinstance(row, dict):
                    yield row


def _money_columns_by_table(engine: Engine) -> dict[str, frozenset[str]]:
    """Money columns of the migrated schema, grouped by table.

    Derived from `information_schema` through #486's helpers. A money column
    added tomorrow appears here without anyone editing this file.
    """

    grouped: dict[str, set[str]] = {}
    for table, column, _data_type in _columns(engine):
        if _looks_like_money(column):
            grouped.setdefault(table.lower(), set()).add(column)
    if not grouped:
        raise AssertionError(
            "KHONG TIM THAY COT TIEN NAO trong schema da migrate -- phep dan xuat "
            "hong, khong phai schema sach. Cong nay khong ket luan duoc gi."
        )
    return {table: frozenset(columns) for table, columns in grouped.items()}


@contextmanager
def recording(engine: Engine) -> Iterator[WriteRecorder]:
    recorder = WriteRecorder(_money_columns_by_table(engine))

    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):  # noqa: ANN001, ARG001 - SQLAlchemy's event signature
        recorder.observe(statement, parameters)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield recorder
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


# --------------------------------------------------------------------------
# The driven surface. Steps are a name -> callable map so the name and the call
# cannot drift apart: there is no second list to keep in step with this one.
# Each step is handed the shared `Slice` and a `state` dict, because the money
# path is sequential -- an obligation cannot be published before the expense it
# came from is confirmed.
# --------------------------------------------------------------------------


def _step_confirm_expense(slice_: Slice, state: dict) -> None:
    _expense_id, confirmation = slice_.confirm_expense()
    state["expense_version_id"] = confirmation.expense_version_id


def _step_publish_batch(slice_: Slice, state: dict) -> None:
    state["obligation_id"] = slice_.publish(state["expense_version_id"])


def _step_report_payment(slice_: Slice, state: dict) -> None:
    slice_.report_payment(state["obligation_id"], minute=5)


def _step_confirm_receipt(slice_: Slice, state: dict) -> None:
    slice_.confirm_receipt(state["obligation_id"], SHARE_VND, minute=7)


MONEY_WRITE_SURFACE: dict[str, Callable[[Slice, dict], None]] = {
    # save_expense_confirmation -- expense versions, rollups, allocations
    "confirm_expense": _step_confirm_expense,
    # save_frozen_batch + save_published_batch -- obligations and their envelope
    "publish_batch": _step_publish_batch,
    # save_payment_report -- the guest's own claim that they transferred
    "report_payment": _step_report_payment,
    # save_receipt_confirmation -- the ledger row a balance is recomputed from
    "confirm_receipt": _step_confirm_receipt,
}


def _drive(slice_: Slice, recorder: WriteRecorder) -> dict[str, int]:
    """Run every named step, counting the money binds each one contributes."""

    state: dict = {}
    per_step: dict[str, int] = {}
    for name, step in MONEY_WRITE_SURFACE.items():
        before = len(recorder.bindings)
        step(slice_, state)
        per_step[name] = len(recorder.bindings) - before
    return per_step


# --------------------------------------------------------------------------
# The law.
# --------------------------------------------------------------------------


def test_no_money_column_is_ever_written_a_non_integer(
    postgres_session: Session,
) -> None:
    """Law 1 at the bind site: every money value written is an `int`."""

    slice_ = Slice(postgres_session)
    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        _drive(slice_, recorder)

    offenders = recorder.unlawful()
    assert not offenders, "gia tri khong phai int duoc ghi vao cot tien:\n" + "\n".join(
        f"  {binding}" for binding in offenders
    )


def test_recorder_observed_money_writes_at_all(postgres_session: Session) -> None:
    """Fail closed. Every assertion above has the shape "nothing matched", and
    a recorder that saw nothing satisfies that shape for free."""

    slice_ = Slice(postgres_session)
    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        _drive(slice_, recorder)

    assert recorder.statements_seen > 0, (
        "KHONG QUAN SAT DUOC CAU GHI NAO -- listener chet, khong phai cay sach"
    )
    assert recorder.bindings, (
        "KHONG QUAN SAT DUOC LAN GHI TIEN NAO -- cong nay khong ket luan duoc gi"
    )


def test_every_write_step_actually_binds_money(postgres_session: Session) -> None:
    """Anti-drift, and the reason leaning on a shared fixture is safe.

    A step that stops reaching its write -- gutted body, a fixture that no
    longer gets past an early return, an import that quietly became a no-op --
    shrinks what this gate measures while every other assertion here stays
    green, because "nothing unlawful was bound" is satisfied perfectly by
    binding nothing. A floor over the whole run (`bindings > 0`) does not
    catch it either: three of four steps still clear it.

    So the floor is per step. This is the same failure QA found in #488, and
    the answer is the one they prescribed there.
    """

    slice_ = Slice(postgres_session)
    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        per_step = _drive(slice_, recorder)

    silent = [name for name, count in per_step.items() if count == 0]
    assert not silent, (
        "buoc lai khong ghi mot dong tien nao, nen no khong do gi: "
        + ", ".join(silent)
        + f"\nso lan bind moi buoc: {per_step}"
    )


# --------------------------------------------------------------------------
# Positive controls. Every assertion above is "nothing matched", which a broken
# recorder satisfies trivially. These run on every invocation, so a gate that
# has stopped being able to see anything fails here first.
# --------------------------------------------------------------------------


KNOWN_BAD_VALUES = [
    pytest.param(300.5, id="float-300.5"),
    pytest.param(300.0, id="float-300.0-integral"),
    pytest.param(Decimal("300.5"), id="Decimal-300.5"),
    pytest.param(Decimal("300"), id="Decimal-300-integral"),
    pytest.param("300", id="str-300"),
    pytest.param(True, id="bool-True"),
]


def _drive_to_obligation(slice_: Slice) -> uuid.UUID:
    """Confirm an expense and publish it, returning something to be paid."""

    _expense_id, confirmation = slice_.confirm_expense()
    return slice_.publish(confirmation.expense_version_id)


@pytest.mark.parametrize("bad_value", KNOWN_BAD_VALUES)
def test_recorder_catches_a_non_int_on_the_real_write_path(
    postgres_session: Session, bad_value: object
) -> None:
    """A value this gate exists to refuse must make it red, and be named.

    The control goes through `save_receipt_confirmation`, not through a scratch
    table, because that method hands `amount_vnd` to the ORM with no cast of
    any kind -- so this is the production path a float actually travels, and
    the control measures the gate's reach over that path rather than over a toy
    one built to be reachable.

    The integral shapes are in the list deliberately. `300.0` and
    `Decimal("300")` store the right number, so no assertion on the amount
    downstream can ever notice them -- and they are the shapes that really
    arrive, because JavaScript has no integer type. A gate that only caught the
    ones that change the number would pass on the day floats became normal and
    fail only later, once one happened to carry a fraction.
    """

    slice_ = Slice(postgres_session)
    obligation_id = _drive_to_obligation(slice_)

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        try:
            slice_.confirm_receipt(obligation_id, bad_value, minute=7)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - `bool` is refused by the column itself
            postgres_session.rollback()

    offenders = recorder.unlawful()
    assert offenders, f"may quan sat KHONG bat duoc {bad_value!r} tren duong ghi that"
    assert any(binding.column == "amount_vnd" for binding in offenders), (
        f"bat duoc nhung khong neu dung ten cot: {[str(b) for b in offenders]}"
    )


def test_recorder_passes_a_value_known_to_be_lawful(postgres_session: Session) -> None:
    """The other half of the control: a plain `int` must not be flagged.

    Without this, a recorder that called everything unlawful would satisfy
    every test above it and look like the strictest gate in the repository.
    """

    slice_ = Slice(postgres_session)
    obligation_id = _drive_to_obligation(slice_)

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        slice_.confirm_receipt(obligation_id, SHARE_VND, minute=7)

    assert not recorder.unlawful(), "int hop le bi bao la vi pham"
    assert recorder.bindings, "khong quan sat duoc lan ghi nao ca"


def test_the_column_itself_refuses_almost_nothing(postgres_session: Session) -> None:
    """Why this file exists: the `bigint` column is not the barrier.

    Pinned as behaviour rather than prose, and pinned on the ledger table a
    balance is recomputed from. If PostgreSQL ever starts refusing these, this
    test fails and whoever reads the docstring above finds it out of date --
    better than the docstring quietly becoming a lie.
    """

    slice_ = Slice(postgres_session)
    obligation_id = _drive_to_obligation(slice_)

    stored: dict[str, object] = {}
    for minute, (label, value) in enumerate(
        (("float", 300.5), ("decimal", Decimal("300.5")), ("str", "300")), start=7
    ):
        record = slice_.confirm_receipt(obligation_id, value, minute=minute)  # type: ignore[arg-type]
        stored[label] = postgres_session.execute(
            text("select amount_vnd from receipt_confirmations where id = :id"),
            {"id": record.id},
        ).scalar()

    refused = False
    try:
        slice_.confirm_receipt(obligation_id, True, minute=11)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 - the refusal is the observation
        postgres_session.rollback()
        refused = True

    assert stored["float"] == 300, (
        f"float 300.5 khong con duoc lam tron xuong 300: {stored['float']!r}"
    )
    assert stored["decimal"] == 301, (
        f"Decimal('300.5') khong con duoc lam tron len 301: {stored['decimal']!r}"
    )
    assert stored["float"] != stored["decimal"], (
        "float va Decimal da lam tron cung huong -- doc lai docstring file nay"
    )
    assert stored["str"] == 300, f"chuoi '300' khong con duoc nhan: {stored['str']!r}"
    assert refused, "bool da thoi bi tu choi -- cot con it hang rao hon truoc"


# --------------------------------------------------------------------------
# The blind spot, made visible rather than left silent.
# --------------------------------------------------------------------------


def test_money_columns_never_written_by_the_driver(postgres_session: Session) -> None:
    """Print the money columns no step reached. Deliberately not an assertion.

    Pinning this set would make it a second hand-written list, and a stale one
    the first time a lane adds a money table. Printing it keeps the boundary of
    what the gate covers readable by anyone running with `-s`, which is the
    difference between a bounded blind spot and a silent one.
    """

    slice_ = Slice(postgres_session)
    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        _drive(slice_, recorder)

    every = {
        f"{table}.{column}"
        for table, columns in recorder.money_columns.items()
        for column in columns
    }
    written = {f"{b.table}.{b.column}" for b in recorder.bindings}
    unwritten = sorted(every - written)

    print(
        f"\ncot tien trong schema: {len(every)}"
        f" | duoc lai cham toi: {len(every) - len(unwritten)}"
        f" | KHONG duoc lai cham: {len(unwritten)}"
    )
    for name in unwritten:
        print(f"  chua phu: {name}")
