"""Law 1 at the HTTP boundary: money crossing the API may not be inexact.

## Why this gate exists, in one sentence

``tests/postgres/test_money_columns_are_integer_postgres.py`` (#486) ends by
saying the database is *not* the last line of defence and that "the real last
line is the type check in ``allocate()`` and the pydantic boundary". That
sentence was an assertion nobody had ever measured. This file measures it.

## What this gate counts, and why that unit was chosen

The unit of counting is **the FastAPI application object that ``main`` actually
builds** -- ``app.routes``, walked into every pydantic model reachable from a
route's request body, response model, query parameters and path parameters.
It is not a hand-written list of model names or route names.

A hand-written list cannot notice a model nobody added it to, so it reports
"all clear" for exactly the change it was supposed to catch. Walking the built
app means a model added tomorrow is measured tomorrow, under whatever name its
author chose.

Query and path parameters are collected **separately** from the model walk, and
the reason is worth stating because it was found by mutation rather than by
reading. Mutant W2 removed query and path parameters from the walk and the gate
stayed green: measured on this tree there are 101 such parameters and *none* is
a pydantic model, so feeding them to a model walk discovers exactly nothing.
Passing them to the walk and calling that coverage would have been a claim with
no measurement under it. One of those 101 is money --
``candidate_per_person_vnd`` on ``GET /contexts/{context_id}/budget`` -- and it
is the single place where a client controls a money value that no model-shaped
rule in this file can see. It gets its own test below.

## The rules, and why none subsumes another

**Rule A -- behavioural, over money-named fields.** Every field whose *name*
says money must *refuse* a fractional value **and accept a plain integer**.
Both directions are checked by handing real values -- ``300.5``,
``Decimal("300.5")``, ``300`` -- to the field's real annotation through a real
``TypeAdapter``. It is deliberately not a check on the declared type.

The second direction is not decoration. Refusal alone is satisfied by a field
that refuses *everything*: a money field annotated ``str`` refuses ``300.5``
and would sail through a refuse-only rule, which is how money-as-text gets in.
Measured, not assumed: ``TypeAdapter(str).validate_python(300.5)`` raises, and
so does ``validate_python(300)`` -- so the accept direction is what catches it.

That distinction is the whole point of the rule. A frozen dataclass observed on
2026-08-31 declared two fields ``int`` and carried a ``Decimal`` in one of
them: ``ObligationAmounts(obligation_amount_vnd=40000,
confirmed_amount_vnd=Decimal("0"))``. A type *declaration* is not a check. So
this gate never reads ``Strict(strict=True)`` metadata, never reads an
annotation's repr, and never asks whether a field "is an int". It runs the
value and looks at what happens.

**Rule B -- structural, over inexact types, deny by default.** Every ``float``
or ``Decimal`` field reachable in the contract must appear in
``INEXACT_API_FIELDS_REVIEWED`` with the reason it is not money. This is the
mirror at the HTTP boundary of the schema-side rule in #486, and it is stated
over the field's *type* rather than its *name* for the same reason: a money
field that ignores the ``_vnd`` naming convention is invisible to any rule
phrased over names, and the reviewer writing the name list cannot know it is
missing.

Rule A is blind to a money field called ``gia_tri``; Rule B catches it the
moment it is inexact. Rule B is blind to money stored as ``str``, because
``str`` is not an inexact numeric type; Rule A's accept direction catches it.
A money field has to satisfy both.

**Rule C -- the allowlist is checked in both directions.** An entry in
``INEXACT_API_FIELDS_REVIEWED`` that no longer matches a discovered field fails
the gate as loudly as an undeclared inexact field does. This is what makes the
gate non-trivial: if the traversal below ever breaks and discovers nothing,
every one of the reviewed entries becomes stale and the gate goes red. There is
no state in which a broken walker prints green.

That property is deliberate and load-bearing. A sibling gate was failed in
review (#492) for resting on ``assert count > 0``, which stays green when a
walker silently loses most of its input. "Not empty" is not a measurement.

## What this gate does NOT prove -- read this before quoting it

* **It does not prove the fence is strict.** It proves fractional values are
  refused. Measured on the tree this landed on: 51 of 62 money fields also
  accept ``300.0``, ``"300"`` and ``True`` -- pydantic's lax mode coerces all
  three to an int, silently. ``True`` becoming ``1`` is not hypothetical
  strictness pedantry: it is the exact mirror of the database, which *refuses*
  a bool and silently *rounds* a float. The two layers refuse disjoint sets.
  Neither is a fence on its own, and this file measures only one of them.
* **It does not cover routes with no pydantic field at all.** Ten routes carry
  a response out without any response model; they are pinned in
  ``ROUTES_WITHOUT_RESPONSE_VALIDATION`` below. Six of them are the guest HTML
  pages, and those pages *do* render money. For that money there is no pydantic
  boundary whatsoever -- the value is formatted into a template. This gate
  states that hole, it does not close it.
* **It does not prove any value is correct.** A field that refuses ``300.5``
  will happily accept ``300`` when the right answer was ``400``. Law 2 is the
  golden vectors' job, not this file's.
* **It says nothing about money inside ``jsonb`` or inside a free-form dict.**
  A field annotated ``dict`` is opaque to pydantic's numeric machinery and so
  is opaque here.
"""

