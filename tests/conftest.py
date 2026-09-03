"""Suite-wide default for the repo-root tests: the header adapter, unless asked.

The twin of `services/api/tests/conftest.py`, and the reason there are two.

`scripts/postgres_tier.sh` runs the live tier as **two pytest processes**, both
invoked from `services/api`: one over `tests/postgres`, one over `../../tests/qa`.
The second collects nothing under `services/api/tests`, so the conftest there
never imports, and the sixteen live QA cases that authenticate with `X-Actor-*`
met the `prod` default and answered 401 -- twenty-two of them, measured in CI on
2026-09-03 and reproduced locally with the same command.

That is the failure mode of this mechanism, and it is worth naming: an
invocation nobody thought of gets `prod` and goes **red**. Loud rather than
silent, which is the right direction for a default that exists to fail closed --
but it does mean a third test root added later needs a third line like this one.

`setdefault`, not assignment: exporting `MOBILE_AUTH_MODE=prod` before pytest
still wins, which is how you run these suites against the strict adapter on
purpose.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# `tests/qa` reaches into the API package; the path is added here rather than
# depending on which directory pytest happened to be invoked from.
API_ROOT = Path(__file__).resolve().parents[1] / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.api.auth_mode import AUTH_MODE_ENV_VAR, DEV  # noqa: E402

os.environ.setdefault(AUTH_MODE_ENV_VAR, DEV)
