"""Money law 1 at the wire: no money field anywhere accepts a non-integer.

`schemas.py` says it already: a JSON string such as ``"82000"`` *or a float such
as ``82000.0``* is a malformed caller precondition, and neither may reach the
allocator. Two shapes are named there. Only the string was ever tested, by
``test_malformed_wire_money_never_reaches_domain_or_storage``, and that one test
lives on one field of one route.

That gap is measurable rather than theoretical. Teaching ``MoneyVnd`` to accept
an integral float -- the change someone makes the first time a JavaScript client
posts ``82000.0``, because JS has no integer type -- leaves the whole suite
green at 1622 passed. The string test stays green because strings are still
refused, so the one gate that exists says nothing about the shape beside it.

Three shapes get in when a money field is declared lax, and each is a different
kind of wrong:

    "82000"     a string, the shape already covered
    82000.0     a float, which is money law 1 broken by definition
    true        a bool, which pydantic coerces to 1 -- a bill of one dong

The bool is the one worth staring at. ``bool`` subclasses ``int`` in Python, so
every ``isinstance(x, int)`` written to defend money says yes to ``True``. The
allocator has no type check of its own: handed ``total_vnd=True`` it raises
nothing and splits one dong across the group. ``vietqr.build_payload`` is the
layer that already knew this and spells ``isinstance(amount_vnd, bool)`` out
before its int check.

So this file does two things the existing test does not:

1. It probes every money field on every request body the app actually serves,
   found by walking the routes rather than by listing names here -- a list would
   go stale the first time someone adds a route, and go stale silently.
2. It asserts on behaviour, not on how pydantic spells strictness internally.
   A field passes only by refusing the value.

Scope, stated so the green is readable: this gate covers fields carrying money
on *request* bodies. Response models are deliberately out -- a lax int there
launders a float the service already computed, which is a different defect with
a different fix, recorded in the PR rather than half-covered here.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError, create_model

from app.api.main import app

# A money field is named for its unit. The codebase is consistent about this,
# and the two dict-valued fields below carry money in their values instead.
MONEY_SUFFIX = "_vnd"
MONEY_VALUED_DICTS = ("allocations", "expected_allocations")

# The shapes a money field must refuse. `True` is listed as its own case rather
# than folded into "not an int", because it is the one that survives the check
# people actually write.
REJECTED = (
    pytest.param("82000", id="string"),
    pytest.param(82000.0, id="integral-float"),
    pytest.param(82000.5, id="fractional-float"),
    pytest.param(True, id="bool-true"),
)


def _request_body_models() -> set[type[BaseModel]]:
    """Every pydantic model the app accepts as a request body."""
    models: set[type[BaseModel]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.body_field is None:
            continue
        annotation = getattr(route.body_field.field_info, "annotation", None)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            models.add(annotation)
    return models


def _nested(model: type[BaseModel], seen: set[type[BaseModel]]) -> None:
    """Collect `model` and every pydantic model reachable from its fields.

    Money hides one level down more often than not: `ExpenseInput` holds no
    amount itself, its items and surcharges do.
    """
    if model in seen:
        return
    seen.add(model)
    for field in model.model_fields.values():
        for arg in _leaves(field.annotation):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                _nested(arg, seen)


def _leaves(annotation) -> list:
    """Flatten `X | None`, `list[X]`, `dict[K, V]` down to the types inside."""
    args = getattr(annotation, "__args__", None)
    if not args:
        return [annotation]
    out = []
    for arg in args:
        out.extend(_leaves(arg))
    return out


def money_fields() -> list[tuple[str, str, object]]:
    """(model name, field name, faithful annotation) for each money field.

    The annotation has to be rebuilt from `field.annotation` *and*
    `field.metadata`. Pydantic v2 splits `Annotated[int, Field(strict=True)]`
    into a bare `int` annotation with the `Strict` constraint filed under
    metadata, so probing `field.annotation` alone silently drops the very
    property under test and reports all 31 cases as holes. That was the first
    version of this file, and the failure it produced was indistinguishable
    from a real defect until the constraint was printed out.
    """
    seen: set[type[BaseModel]] = set()
    for model in _request_body_models():
        _nested(model, seen)

    found = []
    for model in sorted(seen, key=lambda m: m.__name__):
        for name, field in model.model_fields.items():
            if name.endswith(MONEY_SUFFIX) or name in MONEY_VALUED_DICTS:
                annotation = field.annotation
                if field.metadata:
                    annotation = Annotated[tuple([annotation, *field.metadata])]
                found.append((model.__name__, name, annotation))
    return found


MONEY_FIELDS = money_fields()


def test_the_gate_found_money_fields_to_check():
    """An empty scope would let every case below pass by having nothing to run.

    This is the failure mode that makes a gate worse than no gate: it reports
    the same green whether the rule holds or whether the walker stopped finding
    routes. So the scope is asserted before anything is probed, and named
    fields are pinned so that a walk which silently degrades to a handful of
    shallow fields is a failure too.
    """
    # 13 is what the walk finds today across 37 reachable models: six on bill
    # creation, five on the expense pipeline, one outing budget, one receipt
    # confirmation. A floor rather than an equality, so adding a money field
    # does not fail this test -- the new field simply gets probed like the
    # rest. Losing one does fail, which is the direction that matters.
    assert len(MONEY_FIELDS) >= 13, (
        f"walker found only {len(MONEY_FIELDS)} money fields"
    )

    pairs = {(model, field) for model, field, _ in MONEY_FIELDS}
    # One top-level amount, one nested inside a list of line items, and one
    # dict whose values are the money. If any of the three stops being found,
    # the walk lost a shape rather than the schema losing a field.
    for expected in (
        ("ExpenseInput", "total_amount_vnd"),
        ("ExpenseItemInput", "amount_vnd"),
        ("ExpenseConfirmationRequest", "expected_allocations"),
    ):
        assert expected in pairs, f"{expected} missing -- the walker lost a shape"


def _probe(annotation, value):
    """Feed `value` to a model whose only field has `annotation`.

    Behaviour, not shape: the field passes by refusing, however pydantic
    happens to record strictness this release.
    """
    model = create_model("Probe", v=(annotation, ...))
    return model(v=value)


def _payload_for(annotation, value):
    """Put `value` where the money actually sits inside `annotation`."""
    origin = getattr(annotation, "__origin__", None)
    if origin is dict:
        return {str(uuid.uuid4()): value}
    if origin is list:
        return [value]
    return value


@pytest.mark.parametrize("value", REJECTED)
@pytest.mark.parametrize(
    "model_name,field_name,annotation",
    [pytest.param(m, f, a, id=f"{m}.{f}") for m, f, a in MONEY_FIELDS],
)
def test_money_fields_refuse_non_integer_wire_values(
    model_name, field_name, annotation, value
):
    payload = _payload_for(annotation, value)
    with pytest.raises(ValidationError):
        _probe(annotation, payload)


def test_a_bool_total_would_have_become_a_one_dong_bill(client, repository):
    """The wire is the only thing standing between `true` and a one-dong bill.

    Worth an end-to-end case rather than a unit probe, because the claim is
    about what the product does, not about what a type refuses. The allocator
    is handed `True` in the docstring above and splits one dong without
    complaint; this asserts nobody can get it there.
    """
    from .helpers import expense_payload

    response = client.post("/expenses", json=expense_payload(total=True))

    assert response.status_code == 422
    assert repository.expenses == {}
    assert repository.confirmed == {}


def test_a_float_total_never_reaches_the_domain_or_storage(client, repository):
    """The shape `schemas.py` names in its own docstring and nothing tested."""
    from .helpers import expense_payload

    response = client.post("/expenses", json=expense_payload(total=82000.0))

    assert response.status_code == 422
    assert repository.expenses == {}
    assert repository.confirmed == {}
