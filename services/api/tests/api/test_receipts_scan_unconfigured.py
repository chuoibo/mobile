"""A server with no Gemini credential must say so, not blame the photograph.

rd-qa-05 measured this on a stack built by ``make up``: the same image, the
same commit, answered ``422 receipt_unreadable`` in 2.5ms in the container and
``200`` with eight items in 7.06s in a process that had the key. 2.5ms is the
tell -- no network call happened at all, because ``GeminiReceiptReader.read``
raises before it builds a client.

The failure is not that the container lacked the key. It is that the answer
was indistinguishable from a genuinely unreadable photo: same status, same
code, same sentence telling the user to check their image and try again. On a
stage the presenter re-shoots the bill three times before suspecting the
server. A misconfigured server has to be loud, and it has to be loud in a way
the client can branch on -- which means a distinct wire code, not prose.

These tests use the REAL reader on purpose. A fake reader cannot reproduce
this: the bug lives in how the route classifies the real reader's
``RECEIPT_READER_NOT_CONFIGURED``.
"""

from __future__ import annotations

import anyio
import pytest

from app.api.main import create_app
from app.api.routes.receipts import _RECEIPT_UNREADABLE_DETAIL

from .conftest import ASGITestClient
from .helpers import ADVANCER_ID, png_bytes

PNG = png_bytes()
HEADERS = {"X-Actor-ID": str(ADVANCER_ID)}


@pytest.fixture
def unconfigured_client(monkeypatch):
    """A real app whose real reader has no credential to use."""

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    # Both shapes of "no key" a deployment can produce: absent from the
    # environment, and present but empty. Compose interpolation makes the
    # second one the common case, so it must not take a different path.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # No dependency_overrides: this must exercise GeminiReceiptReader itself.
    return ASGITestClient(create_app())


@pytest.fixture
def empty_key_client(monkeypatch, unconfigured_client):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    return unconfigured_client


def scan(client):
    return client.post(
        "/receipts/scan",
        files={"image": ("bill.png", PNG, "image/png")},
        headers=HEADERS,
    )


class TestAMissingKeyIsNotABadPhoto:
    def test_the_code_is_not_the_one_a_bad_photo_gets(self, unconfigured_client):
        """The whole defect in one assertion: same code for two different faults."""
        assert scan(unconfigured_client).json()["code"] != "receipt_unreadable"

    def test_the_code_names_the_server_configuration(self, unconfigured_client):
        assert (
            scan(unconfigured_client).json()["code"] == "receipt_reader_not_configured"
        )

    def test_the_status_is_a_server_fault_not_a_client_one(self, unconfigured_client):
        """4xx tells the caller to fix their request. Nothing they send helps."""
        assert scan(unconfigured_client).status_code == 503

    def test_the_sentence_does_not_tell_the_user_to_retake_the_photo(
        self, unconfigured_client
    ):
        detail = scan(unconfigured_client).json()["detail"]
        assert detail != _RECEIPT_UNREADABLE_DETAIL
        assert "thử lại" not in detail

    def test_the_sentence_says_the_server_is_at_fault(self, unconfigured_client):
        detail = scan(unconfigured_client).json()["detail"]
        assert "máy chủ" in detail.lower()

    def test_an_empty_key_takes_the_same_path_as_a_missing_one(self, empty_key_client):
        """Compose writes '' when the host variable is unset. Same fault."""
        body = scan(empty_key_client).json()
        assert body["code"] == "receipt_reader_not_configured"


class TestTheCredentialStillDoesNotLeak:
    def test_the_variable_value_is_never_echoed(self, monkeypatch):
        """Naming the variable is required. Printing its value is not."""
        sentinel = "AIzaSySENTINELsentinelSENTINELsentinel123"

        async def run_sync_inline(function, *args, **kwargs):
            del kwargs
            return function(*args)

        monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
        monkeypatch.setenv("GEMINI_API_KEY", sentinel)
        # A real key reaches the network and fails there; whatever comes back,
        # it must not carry the credential.
        assert sentinel not in scan(ASGITestClient(create_app())).text
