"""No route may promise a response body under a status code that forbids one.

## Why this file exists

``DELETE /contexts/{cid}/memories/{mid}/reactions`` reached ``main`` declaring
``status_code=204`` on a handler annotated ``-> None``. The suite was green --
2305 cases -- and the container built from that same commit could not start:

    AssertionError: Status code 204 must not have a response body
    fastapi/routing.py:507 __init__ -> is_body_allowed_for_status_code

That assertion runs while the router is being *built*, so nothing is served at
all: no route, no ``/healthz``, not even a 500. The process dies on import, and
the healthcheck never gets a first answer.

What no test in this repository was measuring is the version of the library
underneath it:

    fastapi pinned in requirements-dev.txt : 0.115.6   <- what the image installs
    fastapi installed on the test machine  : 0.135.3   <- what pytest imported

Both read the same source and disagree about whether the product boots. The
difference is one line of upstream behaviour, measured on both:

    def d() -> None: ...        # in a module with `from __future__ import annotations`

    0.115.6  get_typed_return_annotation(d) -> <class 'NoneType'>   truthy
    0.135.3  get_typed_return_annotation(d) -> None                 falsy

``APIRoute.__init__`` guards the assertion with ``if self.response_model:``.
Truthy reaches it; falsy walks past. The ``__future__`` import is what makes
the difference reachable: it hands FastAPI the *string* ``"None"``, and
resolving a string annotation goes through ``typing._type_check``, which maps a
bare ``None`` to the ``NoneType`` class. Without that import the annotation
stays the falsy ``None`` object. Every routes module in this package has the
import.

That is also why the sibling 204 route in ``contexts.py`` has always been
fine: it is written ``-> Response`` and returns ``Response(status_code=204)``,
and ``APIRoute`` reads a ``Response`` subclass as "the endpoint writes its own
body".

## Why the check is spelled out rather than delegated

The obvious test -- register the routes and watch for an exception -- is green
on this machine for exactly the reason the bug got through: the installed
FastAPI does not object. So is any check built on the installed
``get_typed_return_annotation``, which is the single function whose behaviour
changed. A gate that only fires on the version we do not ship is silent on the
version we do.

So the resolution rule of 0.115.6 is restated here in nine lines, using no
FastAPI internals that moved: read the annotation, evaluate it if it is a
string, map a bare ``None`` to ``NoneType``, and let a ``Response`` subclass
through. The predicate then holds whichever FastAPI is installed, which is the
property the bug proves we need.

Two shapes pass, because both are honest:

  * ``-> Response``, returning ``Response(status_code=204)``
  * no return annotation at all

What does not pass is a body-less status code beside a return annotation that
names anything else -- ``None`` included.

## What this does NOT prove

It proves no route *declares* a body under a body-less status code. It says
nothing about whether the rest of the application imports under the pinned
tree, and nothing about the eight other packages that drift from their pins on
this machine (alembic, jinja2, psycopg, pytest, pytest-subtests, segno,
sqlalchemy, uvicorn). Only building the image proves that, and that is
``scripts/gate.sh docker``.
"""

from __future__ import annotations

import inspect

from fastapi.responses import Response
from fastapi.routing import APIRoute
from fastapi.utils import is_body_allowed_for_status_code

from app.api.main import create_app


def _response_model_under_the_pin(endpoint: object) -> object | None:
    """What FastAPI 0.115.6 would store in ``route.response_model``.

    Recomputed from the endpoint instead of read off ``route.response_model``,
    and deliberately not built on ``get_typed_return_annotation``: that helper
    is the one whose behaviour differs between the installed version and the
    pinned one, so asking it would answer the wrong version's question.

    Returns ``None`` when the route promises no body, otherwise the annotation
    that constitutes the promise.
    """

    annotation = inspect.signature(endpoint).return_annotation
    if annotation is inspect.Signature.empty:
        return None

    if isinstance(annotation, str):
        # `from __future__ import annotations` is in force in every routes
        # module, so this is the live path, not a fallback. FastAPI resolves the
        # string through a ForwardRef; the eval below is the same step with the
        # same globals.
        annotation = eval(annotation, getattr(endpoint, "__globals__", {}))  # noqa: S307

    if annotation is None:
        # `typing._type_check` turns a bare `None` into the NoneType class, and
        # a class is truthy. This single line is the bug.
        annotation = type(None)

    if isinstance(annotation, type) and issubclass(annotation, Response):
        return None

    return annotation


def _bodyless_status_routes() -> list[APIRoute]:
    return [
        route
        for route in create_app().routes
        if isinstance(route, APIRoute)
        and route.status_code is not None
        and not is_body_allowed_for_status_code(route.status_code)
    ]


def test_no_route_declares_a_body_under_a_bodyless_status_code() -> None:
    routes = _bodyless_status_routes()

    # A search that reports nothing is indistinguishable from a search that ran
    # over nothing. This repository serves 204 on at least one path, so finding
    # none of them means the walk broke, not that the tree is clean.
    assert routes, (
        "no route in the app declares a body-less status code -- either every "
        "204 route was deleted or this walk stopped seeing routes, and in "
        "both cases the assertion below is guarding nothing"
    )

    offenders = [
        f"{sorted(route.methods or [])} {route.path} status_code="
        f"{route.status_code} declares a body: {model!r}"
        for route in routes
        if (model := _response_model_under_the_pin(route.endpoint)) is not None
    ]

    assert not offenders, (
        "These routes promise a response body under a status code that forbids "
        "one. FastAPI 0.115.6 -- pinned in requirements-dev.txt, installed in "
        "the image -- raises AssertionError while registering them, so "
        "`app.api.main` does not import and the container never answers "
        "/healthz:\n  " + "\n  ".join(offenders)
    )


def _returns_none() -> None:  # pragma: no cover -- inspected, never called
    """The exact shape of the defect: bare ``None`` under a ``__future__`` import."""


def _returns_response() -> Response:  # pragma: no cover -- inspected, never called
    """The sanctioned shape, as written in ``contexts.py``."""
    raise NotImplementedError


def _returns_a_model() -> _SomeModel:  # pragma: no cover -- inspected, never called
    """An ordinary body-bearing handler."""
    raise NotImplementedError


def _unannotated():  # pragma: no cover -- inspected, never called
    """No promise made either way."""


def test_the_predicate_tells_the_four_shapes_apart() -> None:
    """Negative and positive controls for the predicate itself.

    Without these, the test above passes whenever ``_response_model_under_the_pin``
    returns ``None`` for everything -- which is what a changed upstream helper,
    a renamed attribute or an annotation it cannot evaluate would look like. The
    first case is deliberately the shape that shipped, not a convenient stand-in:
    ``-> None`` resolved through a string annotation is the one the installed
    FastAPI reports as falsy and the pinned one reports as truthy.
    """

    assert _response_model_under_the_pin(_returns_none) is type(None), (
        "the predicate no longer sees `-> None` as a body promise; the gate "
        "above cannot fail for the reason it exists"
    )
    assert _response_model_under_the_pin(_returns_a_model) is _SomeModel
    assert _response_model_under_the_pin(_returns_response) is None
    assert _response_model_under_the_pin(_unannotated) is None


class _SomeModel:
    """Stands in for a response schema in the controls above.

    A plain class rather than a pydantic model: the predicate asks only whether
    the annotation names something other than ``Response``, and a real schema
    would pull pydantic into a test about route declarations.
    """
