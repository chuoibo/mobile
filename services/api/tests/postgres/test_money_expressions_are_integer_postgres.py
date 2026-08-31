"""Law 1 on the expression side: no SQL expression may hand money back inexactly.

## The question this file answers

`test_money_columns_are_integer_postgres.py` gates *storage*, and says so in its
own docstring:

> There is no count over column types that answers "every SQL expression
> returning money is an int"; that question is answered at runtime, on the
> values the repository actually hands back.

That was the open hole. `bigint` columns say nothing about what a *query*
returns, because PostgreSQL widens the result in places the column types cannot
predict. This file closes it, and the thing worth reviewing is **the unit of
counting**, not the assertions.

## Why not count function names

The obvious gate is a scan for `func.sum(` over the repository modules. It is
worthless, because the unit of counting is a name a human thought of, and the
widening rule belongs to PostgreSQL. Measured against this server:

    SUM(bigint)              -> numeric   (Decimal)
    AVG(bigint)              -> numeric   (Decimal)
    ROUND(bigint)            -> float8    (float)      <-- not even numeric
    bigint * 1.0             -> numeric   (Decimal)
    CAST(SUM(x) AS bigint)   -> int8      (int)

A name list has to contain `sum`, `avg`, `round`, every other numeric function,
and it still cannot see `text("SUM(...)")` written by hand, a numeric literal
mixed into an expression, or a `/` division. Worse, it has to know that `round`
comes back as *float* rather than numeric -- a fact about PostgreSQL, not about
our code. A list that must anticipate the database cannot be complete, and a
list that is not complete reports "all clear" for exactly the case it missed.

## What is counted instead

**The result type PostgreSQL itself reports for every statement that runs.**

psycopg exposes it as the type OID in `cursor.description`, and a SQLAlchemy
`after_cursor_execute` listener reads it for every statement without knowing
anything about how that statement was written. The rule is stated over the
type, so it is blind to spelling:

    no result column may come back as an inexact numeric type

That catches `sum`, `avg`, `round`, hand-written `text()` SQL, integer
division, a stray numeric literal and a `Numeric` column, by the same mechanism
and without naming any of them. The inexact OIDs are not hardcoded either --
they are read out of the live server's `pg_type`, so the set is the server's
answer rather than ours.

This is the same inversion `INEXACT_COLUMNS_REVIEWED` made on the storage side:
deny by default on the *type*, and let anything legitimately inexact be an
explicit, reviewable entry. The reviewed set here is empty.

## What this gate does NOT prove -- read this before quoting it

* **It only sees statements that actually ran.** The unit of counting is
  "result types of executed statements", so a query no test drives is invisible
  to it. `MONEY_QUERY_SURFACE` below is a hand-written list of entry points and
  carries exactly the weakness every hand-written list carries: it cannot know
  what it is missing. That gap is real. What a hand-written list can still be
  held to is that every name on it means something, and
  `test_every_surface_name_is_actually_driven` holds it to that by resolving
  each name to the callable it refers to and requiring that the driver below
  really reached it. So the list can be short, but it cannot be
  *decorative* -- a name whose call is deleted goes red instead of quietly
  shrinking the surface this gate measures. `test_every_aggregating_method_is_driven`
  covers the opposite drift, a new aggregate nobody added to the list; it is a
  reminder built on names and inherits their limits, and neither reminder is
  part of the type rule.
* **A computed column is a reachability witness, not an aggregate identity.**
  Every query-executing entry point must now expose at least one result column
  whose libpq provenance says it was computed rather than read from a table.
  That catches a call such as `group_recap` reading `Outing` and returning
  before its aggregate. It proves only that *some* computed expression ran
  during the call, however; it does not prove that the entry point's intended
  money aggregate was the expression that ran.
* **It is about the wire, not about JSON.** A number nested inside a `jsonb`
  document has no PostgreSQL numeric type, so it is outside every rule here,
  exactly as it is outside the storage gate.
* **It is not a claim that the values are correct.** An expression can return
  `int8` and still return the wrong amount. Sum correctness is what the 41
  golden vectors and the ledger tests are for.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Outing, Person
from app.db.repository import obligation_amounts_statement

from .conftest import seed_context

# PostgreSQL types that cannot represent "đồng" exactly, or that carry a
# fractional part Law 1 forbids money from ever having. Spelled as type names
# and resolved against the live server below, so the OID numbers are never
# written down here.
INEXACT_TYPE_NAMES = frozenset({"numeric", "float4", "float8", "money"})

# Result columns that are legitimately inexact and are not money. Deny by
# default: an entry here is a visible act in a diff, and each one must carry
# the reason it is not money. Currently empty -- no money query returns a
# geographic coordinate or a ratio.
INEXACT_RESULTS_REVIEWED: dict[str, str] = {}

# Repository modules scanned by the coverage reminder below.
REPOSITORY_MODULES = (
    "app/api/repository.py",
    "app/db/repository.py",
)

# SQL functions that widen an integer argument on this server. Used ONLY by the
# coverage reminder, never by the type rule -- see the docstring.
WIDENING_FUNCTION_NAMES = frozenset({"sum", "avg", "round"})


@dataclass(frozen=True, slots=True)
class InexactResult:
    """One result column PostgreSQL reported with an inexact numeric type."""

    column: str
    type_name: str
    statement: str


class ResultTypeRecorder:
    """Read result types and table provenance without parsing the statement.

    The point of the indirection is that nothing here inspects *how* a query
    was written. `cursor.description` supplies PostgreSQL's type answer, while
    libpq's `ftable()` identifies whether each result column came from a real
    table. A hand-written `text("SUM(...)")` is therefore measured by the same
    path as a `func.sum()` built through the ORM.
    """

    def __init__(self, inexact_oids: dict[int, str]) -> None:
        self._inexact_oids = inexact_oids
        self.statements_seen = 0
        self.result_columns_seen = 0
        self.computed_columns_seen = 0
        self.findings: list[InexactResult] = []

    def observe(self, cursor, statement: str) -> None:
        self.statements_seen += 1
        description = cursor.description
        if description is None:
            return
        try:
            pgresult = cursor.pgresult
        except AttributeError as error:
            raise AssertionError(
                "ResultTypeRecorder requires psycopg3 cursor.pgresult provenance "
                "to distinguish computed columns from table columns"
            ) from error
        if pgresult is None:
            raise AssertionError(
                "ResultTypeRecorder received result columns but psycopg3 "
                "cursor.pgresult is unavailable; computed-column coverage "
                "cannot be measured"
            )
        for index, column in enumerate(description):
            self.result_columns_seen += 1
            # libpq reports relation OID zero for a computed result column.
            if not pgresult.ftable(index):
                self.computed_columns_seen += 1
            type_name = self._inexact_oids.get(column.type_code)
            if type_name is None:
                continue
            if column.name in INEXACT_RESULTS_REVIEWED:
                continue
            self.findings.append(
                InexactResult(
                    column=column.name,
                    type_name=type_name,
                    statement=" ".join(statement.split())[:200],
                )
            )


def _inexact_oids(engine: Engine) -> dict[int, str]:
    """Ask the server which OIDs are inexact. Never hardcode the numbers."""

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT oid, typname FROM pg_type WHERE typname = ANY(:names)"),
            {"names": sorted(INEXACT_TYPE_NAMES)},
        ).all()
    resolved = {int(oid): str(name) for oid, name in rows}
    missing = INEXACT_TYPE_NAMES - set(resolved.values())
    assert not missing, f"server did not resolve inexact type names: {sorted(missing)}"
    return resolved


@contextmanager
def recording(engine: Engine) -> Iterator[ResultTypeRecorder]:
    recorder = ResultTypeRecorder(_inexact_oids(engine))

    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        recorder.observe(cursor, statement)

    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    try:
        yield recorder
    finally:
        event.remove(engine, "after_cursor_execute", _after_cursor_execute)


def _drive_money_query_surface(session: Session, *, seed_trip: bool = True) -> None:
    """Execute every money-returning entry point we know of.

    A result *type* is a property of the statement rather than of the rows, so
    PostgreSQL reports it just as precisely over zero rows. That tempts one to
    drive everything against an empty context and skip fixtures entirely, and
    the first draft of this file did exactly that -- and silently measured
    nothing for `group_recap`, which returns early when the group has no trip
    and therefore never reaches its money query at all.

    So the seeding below is not about having realistic amounts. It exists to
    get *past the early returns*. The default stays enabled for the gate;
    `seed_trip=False` exists only so a positive control can prove that the
    computed-column reachability rule rejects the seedless path.
    """

    context_id = seed_context(session)
    person_id = uuid.uuid4()
    repository = SqlAlchemyApiRepository(session)

    if seed_trip:
        # Enough of a trip to get past `group_recap`'s early return.
        organiser = Person(display_name="Người tổ chức test")
        session.add(organiser)
        session.flush()
        session.add(
            Outing(
                context_id=context_id,
                created_by_id=organiser.id,
                title="Chuyến đi test",
                starts_on=date(2026, 8, 1),
                ends_on=date(2026, 8, 2),
                headcount=2,
                budget_per_person_vnd=0,
            )
        )
        session.flush()

    repository.group_recap(context_id, today=date(2026, 8, 31))
    repository.load_confirmed_receipts(context_id)
    repository.person_finance_summary(person_id, movement_limit=10)
    # The statement builder rather than `get_obligation_amounts`, which raises
    # when the row is absent. What is measured is the result type, and that is
    # reported for zero rows just as precisely.
    session.execute(obligation_amounts_statement(uuid.uuid4())).all()


# Hand-written, and labelled as such in the docstring: these are the entry
# points driven above. Kept as data so the count can be asserted.
MONEY_QUERY_SURFACE = (
    "group_recap",
    "load_confirmed_receipts",
    "person_finance_summary",
    "obligation_amounts_statement",
)


def test_recorder_is_actually_watching(postgres_session: Session) -> None:
    """Non-triviality. Every other assert here is "nothing matched", and a dead
    recorder satisfies that shape perfectly."""

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        _drive_money_query_surface(postgres_session)

    assert recorder.statements_seen > 0, "recorder saw no statements at all"
    assert recorder.result_columns_seen > 0, "recorder saw no result columns at all"


# --------------------------------------------------------------------------
# Binding the list to the driver. `MONEY_QUERY_SURFACE` and
# `_drive_money_query_surface` are two artifacts that describe the same thing,
# and nothing above stops them disagreeing: deleting one call from the driver
# while leaving its name on the list shrinks what the gate measures and every
# "no findings" assert stays green, because a query that never ran cannot
# return an inexact type. The floor `statements_seen > 0` does not see it
# either -- it answers "is the recorder dead", and losing one of four entry
# points is not death.
#
# So each name is resolved to the callable it names and watched. That is a
# lookup rather than a second list: it cannot drift from the first one, and a
# name that resolves to nothing is itself a failure.
# --------------------------------------------------------------------------


@dataclass(slots=True)
class SurfaceObservation:
    """What one entry point on the surface actually did while the driver ran."""

    calls: int = 0
    result_columns: int = 0
    computed_columns: int = 0
    executes_its_own_query: bool = True


def _surface_target(name: str) -> tuple[object, bool]:
    """Resolve a surface name to the object it must be patched on.

    Two kinds live on the list and they are told apart by where the name
    resolves, not by another hand-written list. A repository *method* runs its
    own query, so reaching it is measurable. An imported statement *builder*
    only assembles SQL -- executing it is the driver's job -- so no result
    column can be attributed to the call itself.
    """

    if hasattr(SqlAlchemyApiRepository, name):
        return SqlAlchemyApiRepository, True
    module = sys.modules[__name__]
    if hasattr(module, name):
        return module, False
    raise AssertionError(
        f"{name!r} is on MONEY_QUERY_SURFACE but resolves to nothing: it is "
        "neither a method of SqlAlchemyApiRepository nor imported into this "
        "module, so no test can be driving it."
    )


@contextmanager
def watching_surface(
    recorder: ResultTypeRecorder,
) -> Iterator[dict[str, SurfaceObservation]]:
    """Count what each named entry point does, by wrapping the name itself."""

    observed: dict[str, SurfaceObservation] = {}
    restore: list[tuple[object, str, object]] = []

    def wrap(owner: object, name: str, original):
        def wrapper(*args, **kwargs):
            result_columns_before = recorder.result_columns_seen
            computed_columns_before = recorder.computed_columns_seen
            try:
                return original(*args, **kwargs)
            finally:
                entry = observed[name]
                entry.calls += 1
                entry.result_columns += (
                    recorder.result_columns_seen - result_columns_before
                )
                entry.computed_columns += (
                    recorder.computed_columns_seen - computed_columns_before
                )

        return wrapper

    for name in MONEY_QUERY_SURFACE:
        owner, executes = _surface_target(name)
        observed[name] = SurfaceObservation(executes_its_own_query=executes)
        original = getattr(owner, name)
        restore.append((owner, name, original))
        setattr(owner, name, wrap(owner, name, original))
    try:
        yield observed
    finally:
        for owner, name, original in restore:
            setattr(owner, name, original)


def test_every_surface_name_is_actually_driven(postgres_session: Session) -> None:
    """A name on the surface list must correspond to a call that really happens.

    This is the assert that makes the list honest. Without it the list is a
    claim about coverage that nothing checks, and the cheapest way to lose
    coverage -- delete a line from the driver, leave the name -- is also the
    quietest, because it makes the gate measure less while printing the same
    green.
    """

    engine = postgres_session.get_bind()
    with recording(engine) as recorder, watching_surface(recorder) as observed:
        _drive_money_query_surface(postgres_session)

    assert set(observed) == set(MONEY_QUERY_SURFACE), (
        "the watcher did not cover the whole surface list"
    )

    never_called = sorted(name for name, seen in observed.items() if seen.calls == 0)
    assert never_called == [], (
        f"these names are on MONEY_QUERY_SURFACE but _drive_money_query_surface "
        f"never calls them, so the gate is not watching them at all: "
        f"{never_called}. Either drive them or take them off the list -- a name "
        "left on the list is read as coverage that does not exist."
    )

    # Being called is not the same as running anything: a method stubbed to
    # `return ()` satisfies the count above while the gate observes nothing of
    # what it returns. This catches that shape; the computed-provenance rule
    # below catches an early return that happens after a pure table read.
    ran_no_sql = sorted(
        name
        for name, seen in observed.items()
        if seen.executes_its_own_query and seen.result_columns == 0
    )
    assert ran_no_sql == [], (
        f"these entry points were called but executed no result-returning "
        f"statement at all, so the gate saw nothing of what they return: "
        f"{ran_no_sql}. A method stubbed out to return early looks exactly "
        "like this."
    )


def _surface_methods_without_computed_expression(
    observed: dict[str, SurfaceObservation],
) -> list[str]:
    """Return query-executing methods that exposed only table columns.

    Statement builders are exempt because they only assemble SQL. The driver,
    outside the builder's wrapped call, is where that statement is executed
    and where its result-column provenance can be observed.
    """

    return sorted(
        name
        for name, seen in observed.items()
        if seen.executes_its_own_query and seen.computed_columns < 1
    )


def test_every_surface_method_reaches_a_computed_expression(
    postgres_session: Session,
) -> None:
    """Each method must get beyond pure table reads to a computed expression."""

    engine = postgres_session.get_bind()
    with recording(engine) as recorder, watching_surface(recorder) as observed:
        _drive_money_query_surface(postgres_session)

    pure_table_only = _surface_methods_without_computed_expression(observed)
    assert pure_table_only == [], (
        "these entry points were called and executed result-returning SQL, but "
        "read only columns from real tables and exposed no computed result "
        f"column: {pure_table_only}. They returned before reaching their "
        "aggregate (usually because a required fixture was removed), so this "
        "gate measured nothing about their money expressions."
    )


def test_seedless_group_recap_fails_computed_expression_reachability(
    postgres_session: Session,
) -> None:
    """Positive control: dropping the trip seed must make the new rule red."""

    engine = postgres_session.get_bind()
    with recording(engine) as recorder, watching_surface(recorder) as observed:
        _drive_money_query_surface(postgres_session, seed_trip=False)

    recap = observed["group_recap"]
    assert recap.calls == 1 and recap.result_columns > 0, (
        "seedless group_recap no longer models a called method that runs SQL "
        "before returning early"
    )
    assert _surface_methods_without_computed_expression(observed) == ["group_recap"], (
        "the computed-expression reachability rule did not reject seedless "
        "group_recap specifically; the positive control no longer proves the "
        "fixture-removal regression is caught"
    )


def test_no_money_expression_returns_an_inexact_type(
    postgres_session: Session,
) -> None:
    """The gate. Stated over the type PostgreSQL reports, not over any name."""

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        _drive_money_query_surface(postgres_session)

    assert recorder.findings == [], (
        f"{len(recorder.findings)} result column(s) came back inexact out of "
        f"{recorder.result_columns_seen} observed across "
        f"{recorder.statements_seen} statements:\n"
        + "\n".join(
            f"  {finding.column!r} is {finding.type_name} in: {finding.statement}"
            for finding in recorder.findings
        )
    )


def test_money_values_reaching_python_are_int(postgres_session: Session) -> None:
    """The same rule one layer out: what the caller receives, not what SQL said.

    A `Decimal` here is the symptom people actually see -- it reaches JSON as
    `520000.0` -- so this asserts on the delivered object rather than on the
    wire type.
    """

    context_id = seed_context(postgres_session)
    repository = SqlAlchemyApiRepository(postgres_session)
    summary = repository.person_finance_summary(uuid.uuid4(), movement_limit=10)

    money_fields = {
        field.name: getattr(summary, field.name)
        for field in dataclasses.fields(summary)
        if field.name.endswith("_vnd")
    }
    assert money_fields, "no *_vnd fields found on the summary; check the dataclass"
    wrong = {
        name: (type(value).__name__, value)
        for name, value in money_fields.items()
        # `bool` is an `int` subclass and would pass a naive isinstance check.
        if value is not None and (type(value) is not int)
    }
    assert wrong == {}, f"money fields that are not int: {wrong}"

    recap = repository.group_recap(context_id, today=date(2026, 8, 31))
    for record in recap:
        assert type(record.split_total_vnd) is int, (
            f"group_recap split_total_vnd is {type(record.split_total_vnd).__name__}"
        )


# --------------------------------------------------------------------------
# Positive controls. Every assertion above is "no findings", a shape a broken
# recorder satisfies for free. These plant expressions KNOWN to be inexact and
# require the recorder to go red on them.
# --------------------------------------------------------------------------

KNOWN_INEXACT_EXPRESSIONS = (
    pytest.param(
        "SELECT SUM(x) AS s FROM (VALUES (1::bigint)) v(x)",
        "numeric",
        id="sum-over-bigint",
    ),
    pytest.param(
        "SELECT AVG(x) AS s FROM (VALUES (1::bigint)) v(x)",
        "numeric",
        id="avg-over-bigint",
    ),
    pytest.param(
        "SELECT ROUND(x) AS s FROM (VALUES (1::bigint)) v(x)",
        "float8",
        id="round-returns-float-not-numeric",
    ),
    pytest.param(
        "SELECT 1::bigint * 1.0 AS s", "numeric", id="numeric-literal-mixed-in"
    ),
    pytest.param(
        "SELECT SUM(x) AS s FROM (VALUES (1::bigint)) v(x) WHERE false",
        "numeric",
        id="inexact-even-with-zero-rows",
    ),
)


@pytest.mark.parametrize("statement,expected_type", KNOWN_INEXACT_EXPRESSIONS)
def test_recorder_catches_expressions_known_to_be_inexact(
    postgres_session: Session, statement: str, expected_type: str
) -> None:
    """Each of these is a place we KNOW is inexact; the recorder must see it.

    `round` is the one that matters most: it comes back as float8, so a gate
    that assumed "widening means numeric" would miss it.
    """

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        postgres_session.execute(text(statement)).all()

    assert len(recorder.findings) == 1, (
        f"recorder did not flag a known-inexact expression: {statement}"
    )
    assert recorder.findings[0].type_name == expected_type


def test_recorder_passes_an_expression_known_to_be_exact(
    postgres_session: Session,
) -> None:
    """The other half of the control: the recorder is not flagging everything.

    A recorder that reported every column would make the gate above red for
    free and equally worthless.
    """

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        postgres_session.execute(
            text("SELECT CAST(SUM(x) AS bigint) AS s FROM (VALUES (1::bigint)) v(x)")
        ).all()

    assert recorder.findings == [], (
        f"cast-to-bigint was wrongly flagged: {recorder.findings}"
    )
    assert recorder.result_columns_seen >= 1


def test_reviewed_exemptions_are_not_a_blanket_pass(
    postgres_session: Session,
) -> None:
    """An entry in the reviewed set must exempt one column name, not the rule.

    Guards the failure mode where a future exemption is written in a way that
    turns the whole gate off.
    """

    engine = postgres_session.get_bind()
    with recording(engine) as recorder:
        postgres_session.execute(
            text("SELECT SUM(x) AS lat FROM (VALUES (1::bigint)) v(x)")
        ).all()
    assert len(recorder.findings) == 1, (
        "a column named like a reviewed storage exemption must still be caught "
        "here; the two reviewed sets are not the same set"
    )


# --------------------------------------------------------------------------
# Coverage reminder. Built on names, so it is NOT part of the type rule -- it
# exists so that adding an aggregate to a method nobody drives goes red instead
# of silently shrinking the surface this gate measures.
# --------------------------------------------------------------------------


def _methods_containing_a_widening_call(source_root: pathlib.Path) -> set[str]:
    found: set[str] = set()
    for relative in REPOSITORY_MODULES:
        tree = ast.parse((source_root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                func_node = inner.func
                if (
                    isinstance(func_node, ast.Attribute)
                    and func_node.attr in WIDENING_FUNCTION_NAMES
                    and isinstance(func_node.value, ast.Name)
                    and func_node.value.id == "func"
                ):
                    found.add(node.name)
    return found


def test_every_aggregating_method_is_driven() -> None:
    """Needs no database: a pure source-level drift check on the surface list."""

    source_root = pathlib.Path(__file__).resolve().parents[2]
    aggregating = _methods_containing_a_widening_call(source_root)

    assert aggregating, "scanner found no aggregating methods; it is broken"

    undriven = aggregating - set(MONEY_QUERY_SURFACE)
    assert undriven == set(), (
        "these methods build a widening SQL aggregate but no test above drives "
        f"them, so the gate cannot see what they return: {sorted(undriven)}. "
        "Either drive them in _drive_money_query_surface or state why they are "
        "not money."
    )