from __future__ import annotations

import typing
from decimal import Decimal

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, TypeAdapter

from app.api.main import app

# Values that Law 1 forbids money from ever taking. A money field must refuse
# both, whatever its declared type says.
FRACTIONAL_PROBES: tuple[object, ...] = (300.5, Decimal("300.5"))

# The other direction. A rule that only demands refusal is satisfied by a field
# that refuses everything -- ``str`` being the case that matters, since money
# kept as text passes every numeric rule in this file.
INTEGER_PROBE = 300

# A query parameter arrives off the wire as text, so ``300.5`` reaches it as
# ``"300.5"``. Probing a scalar parameter with the float alone would test a
# shape no HTTP client can actually send.
WIRE_FRACTIONAL_PROBES: tuple[object, ...] = (*FRACTIONAL_PROBES, "300.5")

# Deny by default: an inexact field NOT listed here fails the gate. Each entry
# states why it is not money. Coordinates, ratings, distances and normalised
# scores -- nothing that is ever paid to anybody.
INEXACT_API_FIELDS_REVIEWED: dict[tuple[str, str], str] = {
    ("MemoryResponse", "lat"): "geographic latitude, not an amount",
    ("MemoryResponse", "lng"): "geographic longitude, not an amount",
    ("Place", "lat"): "geographic latitude, not an amount",
    ("Place", "lng"): "geographic longitude, not an amount",
    ("Place", "rating"): "0-5 star rating, not an amount",
    ("Place", "distance_km"): "distance in km, not an amount",
    ("PlaceDetail", "lat"): "geographic latitude, not an amount",
    ("PlaceDetail", "lng"): "geographic longitude, not an amount",
    ("PlaceDetail", "rating"): "0-5 star rating, not an amount",
    ("PlaceDetail", "distance_km"): "distance in km, not an amount",
    ("DestinationSummary", "lat"): "geographic latitude, not an amount",
    ("DestinationSummary", "lng"): "geographic longitude, not an amount",
    ("DestinationSummary", "distance_km"): "distance in km, not an amount",
    ("Review", "rating"): "0-5 star rating, not an amount",
    ("Understood", "max_distance_km"): "distance in km, not an amount",
    ("SuggestionPlace", "rating"): "0-5 star rating, not an amount",
    ("SuggestionPlace", "distance_km"): "distance in km, not an amount",
    ("AreaSummary", "lat"): "geographic latitude, not an amount",
    ("AreaSummary", "lng"): "geographic longitude, not an amount",
    ("VisitedPlace", "lat"): "geographic latitude, not an amount",
    ("VisitedPlace", "lng"): "geographic longitude, not an amount",
    ("MapPlace", "lat"): "geographic latitude, not an amount",
    ("MapPlace", "lng"): "geographic longitude, not an amount",
    ("MapPlace", "rating"): "0-5 star rating, not an amount",
    ("HeatmapArea", "lat"): "geographic latitude, not an amount",
    ("HeatmapArea", "lng"): "geographic longitude, not an amount",
    ("MeetingCandidate", "lat"): "geographic latitude, not an amount",
    ("MeetingCandidate", "lng"): "geographic longitude, not an amount",
    ("MeetingLeg", "lat"): "geographic latitude, not an amount",
    ("MeetingLeg", "lng"): "geographic longitude, not an amount",
    ("MeetingLeg", "km"): "travel distance in km, not an amount",
    ("MeetingFairness", "worst_km"): "travel distance in km, not an amount",
    ("MeetingFairness", "total_km"): "travel distance in km, not an amount",
    ("MeetingFairness", "spread_km"): "travel distance in km, not an amount",
    ("PreferenceTaste", "score"): "normalised 0-1 taste score, not an amount",
    ("FaceBoxResponse", "x"): "normalised face-box coordinate, not an amount",
    ("FaceBoxResponse", "y"): "normalised face-box coordinate, not an amount",
    ("FaceBoxResponse", "width"): "normalised face-box size, not an amount",
    ("FaceBoxResponse", "height"): "normalised face-box size, not an amount",
}

