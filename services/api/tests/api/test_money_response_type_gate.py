"""Money law 1 on the way out: no money field on a response launders a non-int.

The sibling file `test_money_wire_type_gate.py` closed the request side and said
in its own docstring that responses were deliberately left out, because a lax
`int` there launders a value the service already computed -- a different defect
with a different fix. This is that fix.

Laundering is the whole problem, and it is worth stating precisely because it is
what makes the defect invisible rather than merely present. A field declared
plain `int` in pydantic v2 runs in lax mode, so:

    82000.0  ->  82000     a float that reached money, rendered as if it never did
    True     ->  1         a one-dong amount, rendered as money
    "82000"  ->  82000     a string that reached money, likewise

Only `82000.5` is refused, and it is refused as a 500. So the shapes that get
through are exactly the ones a reader cannot tell apart from a correct answer,
and the shape that fails does so in the least useful way.

That is why no assertion on an HTTP body can catch this. By the time a test can
read `response.json()["spend_vnd"]`, pydantic has already turned the service's
`Decimal("520000")` or `520000.0` into `520000`. The test compares `520000 ==
520000` and passes. The suite is structurally incapable of noticing, which is a
stronger statement than "nobody wrote the test yet": writing more body
assertions would not help.

What is upstream today. Every current producer of these figures is guarded
somewhere: the repository casts its `SUM`s (`tests/qa/rd-qa-39` measures that
those casts are individually gated), `_integer_dong` guards the model-authored
budget and history figures, and `normalize_vnd` guards receipt money. So this
gate does not fix a live wrong number. It removes the wire's dependence on all
of those guards staying correct, and on the next money field being added by
someone who knows about them.

The asymmetry that gives the game away is in `FinanceMovementView`: the
counterparty's *name* is `StrictStr`, and the *amount of money* is a plain
`int`. Nobody decided that money deserved less checking than a display name.

One trap, recorded because this file's author walked into it while measuring.
Classifying a field as strict by reading `field.metadata` is wrong: for
`allocations: dict[UUID, MoneyVnd]` the strictness lives in the dict's *value*
type and the field's own metadata is empty, so a metadata check reports the
allocator's own output as lax. Read by behaviour instead -- a field passes only
by refusing the value -- which is what the sibling file concluded for its own
reasons and what every case below does.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError, create_model

from app.api.main import app

# Imported rather than copied. `_leaves` and `_nested` are pure tree-flatteners
# shared with the request gate; a second copy is the shape that drifts silently,
# and if the sibling is ever renamed this import fails loudly instead.
from .test_money_wire_type_gate import (
    MONEY_SUFFIX,
    MONEY_VALUED_DICTS,
    _leaves,
    _nested,
)

REJECTED = (
    pytest.param("82000", id="string"),
    pytest.param(82000.0, id="integral-float"),
    pytest.param(82000.5, id="fractional-float"),
    pytest.param(True, id="bool-true"),
)


def _response_models() -> set[type[BaseModel]]:
    """Every pydantic model reachable from a declared `response_model`."""
    models: set[type[BaseModel]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.response_model is None:
            continue
        for leaf in _leaves(route.response_model):
            if isinstance(leaf, type) and issubclass(leaf, BaseModel):
                _nested(leaf, models)
    return models


def money_fields() -> list[tuple[str, str, object]]:
    """(model name, field name, faithful annotation) for each response money field.

    The annotation is rebuilt from `field.annotation` *and* `field.metadata`,
    for the reason the sibling file records: pydantic v2 splits
    `Annotated[int, Field(strict=True)]` into a bare `int` plus a `Strict`
    constraint filed under metadata, and probing the annotation alone drops the
    property under test.
    """
    found = []
    for model in sorted(_response_models(), key=lambda m: m.__name__):
        for name, field in model.model_fields.items():
            if name.endswith(MONEY_SUFFIX) or name in MONEY_VALUED_DICTS:
                annotation = field.annotation
                if field.metadata:
                    annotation = Annotated[tuple([annotation, *field.metadata])]
                found.append((model.__name__, name, annotation))
    return found


MONEY_FIELDS = money_fields()


def test_the_gate_found_response_money_fields_to_check():
    """An empty scope passes every case below by having nothing to run.

    This is the failure mode that makes a gate worse than none: the same green
    whether the rule holds or whether the walk stopped finding routes. So scope
    is asserted before anything is probed, and four fields are pinned by name so
    a walk that quietly degrades to a shallow handful fails too.
    """
    # 41 is what the walk finds today. A floor rather than an equality, so a new
    # money field does not fail this test -- it simply gets probed like the
    # rest. Losing one does fail, which is the direction that matters.
    assert len(MONEY_FIELDS) >= 41, f"walk found only {len(MONEY_FIELDS)} money fields"

    pairs = {(model, field) for model, field, _ in MONEY_FIELDS}
    # Four structural shapes, not four favourite fields. If any stops being
    # found, the walk lost a shape rather than the schema losing a field.
    for expected in (
        # flat, and the figure the personal finance screen is built around
        ("PersonFinanceResponse", "spend_vnd"),
        # dict-valued: the money is in the values, and this is the allocator's
        # own output going back to the client
        ("AllocationProposal", "allocations"),
        # reached only through a list of nested models
        ("BillItemResponse", "unit_price_vnd"),
        # declared in app/api/routes/places.py, so the walk is proven to cross
        # module boundaries rather than to read schemas.py
        ("Understood", "budget_per_person_vnd"),
    ):
        assert expected in pairs, f"{expected} missing -- the walk lost a shape"


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
def test_response_money_fields_refuse_non_integer_values(
    model_name, field_name, annotation, value
):
    """Behaviour, not shape: the field passes by refusing, however pydantic
    happens to spell strictness this release."""
    probe = create_model("Probe", v=(annotation, ...))
    with pytest.raises(ValidationError):
        probe(v=_payload_for(annotation, value))


def test_a_plain_int_field_would_have_laundered_all_three_shapes():
    """Why the gate exists, asserted rather than described.

    Every case above says a field refuses. This one says what acceptance would
    have *looked like*, and it is the reason the defect could never surface in a
    body assertion: the laundered value is a plausible integer. If pydantic ever
    stops laundering, this fails and the rationale above needs rewriting.
    """
    lax = create_model("Lax", v=(int, ...))

    assert lax(v=82000.0).v == 82000
    assert lax(v="82000").v == 82000
    # The sharp one. `bool` subclasses `int`, so every `isinstance(x, int)`
    # written to defend money says yes to `True` -- and the amount it renders
    # is one dong, not an obviously broken value a reader would question.
    assert lax(v=True).v == 1


def test_a_float_spend_is_refused_by_the_real_response_model():
    """The generic walk again, but through a model the product actually returns.

    Worth its own case because the walk probes a rebuilt annotation, not the
    declared class. If `PersonFinanceResponse` were somehow assembled so that
    the rebuild disagreed with the real thing, every case above could pass while
    the shipped model still laundered.
    """
    from app.api.schemas import PersonFinanceResponse

    fields = {
        "person_id": uuid.uuid4(),
        "display_name": "Kiet",
        "spend_vnd": 750_000,
        "settled_vnd": 250_000,
        "outstanding_vnd": 500_000,
        "receivable_vnd": 120_000,
        "expense_count": 3,
        "group_count": 1,
        "movements": [],
    }

    assert PersonFinanceResponse(**fields).spend_vnd == 750_000

    # Every money field on the model, not just the first one. A new amount
    # added later is exactly where a `float` slips in unnoticed, and naming
    # only `spend_vnd` here would let it: this loop went red the moment
    # `receivable_vnd` was declared and would have stayed green had it been
    # typed as a plain `int`.
    for field in ("spend_vnd", "settled_vnd", "outstanding_vnd", "receivable_vnd"):
        for bad in (750_000.0, True, "750000"):
            with pytest.raises(ValidationError):
                PersonFinanceResponse(**{**fields, field: bad})
