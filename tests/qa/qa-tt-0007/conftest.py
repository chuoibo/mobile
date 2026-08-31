"""Load the PostgreSQL fixtures without redefining them.

Follows `tests/qa/qa-tt-0011/conftest.py`, which explains the reasoning in
full: fixtures are loaded by absolute path rather than by `pytest_plugins`
(legal only in a top-level conftest, and this directory is not one) and rather
than by `import tests.postgres.conftest` (two directories in this repository
are named `tests`, so which one wins depends on `sys.path` order).

Only the PostgreSQL half is loaded here. The probe in this directory drives the
real ASGI stack over the real schema, so it has no use for the fake repository.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[3] / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def _load_by_path(relative: str, module_name: str):
    path = API_ROOT / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_pg = _load_by_path("tests/postgres/conftest.py", "qa_tt_0007_pg_fixtures")

# `live_client` -- the real ASGI stack on one throwaway transaction -- lives in
# a test module rather than a conftest, so it is re-exported here instead of
# imported by the probe. Importing it there and then naming it as a test
# argument is a redefinition (ruff F811); re-exporting is how a fixture defined
# elsewhere becomes a fixture of this directory.
_idem = importlib.import_module("tests.postgres.test_idempotency_postgres")

# Re-exported so pytest sees them as fixtures of this directory.
postgres_engine = _pg.postgres_engine
postgres_session = _pg.postgres_session
live_client = _idem.live_client


def pytest_configure(config):
    """Register `postgres` here too; the repo root declares no pytest config."""

    config.addinivalue_line(
        "markers",
        "postgres: requires a real PostgreSQL database migrated by Alembic",
    )
