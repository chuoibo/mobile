"""The switch, and which way it points when nobody sets it.

The default is the whole point of this file. A deployment that forgets the
variable has to land on the strict adapter, because the failure being guarded
against is a host that quietly kept trusting a header nobody authenticated --
and that host looks exactly like a healthy one until somebody sends a header.

These cases build their own environment mapping instead of reading the
process's, so the suite-wide `MOBILE_AUTH_MODE=dev` in `tests/conftest.py`
cannot make the product's default look like whatever the suite needed.
"""

from __future__ import annotations

import pytest

from app.api.auth_mode import (
    AUTH_MODE_ENV_VAR,
    DEV,
    PROD,
    AuthModeInvalid,
    resolve_auth_mode,
    trusts_actor_headers,
)
from app.api.main import create_app


class TestTheDefault:
    def test_an_absent_variable_is_prod(self):
        assert resolve_auth_mode({}) == PROD

    def test_an_empty_variable_is_prod(self):
        assert resolve_auth_mode({AUTH_MODE_ENV_VAR: ""}) == PROD
        assert resolve_auth_mode({AUTH_MODE_ENV_VAR: "   "}) == PROD

    def test_an_application_built_without_an_environment_is_prod(self, monkeypatch):
        # The suite exports `dev`; the product's default is what a host with
        # nothing set gets, so the variable is removed for this one case.
        monkeypatch.delenv(AUTH_MODE_ENV_VAR, raising=False)
        assert create_app().state.auth_mode == PROD


class TestOptingOut:
    def test_dev_must_be_asked_for(self):
        assert resolve_auth_mode({AUTH_MODE_ENV_VAR: DEV}) == DEV
        assert create_app(auth_mode=DEV).state.auth_mode == DEV

    def test_case_and_whitespace_are_forgiven(self):
        assert resolve_auth_mode({AUTH_MODE_ENV_VAR: " Dev "}) == DEV
        assert resolve_auth_mode({AUTH_MODE_ENV_VAR: "PROD"}) == PROD


class TestRefusingToGuess:
    def test_an_unknown_value_is_a_startup_error(self):
        with pytest.raises(AuthModeInvalid) as raised:
            resolve_auth_mode({AUTH_MODE_ENV_VAR: "prd"})
        message = str(raised.value)
        # Names the variable and both accepted values, so the operator can fix
        # it from the log line alone.
        assert AUTH_MODE_ENV_VAR in message
        assert PROD in message
        assert DEV in message

    def test_an_unknown_value_does_not_silently_become_dev(self):
        # The dangerous direction. A typo must not open the door.
        for typo in ("develop", "development", "debug", "0", "false"):
            with pytest.raises(AuthModeInvalid):
                resolve_auth_mode({AUTH_MODE_ENV_VAR: typo})

    def test_an_application_refuses_an_unknown_mode(self):
        with pytest.raises(AuthModeInvalid):
            create_app(auth_mode="staging")


class TestWhoTrustsHeaders:
    def test_only_dev_does(self):
        assert trusts_actor_headers(DEV) is True
        assert trusts_actor_headers(PROD) is False

    def test_an_unrecognised_mode_does_not(self):
        # If a third mode is ever added, it starts out untrusted rather than
        # inheriting the header adapter at a call site nobody updated.
        assert trusts_actor_headers("staging") is False
