"""Reuse the real PostgreSQL fixtures without breaking the repo-wide gate.

`services/api/tests/postgres/conftest.py` migrates a throwaway schema with
Alembic and refuses non-PostgreSQL URLs. Copying that setup here would create a
second, drifting definition of "a real database", so this file loads it.

It does NOT load it with `pytest_plugins`. That is only legal in a top-level
conftest, and this directory is not one: `python3 -m pytest services/api/tests
tests -q` -- the gate command in CLAUDE.md -- picks a rootdir above this file
and pytest then refuses the whole collection, taking all 1010 passing cases
down with it. An earlier revision of this helper did exactly that.

It also does not `import tests.postgres.conftest`. There are two directories
named `tests` in this repository, and which one wins depends on sys.path order
at the moment of import -- a gate whose result depends on which directory you
invoked it from is not a gate.

Loading the file by absolute path avoids both problems: no plugin registration,
no package-name race. Fixtures imported into a conftest namespace are visible to
tests in that directory, so `postgres_engine` and `postgres_session` work the
same as if they had been declared here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[3] / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

_FIXTURES = API_ROOT / "tests" / "postgres" / "conftest.py"
_spec = importlib.util.spec_from_file_location("rd_qa_13_pg_fixtures", _FIXTURES)
assert _spec is not None and _spec.loader is not None, _FIXTURES
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

# Re-exported so pytest sees them as fixtures of this directory.
postgres_engine = _module.postgres_engine
postgres_session = _module.postgres_session
