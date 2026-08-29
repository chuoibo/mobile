"""What a stranger sees when the guest link they were sent does not work.

One answer on the `/g` boundary was still leaving the product's own surface and
going out as machine output: a token that cannot be found answered with the
JSON error envelope. Chat clients truncate long URLs when they forward them, so
the single most likely way to arrive here is a *correct* link that lost its last
few characters -- and the reader got `{"code":"guest_link_not_found"}` in
English. The repo already owns the right wording for a link that stopped
working; only this branch never reached it.

The neighbouring gap on this boundary -- a 500 going out with none of the three
privacy headers -- was closed separately in #167, and its cases live in
`test_guest_privacy_headers.py`.
"""

from __future__ import annotations

import pytest

GUEST_PRIVACY_HEADERS = {
    "cache-control": "no-store",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex, nofollow",
}

# 43 characters, the shape `secrets.token_urlsafe(32)` produces, so the request
# gets past the path validator and is refused for the reason under test rather
# than for being malformed.
UNKNOWN_TOKEN = "z" * 43


def test_unknown_token_answers_with_the_page_and_not_the_json_envelope(client):
    """A truncated link is the common case, and it is not a machine's problem.

    Cutting the last four characters off a working link is exactly what a chat
    client does to a long URL when it forwards it.
    """

    response = client.get(f"/g/{UNKNOWN_TOKEN}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "guest_link_not_found" not in response.text
    assert "Guest link does not exist" not in response.text


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", f"/g/{UNKNOWN_TOKEN}"),
        ("GET", f"/g/{UNKNOWN_TOKEN}/khong-phai-toi"),
        ("POST", f"/g/{UNKNOWN_TOKEN}/khong-phai-toi"),
        ("GET", f"/g/{UNKNOWN_TOKEN}/doi-so-tien"),
    ],
)
def test_every_route_that_can_refuse_an_unknown_token_answers_with_the_page(
    client, method, path
):
    """Two call sites raise this, and both are reachable from a link.

    The code is a literal in `app.api.service` and a constant in
    `app.api.errors`; nothing but this test holds them equal. Driving every
    route that can raise it is what makes a drifted literal go red here
    instead of silently going back to shipping JSON at a stranger.
    """

    response = client.request(
        method, path, **({"data": {}} if method == "POST" else {})
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "guest_link_not_found" not in response.text
    assert "Không mở được link này" in response.text


def test_the_page_for_an_unknown_token_says_what_to_do_next(client):
    """It has to name the likely cause and give one action.

    "Not found" alone leaves the reader believing the money vanished with the
    link, which is the one thing that is never true here (section 8.2).
    """

    body = client.get(f"/g/{UNKNOWN_TOKEN}").text

    assert "Không mở được link này" in body
    assert "cắt" in body, "the truncated-link cause is the reason they are here"
    assert "xin link mới" in body, "one concrete next step, not an apology"
    assert "vẫn còn" in body, "a broken link does not settle a debt"


def test_the_page_for_an_unknown_token_invents_nobody(client):
    """There is no envelope behind this token, so there is no name to print.

    The expired and revoked pages say "message <name> for a new link" because
    they are holding a real record. This branch is not, and a page that fills
    that gap with a placeholder is worse than one that leaves it out.
    """

    body = client.get(f"/g/{UNKNOWN_TOKEN}").text

    assert "None" not in body
    assert UNKNOWN_TOKEN not in body, "the credential must not be echoed back"


def test_the_page_for_an_unknown_token_still_carries_the_privacy_headers(client):
    """Turning a JSON refusal into a page must not drop what #151 installed."""

    response = client.get(f"/g/{UNKNOWN_TOKEN}")

    for header, expected in GUEST_PRIVACY_HEADERS.items():
        assert response.headers.get(header) == expected
