"""Borrow both test tiers' fixtures without forking either one.

This directory needs the fake-repository `client`/`repository` pair from
`services/api/tests/api/conftest.py` *and* the real-database `postgres_session`
from `services/api/tests/postgres/conftest.py`. Re-declaring either here would
create a second, drifting definition of "the API under test", which is exactly
the failure this lane is auditing: two copies of a rule, one of them stale.

The loading is deliberately awkward for reasons `tests/qa/rd-qa-13/conftest.py`
already paid for:

* not `pytest_plugins` -- only legal in a top-level conftest, and the gate
  command `python3 -m pytest services/api/tests tests -q` puts the rootdir
  above this file, so pytest refuses the whole collection.
* not `import tests.api.conftest` -- there are two directories named `tests` in
  this repository and which one wins depends on sys.path order.

`services/api/tests/api/conftest.py` also does `from .helpers import ...`, so it
cannot be loaded as a lone module the way the postgres one can: a relative
import needs a package to be relative *to*. A synthetic package is registered
first, with `__path__` pointing at the real directory, so `.helpers` resolves to
the same file the backend suite uses.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[3] / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

_PKG = "rd_qa_40_api_fixtures"


def _load_api_package() -> types.ModuleType:
    package = types.ModuleType(_PKG)
    package.__path__ = [str(API_ROOT / "tests" / "api")]
    sys.modules[_PKG] = package

    def load(name: str) -> types.ModuleType:
        path = API_ROOT / "tests" / "api" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"{_PKG}.{name}", path)
        assert spec is not None and spec.loader is not None, path
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    load("helpers")
    return load("conftest")


_api = _load_api_package()

_PG_FIXTURES = API_ROOT / "tests" / "postgres" / "conftest.py"
_spec = importlib.util.spec_from_file_location("rd_qa_40_pg_fixtures", _PG_FIXTURES)
assert _spec is not None and _spec.loader is not None, _PG_FIXTURES
_pg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pg)

# Re-exported so pytest sees them as fixtures of this directory.
repository = _api.repository
client = _api.client
postgres_engine = _pg.postgres_engine
postgres_session = _pg.postgres_session


def pytest_configure(config):
    """Register `postgres` here too -- the repo root declares no pytest config.

    Same reasoning as `tests/qa/rd-qa-13/conftest.py`: `--strict-markers` lives
    in `services/api/pyproject.toml`, and the gate command picks a rootdir that
    never reads it. An unregistered mark is one flag away from failing
    collection, and `-m postgres` from the wrong directory would silently
    select nothing.
    """
    config.addinivalue_line(
        "markers",
        "postgres: requires a real PostgreSQL database migrated by Alembic",
    )
