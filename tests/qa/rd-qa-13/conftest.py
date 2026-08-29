"""Reuse the real PostgreSQL fixtures instead of re-implementing them.

`services/api/tests/postgres/conftest.py` migrates a throwaway schema with
Alembic and refuses non-PostgreSQL URLs. Copying that setup here would create a
second, drifting definition of "a real database", so this file imports it.
"""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[3] / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

pytest_plugins = ["tests.postgres.conftest"]
