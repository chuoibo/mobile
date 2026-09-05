"""Law 1 on the storage side: no money column may hold a non-integer type.

## What this gate counts, and why that unit was chosen

The table-level completeness unit is **the SQLAlchemy model metadata**, compared
with the tables returned by ``information_schema.columns``. It is not a
hand-written list of table or column names. A hand-written list cannot notice a
table nobody added to it, so it reports "all clear" for exactly the change it
was supposed to catch.

The schema read is not assumed complete merely because it returns many rows.
Every model table must be represented in the read, and every returned column is
then classified **deny by default**. Within the numeric family, a money column
added tomorrow is caught whatever it is called, because the rule is stated over
the column's *type*, not over its *name*:

    every inexact-numeric column must appear in INEXACT_COLUMNS_REVIEWED

So ``numeric``, ``real``, ``double precision`` and ``money`` cannot enter the
schema unnoticed. The reviewed set is two geographic coordinates, and each
entry carries the reason it is not money. Adding a third entry is a visible,
reviewable act in a diff -- which is the point.

A second, name-side rule runs the other way and catches money stored in a type
that is not numeric at all (``text``, ``varchar``, ``jsonb``) when the column
matches the repository's ``_vnd``/``amount`` naming convention. Neither rule
subsumes the other, and the naming heuristic is intentionally not exhaustive.

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
* **A money column can evade both rules by using both an unconventional name
  and a type outside the numeric family.** For example, ``gia_tri text`` and
  ``total text`` match neither detector. The last line of defence for this gap
  is the type check in ``allocate()`` plus the pydantic boundary, not a longer
  hand-written name list here.
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

from app.db.models import Base

# PostgreSQL types that cannot represent "đồng" exactly, or that carry a
# fractional part Law 1 forbids money from ever having.
INEXACT_SQL_TYPES = frozenset(
    {"numeric", "decimal", "real", "double precision", "money"}
)

# The only types a money column may use.
EXACT_INTEGER_TYPES = frozenset({"smallint", "integer", "bigint"})

# Deny by default: an inexact column NOT listed here fails the gate. Each entry
# states why it is not money. Coordinates, a bounding box, a star rating and a
# distance -- nothing anybody pays.
INEXACT_COLUMNS_REVIEWED: dict[tuple[str, str], str] = {
    ("memories", "lat"): "geographic latitude of a memory, not an amount",
    ("memories", "lng"): "geographic longitude of a memory, not an amount",
    # M9 (ADR-0017), the catalogue as tables.
    ("destinations", "lat"): "geographic latitude of a destination centre",
    ("destinations", "lng"): "geographic longitude of a destination centre",
    ("destinations", "bbox_south"): "bounding box the OSM import reads, degrees",
    ("destinations", "bbox_west"): "bounding box the OSM import reads, degrees",
    ("destinations", "bbox_north"): "bounding box the OSM import reads, degrees",
    ("destinations", "bbox_east"): "bounding box the OSM import reads, degrees",
    ("places", "lat"): "geographic latitude of a place, not an amount",
    ("places", "lng"): "geographic longitude of a place, not an amount",
    ("places", "rating"): "0-5 star rating, not an amount",
    ("places", "distance_km"): "distance in km, not an amount",
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
    # M9 (ADR-0017). Prices live in their own bigint columns
    # (`price_min_vnd`, `price_max_vnd`); none of these four holds an amount.
    ("places", "kinds"): (
        "short words under the name (cuisine, amenity); strings, no amounts"
    ),
    ("places", "traits"): (
        "facts a tag states outright («Ngoài trời», «Wifi»); strings, no amounts"
    ),
    ("places", "group_fit"): (
        "min/max headcount and a relation word; the two numbers are people"
    ),
    ("places", "activities"): (
        "«nên làm gì ở đây» (M12): câu chữ suy từ tag của chính dòng ấy, "
        "không có số nào"
    ),
    ("places", "reviews"): (
        "author, 0-5 rating and body text of a seed review; no amounts"
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


def _model_tables() -> frozenset[str]:
    """Return the table names derived from SQLAlchemy model metadata."""

    return frozenset(Base.metadata.tables)


def _tables_missing_from_read(
    columns: list[tuple[str, str, str]],
) -> list[str]:
    return sorted(_model_tables() - {table for table, _, _ in columns})


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
    """Catch a schema read that is empty or broadly truncated.

    Both rules below are "no row satisfies X". An empty enumeration satisfies
    them for free, so these coarse floors still reject a badly truncated read.
    They do not answer whether one table is missing; the model-table coverage
    test answers that separate question.
    """

    columns = _columns(postgres_engine)
    assert len(columns) > 200, f"migrated schema looks truncated: {len(columns)}"
    money_named = [c for c in columns if _looks_like_money(c[1])]
    assert len(money_named) >= 20, f"money columns missing: {len(money_named)}"


def test_schema_read_covers_every_model_table(postgres_engine: Engine) -> None:
    """Every mapped table must contribute columns to the schema read."""

    missing = _tables_missing_from_read(_columns(postgres_engine))
    assert missing == [], (
        "model table(s) missing from the schema read: "
        + ", ".join(missing)
        + ". A table that falls out of this read makes every rule in this file "
        "pass for that table for free. A missing role grant is a measured cause; "
        "restore the grant before trusting this gate."
    )


def test_read_completeness_notices_every_single_lost_table(
    postgres_engine: Engine,
) -> None:
    """Positive control for the coverage rule: lose each table in turn.

    ``test_schema_read_covers_every_model_table`` is another "no rows matched"
    assertion, and on a healthy schema it passes whether or not the detector
    behind it works at all. So the detector is exercised here against a read
    that is known to have lost a table -- every table in turn, not a sampled
    one, because a single chosen table only says something about that table.

    The second half measures the floors this rule was added to replace, and it
    derives which tables they are blind to from the schema read rather than
    remembering a list of names. Two numbers, measured separately, both real:

    * **40 of 41** tables can leave the read without either floor noticing.
      ``expense_versions`` is the one exception -- it carries six money columns,
      enough to take the money count from 24 under the floor of 20.
    * **37 of 41** tables can leave the read without *any* of the gate's cases
      going red. The three-table difference is ``memories``, ``audit_events``
      and ``messages``, and they are not caught by a money rule at all: each is
      named in ``INEXACT_COLUMNS_REVIEWED`` or ``JSONB_COLUMNS_REVIEWED``, so
      losing them trips the allowlist-freshness rule by coincidence of having
      been written down. That is not coverage, and it does not extend to the
      money tables, which is where the 13-of-14 figure in the report came from.

    Only the first number is derived here, because only the floors are what
    this rule replaces.
    """

    columns = _columns(postgres_engine)
    model_tables = _model_tables()

    checked: list[str] = []
    invisible_to_old_floors: list[str] = []
    for victim in sorted(model_tables):
        truncated = [column for column in columns if column[0] != victim]

        assert _tables_missing_from_read(truncated) == [victim], (
            f"losing {victim} from the read was not reported as exactly that "
            "table missing"
        )
        checked.append(victim)

        money_named = [c for c in truncated if _looks_like_money(c[1])]
        if len(truncated) > 200 and len(money_named) >= 20:
            invisible_to_old_floors.append(victim)

    # A loop that never ran asserts nothing -- the exact shape of free-green
    # this file exists to reject. Pin the trip count against its source.
    assert checked == sorted(model_tables), (
        f"coverage control ran over {len(checked)} of {len(model_tables)} tables"
    )
    assert len(checked) > 0, "no model tables to check; the source list is empty"

    # If this ever drops to zero the floors would be doing the job on their own
    # and this rule would be dead weight. It was 40/41 when the rule was added.
    assert len(invisible_to_old_floors) > 0, (
        "the row-count floors now notice every single lost table on their own; "
        "re-examine whether this rule is still the thing catching them"
    )


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
        # Measured blind spots: these rows are documented holes, not controls.
        ("text", "gia_tri", False, False),
        ("character varying(32)", "so_tien", False, False),
        ("jsonb", "tong_cong", False, False),
        ("text", "total", False, False),
    ],
)
def test_detector_catches_a_column_known_to_be_wrong(
    postgres_engine: Engine,
    sql_type: str,
    column_name: str,
    caught_by_type_rule: bool,
    caught_by_name_rule: bool,
) -> None:
    """Plant measured canaries and verify each detector's expected result.

    Without this, every assertion above is "no rows matched", which a broken
    query satisfies just as well as a clean schema. The canary goes into the
    same migrated schema and is read back by the same ``_columns`` call, so it
    exercises the query the gate actually depends on -- not a hand-fed list.
    Rows expecting neither rule to fire record the known detection gap; they
    are not positive controls.
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
