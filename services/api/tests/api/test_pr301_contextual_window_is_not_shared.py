"""PR #301 -- does the F33 window actually spend only its own budget?

`test_contextual_suggestion_rate_limit.py` answers a neighbouring question and
answers it well: no two doors on `app.state` are the *same object*. That check
is real, and it is blind to the failure that matters just as much.

    application.state.contextual_suggestion_limiter = build_...()   # distinct
    ...
    def get_contextual_suggestion_limiter(request):
        return request.app.state.suggestion_limiter                 # wrong one

Two distinct objects, one of them never consulted, and both routes counting
into a single window. `is not` is green throughout. So is
`test_spending_the_contextual_ceiling_leaves_the_proactive_card_whole`, whose
name promises a burst and whose body is one identity comparison -- it never
spends the ceiling it is named for.

What decides the question is which limiter the *request* reaches, so this file
drives requests and then reads the budgets. Both directions, because the two
are different bugs: spending F33 must leave the other doors whole, and having
spent the other doors must leave F33 open.

The roster of doors is discovered off `app.state` rather than typed out here,
so a door added next month is inside these cases without anyone remembering.
"""

from __future__ import annotations

import uuid

import anyio
import pytest

from app.api import companion_places
from app.api.deps import get_contextual_suggester, get_repository
from app.api.errors import ApiProblem
from app.api.main import create_app
from app.api.search_rate_limit import (
    CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW,
    FixedWindowLimiter,
)

from .conftest import ASGITestClient
from .test_contextual_suggestion_rate_limit import (
    CATALOGUE,
    CONTEXT_ID,
    HEADERS,
    MEMBER_ID,
    NOW,
    CountingContextualSuggester,
    StubRepository,
)


@pytest.fixture
def suggester():
    return CountingContextualSuggester()


@pytest.fixture
def client(monkeypatch, suggester):
    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
    monkeypatch.setattr("app.api.service._now", lambda: NOW)
    monkeypatch.setattr(
        companion_places, "load_place_catalogue", lambda: list(CATALOGUE)
    )
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: StubRepository()
    app.dependency_overrides[get_contextual_suggester] = lambda: suggester
    return ASGITestClient(app)


def _windows(app) -> dict[str, FixedWindowLimiter]:
    """Every actor-keyed window `create_app` built, discovered not listed.

    `CachedReasonWriter` is excluded because it is not keyed on an actor and
    has no budget to spend on one -- `GET /places` has no actor at all. The
    assertion below is what keeps a rename from turning discovery into an
    empty dict and this whole file into a vacuous pass.
    """

    found = {
        name: value
        for name, value in vars(app.state)["_state"].items()
        if isinstance(value, FixedWindowLimiter)
    }
    assert len(found) >= 2, f"discovered {sorted(found)}; expected several windows"
    return found


def _card(client):
    return client.get(f"/contexts/{CONTEXT_ID}/contextual-suggestion", headers=HEADERS)


def _spend(limiter: FixedWindowLimiter, key: uuid.UUID) -> int:
    """Empty one window for one identity. Returns how many calls it took."""

    for _ in range(limiter.limit):
        limiter.check(key)
    return limiter.limit


def _is_open(limiter: FixedWindowLimiter, key: uuid.UUID) -> bool:
    """Whether this identity may still spend here, without spending it twice.

    `check` admits a call when it succeeds, so a probe costs one from the
    budget it is probing. That is fine in both directions below -- the claim is
    "there was room", not "there was exactly N room" -- and doing it any other
    way would mean reaching into `_windows`, which is reading the implementation
    rather than the behaviour.
    """

    try:
        limiter.check(key)
    except ApiProblem as problem:
        assert problem.status_code == 429
        return False
    return True


def test_spending_the_whole_f33_window_leaves_every_other_door_open(client):
    """The direction the PR's identity check is closest to proving.

    Drives the real route to its real ceiling -- no test-installed limiter --
    and then asks every other window whether this same person may still use it.
    A shared window shows up as a door that is suddenly shut for someone who
    never knocked on it.
    """

    codes = [
        _card(client).status_code
        for _ in range(CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW + 1)
    ]

    assert codes == [200] * CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW + [429]

    windows = _windows(client.app)
    contextual = client.app.state.contextual_suggestion_limiter
    shut = [
        name
        for name, limiter in windows.items()
        if limiter is not contextual and not _is_open(limiter, MEMBER_ID)
    ]

    assert not shut, f"F33's burst closed doors it does not own: {shut}"


def test_emptying_every_other_door_leaves_the_f33_card_answering(client, suggester):
    """The direction nothing else covers at all.

    If `get_contextual_suggestion_limiter` resolved to a neighbour's window --
    distinct object, wrong one -- then exhausting that neighbour would refuse
    the F33 card, and every existing case would still be green: they only ever
    spend F33's own budget, where the two are indistinguishable because both
    ceilings are the same number.
    """

    windows = _windows(client.app)
    contextual = client.app.state.contextual_suggestion_limiter
    emptied = [name for name, limiter in windows.items() if limiter is not contextual]
    for name in emptied:
        _spend(windows[name], MEMBER_ID)

    assert emptied, "no neighbouring window to empty"

    response = _card(client)

    assert response.status_code == 200, (
        f"F33 was refused after emptying {emptied}; its window is not its own"
    )
    assert len(suggester.calls) == 1


def test_the_f33_ceiling_is_counted_per_person_across_a_full_window(client):
    """One person's exhausted window must not be another person's.

    Spends the real ceiling as one actor and then reads the card as a second,
    which a global counter -- the other cheap way to "add" a limiter -- refuses.
    """

    for _ in range(CONTEXTUAL_SUGGESTION_LIMIT_PER_WINDOW):
        assert _card(client).status_code == 200
    assert _card(client).status_code == 429

    other = client.get(
        f"/contexts/{CONTEXT_ID}/contextual-suggestion",
        headers={"X-Actor-ID": str(uuid.uuid4()), "X-Actor-Roles": "member"},
    )

    assert other.status_code == 200