# Routes FastAPI builds no response field for, so nothing validates what leaves
# them. Pinned with a reason each, so a new unvalidated route has to pass
# through this file. The guest pages are the ones that matter: they render
# money into HTML with no pydantic boundary at all.
ROUTES_WITHOUT_RESPONSE_VALIDATION: dict[tuple[str, str], str] = {
    ("DELETE", "/contexts/{context_id}/members/{person_id}"): "204, no body",
    ("DELETE", "/sessions/current"): "204, no body; signing out returns nothing",
    ("DELETE", "/contexts/{context_id}/memories/{memory_id}/reactions"): "204, no body",
    ("DELETE", "/people/me/saved-places/{place_id}"): "204, no body",
    (
        "GET",
        "/contexts/{context_id}/photos/{photo_id}",
    ): "raw image bytes, no body model",
    ("GET", "/people/{person_id}/avatar"): "raw image bytes, no body model",
    (
        "GET",
        "/places/{place_id}/photos/{photo_id}",
    ): "raw image bytes, no body model",
    ("GET", "/g/{token}"): "guest HTML page; RENDERS MONEY with no pydantic boundary",
    ("GET", "/g/{token}/khong-phai-toi"): "guest HTML page",
    ("POST", "/g/{token}/khong-phai-toi"): "guest HTML redirect",
    (
        "GET",
        "/g/{token}/doi-so-tien",
    ): "guest HTML page; RENDERS MONEY with no pydantic boundary",
    ("POST", "/g/{token}/doi-so-tien"): "guest HTML redirect",
    ("POST", "/g/{token}/xin-cach-tinh"): "guest HTML redirect",
}

# Floor for Rule A, bound to the count measured when this gate landed. A floor
# of "> 0" would stay green after a walker lost 95% of its input; this one does
# not. Lowering the number is a visible act in a diff, which is the point.
MONEY_FIELDS_AT_PIN = 62


def _looks_like_money(field_name: str) -> bool:
    """Name-side heuristic. Used only to decide what Rule A must probe."""

    return field_name.endswith("_vnd") or "amount" in field_name


def _annotation_of(field: object) -> object | None:
    """Pull the annotation off a FastAPI ModelField without assuming a version."""

    info = getattr(field, "field_info", None)
    return getattr(info, "annotation", None) if info is not None else None


def _walk_contract() -> tuple[
    dict[tuple[str, str], object],
    dict[tuple[str, str], object],
    set[str],
    int,
]:
    """Walk the built app into every reachable pydantic field.

    Returns the discovered model fields keyed by (model name, field name), the
    scalar query/path parameters keyed by (route path, parameter name), the set
    of model names visited, and the number of APIRoutes walked. Nothing here is
    driven by a hand-written list: the only input is ``app.routes``.
    """

    discovered: dict[tuple[str, str], object] = {}
    scalars: dict[tuple[str, str], object] = {}
    visited: set[str] = set()
    seen_models: set[type] = set()
    routes_walked = 0

    def walk(annotation: object) -> None:
        if annotation is None:
            return
        for arg in typing.get_args(annotation) or ():
            walk(arg)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            visit(annotation)

    def visit(model: type[BaseModel]) -> None:
        if model in seen_models:
            return
        seen_models.add(model)
        visited.add(model.__name__)
        for name, field in model.model_fields.items():
            discovered[(model.__name__, name)] = field.annotation
            walk(field.annotation)

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        routes_walked += 1
        for field in (
            getattr(route, "response_field", None),
            getattr(route, "body_field", None),
        ):
            if field is not None:
                walk(_annotation_of(field))
        dependant = route.dependant
        for param in (
            list(dependant.body_params or ())
            + list(dependant.query_params or ())
            + list(dependant.path_params or ())
        ):
            annotation = _annotation_of(param)
            walk(annotation)
            # A query or path parameter is usually a bare scalar, not a model,
            # so ``walk`` above discovers nothing for it. Money arriving that
            # way would be invisible to every model-shaped rule in this file.
            name = getattr(param, "name", None)
            if name is not None and annotation is not None:
                scalars[(route.path, name)] = annotation

    return discovered, scalars, visited, routes_walked


def _accepts(annotation: object, value: object) -> bool:
    """Run a real value through the real annotation. No metadata is read."""

    try:
        TypeAdapter(annotation).validate_python(value)
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def contract() -> tuple[
    dict[tuple[str, str], object],
    dict[tuple[str, str], object],
    set[str],
    int,
]:
    return _walk_contract()


def test_walker_reached_every_api_route(contract) -> None:
    """The walker's input is the route table, so bind it to the route table.

    If this drifts, every other assertion in the file is measuring a subset
    without saying so.
    """

    _, _, _, routes_walked = contract
    live_routes = sum(1 for route in app.routes if isinstance(route, APIRoute))
    assert routes_walked == live_routes, (
        f"walked {routes_walked} routes but the app has {live_routes}"
    )
    assert live_routes >= 80, f"only {live_routes} APIRoutes found; app did not build"


