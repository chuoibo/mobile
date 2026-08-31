"""Law 1 on the storage side: no money column may hold a non-integer type.

## What this gate counts, and why that unit was chosen

The unit of counting is **the schema Alembic actually migrated**, read back out
of ``information_schema.columns``. It is not a hand-written list of column
names. A hand-written list cannot notice a column nobody added it to, so it
reports "all clear" for exactly the change it was supposed to catch.

The enumeration here is complete by construction: every column in the migrated
schema is classified, and the classification is **deny by default**. A money
column added tomorrow is caught whatever it is called, because the rule is
stated over the column's *type*, not over its *name*:

    every inexact-numeric column must appear in INEXACT_COLUMNS_REVIEWED

So ``numeric``, ``real``, ``double precision`` and ``money`` cannot enter the
schema unnoticed. The reviewed set is two geographic coordinates, and each
entry carries the reason it is not money. Adding a third entry is a visible,
reviewable act in a diff -- which is the point.

A second, name-side rule runs the other way and catches money stored in a type
that is not numeric at all (``text``, ``varchar``, ``jsonb``): every column
named like money must be an exact integer type. Neither rule subsumes the
other, and a money column has to satisfy both.

## What this gate does NOT prove -- read this before quoting it

* **It is about STORAGE, not EXPRESSIONS.** ``bigint`` columns say nothing
  about what a *query* returns. PostgreSQL widens to ``numeric`` in places the
  column types cannot predict -- ``sum()``, ``avg()``, ``round()``, integer
  division, a numeric literal mixed into an expression, or raw ``text("...")``
  SQL. That class of defect was real (#475: ``func.sum()`` returned ``Decimal``
  out of ``app/db/repository.py``) and this gate would not have caught it.
  There is no count over column types that answers "every SQL expression
  returning money is an int"; that question is answered at runtime, on the
  values the repository actually hands back.
* **It does not read inside ``jsonb``.** PostgreSQL applies no numeric type to
  a value nested in a JSON document, so money inside ``jsonb`` is outside every
  rule stated here. The blind spot is bounded rather than silent: the jsonb
  columns are enumerated from the same migrated schema and pinned below, so a
  *new* jsonb column cannot appear without a reviewer seeing this file.
* **The database is not the last line of defence.** Sending a float to a
  ``bigint`` column does not raise -- PostgreSQL rounds it and stores the
  rounded value (300.5 -> 300). The refusal people expect from a typed column
  only happens for a few types, such as ``bool``. A float that leaks this far
  is stored silently and wrong, with no error anywhere. The real last line is
  the type check in ``allocate()`` and the pydantic boundary.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

# PostgreSQL types that cannot represent "đồng" exactly, or that carry a
# fractional part Law 1 forbids money from ever having.
INEXACT_SQL_TYPES = frozenset(
    {"numeric", "decimal", "real", "double precision", "money"}
)

# The only types a money column may use.
EXACT_INTEGER_TYPES = frozenset({"smallint", "integer", "bigint"})

# Deny by default: an inexact column NOT listed here fails the gate. Each entry
# states why it is not money. Two geographic coordinates, and nothing else.
INEXACT_COLUMNS_REVIEWED: dict[tuple[str, str], str] = {
    ("memories", "lat"): "geographic latitude of a memory, not an amount",
    ("memories", "lng"): "geographic longitude of a memory, not an amount",
}

# jsonb is untyped as far as money is concerned. These are pinned so that a new
# jsonb column has to pass through this file, where the blind spot is written
# down, instead of arriving unnoticed.
JSONB_COLUMNS_REVIEWED: dict[tuple[str, str], str] = {
    ("audit_events", "event_data"): (
        "append-only audit payload; amounts inside are a copy of ledger rows, "
        "never the source a balance is recomputed from"
    ),
    ("messages", "card"): (
        "rendered chat card; amounts inside are display copies of ledger rows"
    ),
}


def _looks_like_money(column_name: str) -> bool:
    """Name-side heuristic, used only to make the type rule stricter."""

    return column_name.endswith("_vnd") or "amount" in column_name


def _columns(engine: Engine) -> list[tuple[str, str, str]]:
    """Read every column of the schema Alembic migrated for this session."""

    with engine.connect() as connection:
        schema = connection.scalar(text("select current_schema()"))
        rows = connection.execute(
            text(
                """
                select table_name, column_name, data_type
                from information_schema.columns
                where table_schema = :schema
                order by table_name, column_name
                """
            ),
            {"schema": schema},
        ).fetchall()
    return [(row.table_name, row.column_name, row.data_type) for row in rows]


def _unreviewed_inexact(columns: list[tuple[str, str, str]]) -> list[str]:
    return [
        f"{table}.{column} :: {data_type}"
        for table, column, data_type in columns
        if data_type in INEXACT_SQL_TYPES
        and (table, column) not in INEXACT_COLUMNS_REVIEWED
    ]


def _money_named_not_integer(columns: list[tuple[str, str, str]]) -> list[str]:
    return [
        f"{table}.{column} :: {data_type}"
        for table, column, data_type in columns
        if _looks_like_money(column) and data_type not in EXACT_INTEGER_TYPES
    ]


def test_schema_enumeration_is_not_empty(postgres_engine: Engine) -> None:
    """A gate whose input list is empty passes by saying nothing.

    Both rules below are "no row satisfies X". An empty enumeration satisfies
    them for free, so the schema read has to be shown non-empty first or the
    green means nothing.
    """

    columns = _columns(postgres_engine)
    assert len(columns) > 200, f"migrated schema looks truncated: {len(columns)}"
    money_named = [c for c in columns if _looks_like_money(c[1])]
    assert len(money_named) >= 20, f"money columns missing: {len(money_named)}"


def test_no_unreviewed_inexact_numeric_column(postgres_engine: Engine) -> None:
    """Name-blind rule: no numeric/real/double column may enter unreviewed."""

    offenders = _unreviewed_inexact(_columns(postgres_engine))
    assert offenders == [], (
        "inexact-numeric column(s) in the migrated schema with no review entry: "
        + ", ".join(offenders)
        + ". If it holds money, Law 1 says make it bigint. If it does not, add "
        "it to INEXACT_COLUMNS_REVIEWED with the reason."
    )


def test_every_money_named_column_is_exact_integer(postgres_engine: Engine) -> None:
    """Name-side rule: catches money stored as text/varchar/jsonb."""

    offenders = _money_named_not_integer(_columns(postgres_engine))
    assert offenders == [], (
        "money-named column(s) that are not an exact integer type: "
        + ", ".join(offenders)
    )


def test_reviewed_entries_still_describe_the_schema(postgres_engine: Engine) -> None:
    """The review lists must not rot into permanent, unexamined exemptions.

    An allowlist that keeps entries for columns that changed type or no longer
    exist widens the gate silently forever. Every entry has to still be a real
    column of the kind it claims to excuse.
    """

    columns = _columns(postgres_engine)
    by_key = {(table, column): data_type for table, column, data_type in columns}

    stale = [
        f"{table}.{column}"
        for (table, column) in INEXACT_COLUMNS_REVIEWED
        if by_key.get((table, column)) not in INEXACT_SQL_TYPES
    ]
    assert stale == [], (
        "INEXACT_COLUMNS_REVIEWED entries that are no longer inexact columns "
        f"(drop them): {', '.join(stale)}"
    )

    stale_json = [
        f"{table}.{column}"
        for (table, column) in JSONB_COLUMNS_REVIEWED
        if by_key.get((table, column)) != "jsonb"
    ]
    assert stale_json == [], (
        f"JSONB_COLUMNS_REVIEWED entries that are no longer jsonb: "
        f"{', '.join(stale_json)}"
    )

    unpinned_json = [
        f"{table}.{column}"
        for table, column, data_type in columns
        if data_type == "jsonb" and (table, column) not in JSONB_COLUMNS_REVIEWED
    ]
    assert unpinned_json == [], (
        "new jsonb column(s) not pinned here: "
        + ", ".join(unpinned_json)
        + ". Money nested in jsonb is outside every rule in this file; say so "
        "in JSONB_COLUMNS_REVIEWED before adding it."
    )


@pytest.mark.parametrize(
    ("sql_type", "column_name", "caught_by_type_rule", "caught_by_name_rule"),
    [
        # A money column somebody typed as numeric. Caught name-blind.
        ("numeric(12, 2)", "amount_vnd", True, True),
        # A money column named nothing like money -- the case a hand-written
        # name list is structurally unable to notice.
        ("numeric(12, 2)", "gia_tri", True, False),
        ("double precision", "gia_tri", True, False),
        # Money stored outside the numeric family: invisible to the type rule,
        # which is why the name rule exists.
        ("text", "amount_vnd", False, True),
        ("jsonb", "total_amount_vnd", False, True),
    ],
)
def test_detector_catches_a_column_known_to_be_wrong(
    postgres_engine: Engine,
    sql_type: str,
    column_name: str,
    caught_by_type_rule: bool,
    caught_by_name_rule: bool,
) -> None:
    """Positive control: plant a column known to be wrong, re-run the real query.

    Without this, every assertion above is "no rows matched", which a broken
    query satisfies just as well as a clean schema. The canary goes into the
    same migrated schema and is read back by the same ``_columns`` call, so it
    exercises the query the gate actually depends on -- not a hand-fed list.
    """

    with postgres_engine.begin() as connection:
        connection.execute(
            text(f'create table gate_canary ("{column_name}" {sql_type})')
        )
    try:
        columns = _columns(postgres_engine)
        assert ("gate_canary", column_name) in {
            (table, column) for table, column, _ in columns
        }, "canary column did not appear in the schema read"

        type_rule = [c for c in _unreviewed_inexact(columns) if "gate_canary" in c]
        name_rule = [c for c in _money_named_not_integer(columns) if "gate_canary" in c]

        assert bool(type_rule) is caught_by_type_rule, (
            f"type rule on {column_name} {sql_type}: expected "
            f"caught={caught_by_type_rule}, got {type_rule}"
        )
        assert bool(name_rule) is caught_by_name_rule, (
            f"name rule on {column_name} {sql_type}: expected "
            f"caught={caught_by_name_rule}, got {name_rule}"
        )
        assert caught_by_type_rule or caught_by_name_rule, (
            "this row claims neither rule catches the column, which would make "
            "it a documented hole rather than a control"
        )
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(text("drop table if exists gate_canary"))


def test_reviewed_inexact_columns_are_not_a_blanket_exemption(
    postgres_engine: Engine,
) -> None:
    """The review list must exempt only what it names, not the whole type.

    A canary named exactly like a reviewed column but living in another table
    must still be caught; otherwise ``lat``/``lng`` would have quietly licensed
    every ``double precision`` column in the schema.
    """

    with postgres_engine.begin() as connection:
        connection.execute(text("create table gate_canary_geo (lat double precision)"))
    try:
        offenders = _unreviewed_inexact(_columns(postgres_engine))
        assert any("gate_canary_geo.lat" in o for o in offenders), (
            "a reviewed column name exempted the same name in a different "
            f"table: {offenders}"
        )
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(text("drop table if exists gate_canary_geo"))
