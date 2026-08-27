"""Liveness endpoint.

Added with the Dockerfile: a HEALTHCHECK pointing at a route that does not
exist is worse than no health check, because the container reports unhealthy
forever and the reason looks like an application fault.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))


def test_healthz_is_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_does_not_touch_the_database(client, repository):
    """A liveness probe that fails on a database blip gets a healthy process
    killed, and restarting the API does not fix a database."""
    before = (dict(repository.expenses), dict(repository.confirmed))
    client.get("/healthz")
    assert (dict(repository.expenses), dict(repository.confirmed)) == before
