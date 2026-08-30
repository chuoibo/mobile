"""Every route declaration must survive the fastapi version the *image* installs.

## The defect this exists to catch

On 2026-08-30 `main` shipped a tree where 1922 pytest cases passed and the API
could not start. `DELETE /contexts/{id}/memories/{id}/reactions` declared
`status_code=204` on a function annotated `-> None`, inside a module carrying
`from __future__ import annotations`. Under fastapi 0.115.6 -- the version
`services/api/pyproject.toml` admits and the image resolves -- that raises at
*import* time:

    AssertionError: Status code 204 must not have a response body

The demo container exited on boot and the shared machine was down.

## Why the whole suite was structurally unable to notice

The failing assertion lives in `APIRoute.__init__`, and it is byte-for-byte the
same code in both versions. What differs is one step upstream, in
`get_typed_return_annotation`:

    deferred `-> None`     0.115.6 -> <class 'NoneType'>   truthy  -> asserts
                           0.135.3 -> None                 falsy   -> silent

So on a developer machine with a newer fastapi the declaration is legal, the
app imports, and every case that goes through it is green *honestly*. No
assertion on a response, a status code or an OpenAPI document can see this,
because on this machine there is nothing wrong. Only an interpreter with the
older resolver disagrees, and until now the only stage that ran one was
`docker` -- a stage that builds an image, and so is the stage people skip.

This file removes the dependence on remembering to run that stage. It is not a
substitute for it: `docker` proves the image boots, this proves one specific
reason it would not.

## How it measures, and why not by reading the source

The obvious cheap gate is a grep or an AST walk for `status_code=204` next to
`-> None`. That gate measures the source text and not the framework's rule, so
it drifts the first time fastapi changes its inference and it cannot see a
status code that arrives through a constant or an enum.

Instead a child interpreter restores the *old* resolver and imports the real
app. The assertion that fires is then fastapi's own, on the real routers, with
the real error string -- there is no second implementation of the rule here to
disagree with the library. The emulation narrows to the deferred spelling on
purpose: written without `from __future__ import annotations`, `-> None` is the
`None` object on both versions and neither asserts, so firing on every `-> None`
would make this gate stricter than the library it is protecting against, and a
gate that reports defects the shipped code does not have gets deleted.

`SHAPES` below is the mutation table, and it is executable rather than
described. Three rows must be refused and five must be accepted; the accepted
rows are what stops this from being a gate that merely notices somebody edited
a route. The row that carries the most weight is `plain_none_204`, the
non-deferred spelling: it is the one that separates "measures the pinned rule"
from "allergic to the characters `-> None`".
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

#: `services/api`, the directory a child interpreter needs on its path to
#: resolve `app`. pytest supplies this from `pythonpath` in pyproject.toml; a
#: bare interpreter does not read that setting.
API_ROOT = Path(__file__).resolve().parents[2]

# One definition of the emulation, run by the real gate and by every canary
# alike. A canary exercising a second copy would stop measuring the gate.
CHILD = r'''
import importlib
import inspect
import os

import fastapi.routing
from fastapi.dependencies.utils import get_typed_return_annotation as _modern


def _pinned(call):
    """Return what fastapi 0.115.6 inferred, on whatever fastapi is installed.

    0.115.6 evaluated a deferred `-> None` to the class `NoneType`, which is
    truthy, and so concluded the route carried a response model. Newer fastapi
    normalises the same annotation to `None`. Nothing else about the assertion
    changed, so restoring this one value restores the old verdict exactly.
    """
    inferred = _modern(call)
    if inferred is None and isinstance(inspect.signature(call).return_annotation, str):
        return type(None)
    return inferred


fastapi.routing.get_typed_return_annotation = _pinned
importlib.import_module(os.environ["PINNED_IMPORT_TARGET"])
print("IMPORT OK")
'''

#: name -> (module source, must the pinned resolver refuse it?)
#:
#: Read as a mutation table: the `True` rows are declarations that took the
#: container down, the `False` rows are edits a person tidying this file would
#: plausibly make and which must not turn the gate red.
SHAPES = {
    # --- must be refused ------------------------------------------------
    # Exactly the declaration that stopped the image booting.
    "deferred_none_204": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.delete('/x', status_code=204)\n"
        "def x() -> None: ...\n",
        True,
    ),
    # 304 is bodyless too; the defect is the status class, not the number 204.
    "deferred_none_304": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/x', status_code=304)\n"
        "def x() -> None: ...\n",
        True,
    ),
    # A real model behind a bodyless code is the same defect stated loudly, and
    # it is refused by *both* fastapi versions -- so this row also proves the
    # child process reports failures at all.
    "deferred_model_204": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter\n"
        "from pydantic import BaseModel\n"
        "class M(BaseModel):\n"
        "    a: int\n"
        "router = APIRouter()\n"
        "@router.delete('/x', status_code=204)\n"
        "def x() -> M: ...\n",
        True,
    ),
    # --- must be accepted -----------------------------------------------
    # The load-bearing row. Without `from __future__ import annotations` the
    # annotation is the `None` object, 0.115.6 does not assert, and neither may
    # this gate. Measured against a real 0.115.6 interpreter, not assumed.
    "plain_none_204": (
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.delete('/x', status_code=204)\n"
        "def x() -> None: ...\n",
        False,
    ),
    # What `contexts.py` already does, and the reason its two 204 routes were
    # never affected: a `Response` subclass suppresses the response model.
    "deferred_response_204": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter, Response\n"
        "router = APIRouter()\n"
        "@router.delete('/x', status_code=204)\n"
        "def x() -> Response: ...\n",
        False,
    ),
    # The fix. Passing the model explicitly skips the inference entirely.
    "deferred_none_204_explicit_model": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.delete('/x', status_code=204, response_model=None)\n"
        "def x() -> None: ...\n",
        False,
    ),
    # 200 allows a body, so the same annotation is fine. Guards against a gate
    # that keys off the annotation and forgets the status code.
    "deferred_none_200": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/x', status_code=200)\n"
        "def x() -> None: ...\n",
        False,
    ),
    # No annotation at all: `get_typed_return_annotation` returns None from the
    # empty signature on both versions, and must not be mistaken for `NoneType`.
    "deferred_unannotated_204": (
        "from __future__ import annotations\n"
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.delete('/x', status_code=204)\n"
        "def x(): ...\n",
        False,
    ),
}

REFUSAL = "must not have a response body"


def import_under_pinned_fastapi(target: str, extra_path: Path | None = None):
    """Import `target` in a child whose fastapi infers like the pinned one."""

    env = dict(os.environ)
    env["PINNED_IMPORT_TARGET"] = target
    search = [str(API_ROOT)] + ([str(extra_path)] if extra_path else [])
    env["PYTHONPATH"] = os.pathsep.join(search)
    return subprocess.run(
        [sys.executable, "-c", CHILD],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(API_ROOT),
        timeout=300,
    )


def test_no_route_declaration_breaks_under_the_fastapi_the_image_installs():
    """The gate itself: the real app, imported by the old resolver.

    A failure here means the container will not boot, whatever pytest says on
    this machine. The assertion text names the offending status code; the
    module and function are in the traceback.
    """

    result = import_under_pinned_fastapi("app.api.main")

    assert result.returncode == 0, (
        "app.api.main does not import under the fastapi resolver the image "
        "installs, so the container will exit on boot while this machine's "
        "newer fastapi accepts the same declaration.\n"
        "Fix: pass `response_model=None` in the decorator of the route named "
        "in the traceback, or annotate it `-> Response`.\n"
        f"--- child stderr ---\n{result.stderr}"
    )


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_the_pinned_resolver_refuses_exactly_the_declarations_it_should(
    name: str, tmp_path: Path
):
    """The mutation table, run rather than described.

    Three shapes must be refused and five must be accepted. Without the
    accepted rows a red result here would only prove the child process can
    fail, which is not the same as proving it fails for the right reason.
    """

    source, must_be_refused = SHAPES[name]
    module = f"shape_{name}"
    (tmp_path / f"{module}.py").write_text(source)

    result = import_under_pinned_fastapi(module, extra_path=tmp_path)

    if must_be_refused:
        assert result.returncode != 0, (
            f"{name} declares a response body on a bodyless status code and "
            f"the pinned resolver accepted it; the gate is blind.\n{result.stdout}"
        )
        assert REFUSAL in result.stderr, (
            f"{name} failed, but not with fastapi's response-body assertion, "
            f"so the failure does not measure what this table claims.\n"
            f"{result.stderr}"
        )
    else:
        assert result.returncode == 0, (
            f"{name} is legal under the pinned fastapi but this gate refused "
            f"it. A gate stricter than the library it protects reports defects "
            f"the shipped code does not have.\n{result.stderr}"
        )


def test_the_shape_table_is_literal_so_a_pinned_interpreter_can_read_it():
    """`SHAPES` must stay `ast.literal_eval`-able.

    The equivalence measurement in the pull request runs this same table on a
    real fastapi 0.115.6, which has neither pytest nor `app` installed and so
    parses this file instead of importing it. Keeping the table a literal is
    what lets that check read the committed corpus rather than a second copy
    of it that could drift.
    """

    tree = ast.parse(Path(__file__).read_text())
    assigned = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == "SHAPES" for t in node.targets)
    ]

    assert len(assigned) == 1, "SHAPES must be assigned exactly once, as a literal"
    assert ast.literal_eval(assigned[0].value) == SHAPES
