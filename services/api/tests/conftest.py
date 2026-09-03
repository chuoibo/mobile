"""Suite-wide default: the tests run the header adapter unless they say otherwise.

`create_app()` with no argument is `prod` now, and `prod` refuses `X-Actor-*`.
Around sixty test modules build their own application and then authenticate
with those headers, so without this the change to the default would have shown
up as sixty files of churn -- and a diff that size hides the thing being
reviewed.

`setdefault`, not assignment: exporting `MOBILE_AUTH_MODE=prod` before pytest
still wins, which is how you run the existing suite against the strict adapter
and see what it says.

What this must never do is make the product's own default untestable. It does
not: `tests/api/test_auth_mode.py` asks `resolve_auth_mode` about an
environment with the variable removed, and `tests/api/test_prod_session_auth.py`
builds its applications with `auth_mode="prod"` explicitly. Neither reads the
value set here.
"""

from __future__ import annotations

import os

from app.api.auth_mode import AUTH_MODE_ENV_VAR, DEV

os.environ.setdefault(AUTH_MODE_ENV_VAR, DEV)
