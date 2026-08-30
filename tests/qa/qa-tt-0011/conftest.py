"""Load the API and PostgreSQL fixtures without redefining either of them.

Same reasoning as `tests/qa/rd-qa-13/conftest.py`, which this follows: the
fixtures are loaded by absolute path rather than by `pytest_plugins` (only
legal in a top-level conftest, and this directory is not one) and rather than
by `import tests.api.conftest` (two directories in this repository are named
`tests`, so which one wins depends on `sys.path` order at import time).

Two files are loaded here instead of one because the finding this directory
gates has a fake-visible half and a live-only half, and they must not be
collapsed into a single tier:

  * `POST /bills` storing a share for a non-member is visible against the fake,
    so that case runs in the default gate with no database.
  * The allocator handing that non-member money only happens when the roster
    comes back empty, and the fake's roster is never empty by construction --
    `tests/api/conftest.py` returns two active rows for every context. Only a
    real `memberships` table can be empty, so that case is live-only.
"""

from __future__ import annotations

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


# `tests/api/conftest.py` does `from .helpers import ...`, so it can only be
# loaded as a member of its own package -- a bare path load raises "attempted
# relative import with no known parent package". `tests.api` exists in exactly
# one place on disk, so there is no portion to race with here: `tests` resolves
# as a namespace package spanning both trees and only `services/api` holds an
# `api` subpackage.
_api = importlib.import_module("tests.api.conftest")
# `tests/postgres/conftest.py` has no relative imports, so it keeps the
# by-path load `rd-qa-13` established.
_pg = _load_by_path("tests/postgres/conftest.py", "qa_tt_0011_pg_fixtures")

# Re-exported so pytest sees them as fixtures of this directory.
repository = _api.repository
client = _api.client
postgres_engine = _pg.postgres_engine
postgres_session = _pg.postgres_session


def pytest_configure(config):
    """Register `postgres` here too; the repo root declares no pytest config.

    `services/api/pyproject.toml` registers the mark, but pytest picks its ini
    file from the rootdir it derives from the invocation arguments, and the
    gate command in CLAUDE.md (`python3 -m pytest services/api/tests tests -q`,
    run from the repo root) lands on a rootdir with no config at all. Without
    this the mark arrives unregistered on every gate run.
    """

    config.addinivalue_line(
        "markers",
        "postgres: requires a real PostgreSQL database migrated by Alembic",
    )
