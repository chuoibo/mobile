"""Which identity claim this process trusts.

Two modes, one variable, and the default is the strict one. `dev` keeps the
`X-Actor-*` headers working so the existing suites and the demo box still run;
`prod` refuses them and requires a session the server itself issued.

The default matters more than the switch. A deployment that forgets the
variable gets `prod`, because the failure being guarded against is exactly a
host that quietly kept trusting a header nobody authenticated. Fail-open by
omission would reproduce the incident this module exists to end.

An unrecognised value is a startup error rather than a fallback. `MOBILE_AUTH_MODE=prd`
resolving silently to either mode is a configuration lie: one direction opens
the door, the other closes a door the operator meant to leave open, and neither
is visible in a log line that reports the mode it decided on its own.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = [
    "AUTH_MODE_ENV_VAR",
    "DEV",
    "PROD",
    "AuthModeInvalid",
    "resolve_auth_mode",
    "trusts_actor_headers",
]

AUTH_MODE_ENV_VAR = "MOBILE_AUTH_MODE"

PROD = "prod"
DEV = "dev"

_MODES = frozenset({PROD, DEV})


class AuthModeInvalid(RuntimeError):
    """The variable is set to something that is neither mode."""


def resolve_auth_mode(environ: Mapping[str, str] | None = None) -> str:
    """The mode this process runs in.

    Absent or empty means `prod`. Case and surrounding whitespace are
    forgiven -- `"Dev "` is a legible intent -- but a value that is not one of
    the two modes raises, naming the variable and both accepted values without
    echoing anything else about the environment.
    """

    import os

    env = os.environ if environ is None else environ
    raw = env.get(AUTH_MODE_ENV_VAR, "").strip().lower()
    if not raw:
        return PROD
    if raw in _MODES:
        return raw
    raise AuthModeInvalid(
        f"{AUTH_MODE_ENV_VAR} must be {PROD!r} or {DEV!r}; refusing to guess"
    )


def trusts_actor_headers(mode: str) -> bool:
    """True only in `dev`.

    Written as a question about the mode rather than a comparison spelled out
    at each call site, so a third mode added later cannot become trusted by
    default at a site nobody remembered to update.
    """

    return mode == DEV
