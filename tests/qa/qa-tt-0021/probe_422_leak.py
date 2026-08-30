"""QA probe (qa-tt-0021): does a 422 read back the sentence a person typed?

Runs the SAME violation -- private free text reaching a validation error --
written in six different shapes. PR #283 measured exactly one of them (a
5800-character comment body) and fixed it with one handler in `create_app`.
A handler is only as wide as the shapes it was tested against, so this probe
writes the violation the ways the PR did not.

Run from `services/api/` in any worktree:

    python3 ../../tests/qa/qa-tt-0021/probe_422_leak.py

Prints one line per shape: LEAK / clean. Exit code is the number of leaks, so
the same file is a red/green gate on both the before-tree and the after-tree.
"""

from __future__ import annotations

import json
import sys
import uuid

import anyio
import httpx

sys.path.insert(0, ".")

from app.api.deps import get_repository  # noqa: E402
from app.api.main import create_app  # noqa: E402

# Stands in for a private sentence somebody typed into a group chat. Distinctive
# enough that finding it anywhere in a response body is unambiguous.
CANARY = "toi-vua-chia-tay-ban-gai-dung-ke-cho-ai-biet-nhe"

CONTEXT_ID = uuid.uuid4()
MEMORY_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()

HEADERS = {"X-Actor-ID": str(ACTOR_ID)}


class _NullRepository:
    """Every attribute answers, nothing is stored.

    The probe never reaches a handler: a 422 is decided by the validation layer
    before the route body runs. So the repository only has to exist.
    """

    def __getattr__(self, name):
        def call(*args, **kwargs):
            del args, kwargs
            return None

        return call


def _client():
    app = create_app()
    app.dependency_overrides[get_repository] = _NullRepository
    return app


def _request(app, method, path, *, content=None, json_body=None, headers=None):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(
                method,
                path,
                content=content,
                json=json_body,
                headers={**HEADERS, **(headers or {})},
            )

    return anyio.run(send)


MESSAGES = f"/contexts/{CONTEXT_ID}/messages"
MEMORIES = f"/contexts/{CONTEXT_ID}/memories"
COMMENTS = f"/contexts/{CONTEXT_ID}/memories/{MEMORY_ID}/comments"


def shapes():
    """Each entry: (label, callable(app) -> response).

    Ordered from the shape the PR measured to the shapes it did not.
    """

    long_text = CANARY + " " + ("x" * 6000)

    return [
        (
            "1. messages.body over max_length=4000 (the pre-existing shape)",
            lambda app: _request(
                app, "POST", MESSAGES, json_body={"kind": "text", "body": long_text}
            ),
        ),
        (
            "2. messages.body sent as an OBJECT holding the text",
            lambda app: _request(
                app,
                "POST",
                MESSAGES,
                json_body={"kind": "text", "body": {"typed": CANARY}},
            ),
        ),
        (
            "3. messages.body sent as a LIST holding the text",
            lambda app: _request(
                app, "POST", MESSAGES, json_body={"kind": "text", "body": [CANARY]}
            ),
        ),
        (
            "4. extra=forbid, the text is the FIELD NAME (lands in `loc`)",
            lambda app: _request(
                app,
                "POST",
                MESSAGES,
                json_body={"kind": "text", "body": "hi", CANARY: 1},
            ),
        ),
        (
            "5. malformed JSON carrying the text",
            lambda app: _request(
                app,
                "POST",
                MESSAGES,
                content=('{"kind": "text", "body": "' + CANARY + '",,}').encode(),
                headers={"content-type": "application/json"},
            ),
        ),
        (
            "6. memories.caption over max_length=2000 (a different route)",
            lambda app: _request(
                app,
                "POST",
                MEMORIES,
                json_body={
                    "place_id": "p1",
                    "caption": CANARY + " " + ("y" * 3000),
                },
            ),
        ),
        (
            "7. comments.body over max_length (the shape the PR measured)",
            lambda app: _request(
                app, "POST", COMMENTS, json_body={"body": CANARY + " " + ("z" * 6000)}
            ),
        ),
    ]


def main() -> int:
    app = _client()
    leaks = 0
    print(f"canary = {CANARY!r}\n")
    for label, run in shapes():
        try:
            response = run(app)
        except Exception as exc:  # noqa: BLE001 - a crash is a result, not a stop
            print(f"  ERROR  {label}\n         {type(exc).__name__}: {exc}")
            continue
        text = response.text
        leaked = CANARY in text
        if leaked:
            leaks += 1
        # Where in the payload did it land? Names the field to fix.
        where = []
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                for error in json.loads(text).get("detail", []):
                    if not isinstance(error, dict):
                        continue
                    for key, value in error.items():
                        if CANARY in json.dumps(value, default=str):
                            where.append(key)
            except (ValueError, AttributeError):
                pass
        verdict = "LEAK" if leaked else "clean"
        detail = f"  via {sorted(set(where))}" if where else ""
        print(f"  {verdict:5}  [{response.status_code}] {label}{detail}")
    print(f"\n{leaks} shape(s) read the typed sentence back.")
    return leaks


if __name__ == "__main__":
    raise SystemExit(main())