def test_every_money_field_refuses_a_fractional_value(contract) -> None:
    """Rule A. Behavioural: the value is run, the declaration is ignored."""

    discovered, _, _, _ = contract
    money = {
        key: annotation
        for key, annotation in discovered.items()
        if _looks_like_money(key[1])
    }
    assert len(money) >= MONEY_FIELDS_AT_PIN, (
        f"only {len(money)} money-named fields discovered, expected at least "
        f"{MONEY_FIELDS_AT_PIN}; the walker lost input rather than the app "
        f"losing fields"
    )

    leaked = [
        f"{model}.{field} accepted {value!r}"
        for (model, field), annotation in sorted(money.items())
        for value in FRACTIONAL_PROBES
        if _accepts(annotation, value)
    ]
    assert leaked == [], (
        "money fields at the HTTP boundary accepted a fractional value, "
        "violating Law 1:\n  " + "\n  ".join(leaked)
    )

    not_numeric = [
        f"{model}.{field} refused {INTEGER_PROBE!r}"
        for (model, field), annotation in sorted(money.items())
        if not _accepts(annotation, INTEGER_PROBE)
    ]
    assert not_numeric == [], (
        "money fields refused a plain integer, so they are not holding money "
        "as a number at all -- text and opaque types refuse every probe above "
        "and would otherwise pass this gate:\n  " + "\n  ".join(not_numeric)
    )


def test_every_money_query_or_path_parameter_refuses_a_fractional_value(
    contract,
) -> None:
    """Rule A, applied to scalars that never live inside a model.

    A query parameter is a bare annotation hanging off the route, so the model
    walk never reaches it. Measured on the tree this landed on there are 101
    query and path parameters, none of them a pydantic model, and exactly one
    of them is money: ``candidate_per_person_vnd`` on
    ``GET /contexts/{context_id}/budget``. Without this test that parameter is
    the one place money enters the API with nothing in this file watching it.
    """

    _, scalars, _, _ = contract
    money = {
        key: annotation
        for key, annotation in scalars.items()
        if _looks_like_money(key[1])
    }
    assert money, (
        "no money-named query or path parameter found at all; the parameter "
        "collection above broke, because this tree has one"
    )

    leaked = [
        f"{path}?{name} accepted {value!r}"
        for (path, name), annotation in sorted(money.items())
        for value in WIRE_FRACTIONAL_PROBES
        if _accepts(annotation, value)
    ]
    assert leaked == [], (
        "a money query/path parameter accepted a fractional value, violating "
        "Law 1 at the point where a client controls it directly:\n  "
        + "\n  ".join(leaked)
    )


def test_every_inexact_field_is_reviewed(contract) -> None:
    """Rule B. Deny by default, stated over the type, not over the name."""

    discovered, _, _, _ = contract
    inexact = {
        key
        for key, annotation in discovered.items()
        if any(
            arg in (float, Decimal)
            for arg in [annotation, *typing.get_args(annotation)]
        )
    }

    undeclared = sorted(inexact - set(INEXACT_API_FIELDS_REVIEWED))
    assert undeclared == [], (
        "inexact-numeric fields reached the API contract without review; if "
        "any of these is money, Law 1 is already broken:\n  "
        + "\n  ".join(f"{model}.{field}" for model, field in undeclared)
    )


def test_reviewed_inexact_entries_all_still_exist(contract) -> None:
    """Rule C. The direction that makes a broken walker impossible to hide.

    A stale entry is as loud as an undeclared field. If the walker above ever
    returns nothing, all 37 reviewed entries go stale here and this fails --
    so there is no way for this file to pass by measuring nothing.
    """

    discovered, _, _, _ = contract
    stale = sorted(set(INEXACT_API_FIELDS_REVIEWED) - set(discovered))
    assert stale == [], (
        "reviewed inexact fields no longer exist in the contract; either the "
        "walker broke or the allowlist is out of date:\n  "
        + "\n  ".join(f"{model}.{field}" for model, field in stale)
    )


def test_routes_without_response_validation_are_pinned() -> None:
    """The hole this gate does not close, written down instead of omitted."""

    unvalidated = {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if getattr(route, "secure_cloned_response_field", None) is None
        and getattr(route, "response_field", None) is None
    }

    assert unvalidated == set(ROUTES_WITHOUT_RESPONSE_VALIDATION), (
        "the set of routes with no response validation changed; a new one is a "
        "new place money can leave the API with no pydantic boundary.\n"
        f"  appeared: {sorted(unvalidated - set(ROUTES_WITHOUT_RESPONSE_VALIDATION))}\n"
        f"  gone:     {sorted(set(ROUTES_WITHOUT_RESPONSE_VALIDATION) - unvalidated)}"
    )
