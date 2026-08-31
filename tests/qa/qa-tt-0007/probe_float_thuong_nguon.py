"""QA probe for #497: does its recorder see a float that enters upstream?

NOT collected by the tier on purpose. `scripts/postgres_tier.sh` runs
`pytest ../../tests/qa`, which collects `test_*.py`; this file is named
`probe_*` so it never joins that run. It asserts nothing, so as a tier case it
would be green forever and prove nothing -- which is the shape this probe exists
to expose, not to add.

## What it shows

`test_money_writes_are_integer_postgres.py` (#497) drives its money writes
through `Slice`, which builds `SqlAlchemyApiRepository(session)` and calls
repository methods directly, handing them integer literals written inside the
fixture. `app/api/service.py` is never executed, so a float introduced anywhere
above the repository is invisible to the gate.

The recorder itself is fine. Point it at the real HTTP path and it flags every
offender. Measured on 0feb017 with one mutation at `app/api/service.py:3789`:

    rollups={k: float(v) for k, v in component_rollups(domain_expense).items()},

    tests/postgres              -> 551 passed   (the gate sees nothing)
    this probe                  -> 6 unlawful float binds, all named

The six columns it names are inside the eleven that #497 prints as "driven", so
the printed blind-spot map is narrower than the real one.

Run it:

    scripts/postgres_tier.sh --keep          # prints a throwaway database URL
    cd services/api && MOBILE_TEST_DATABASE_URL='<url>' \
      MOBILE_REQUIRE_POSTGRES_TESTS=1 \
      python3 -m pytest ../../tests/qa/qa-tt-0007/probe_float_thuong_nguon.py -q -s

Without the mutation every binding is a lawful int and the violation count is 0;
that is the negative control, and it is worth running first.
"""

import uuid

import pytest
from sqlalchemy.engine import Engine

# `conftest.py` next to this file puts `services/api` on `sys.path` and
# re-exports `postgres_engine` and `live_client` as fixtures of this directory.
from tests.postgres.test_idempotency_postgres import _actor_headers, _expense_payload
from tests.postgres.test_money_writes_are_integer_postgres import recording

pytestmark = pytest.mark.postgres


def test_probe_float_di_qua_service_co_bi_bat_khong(
    live_client, postgres_engine: Engine
) -> None:
    """Drive confirm over real HTTP and report what #497's recorder sees."""

    context_id = uuid.uuid4()
    live_client.seed_group(context_id)
    headers = _actor_headers(context_id)

    created = live_client.post(
        "/expenses",
        json=_expense_payload() | {"context_id": str(context_id)},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    proposed = created.json()

    with recording(postgres_engine) as recorder:
        confirmed = live_client.post(
            f"/expenses/{proposed['expense_id']}/confirm",
            headers=headers,
            json={
                "proposal": proposed["proposal"],
                "expected_allocations": proposed["allocation"]["allocations"],
                "acknowledge_as_advancer": True,
            },
        )

    print(f"\nconfirm status = {confirmed.status_code}")
    print(f"money binds observed on the HTTP path = {len(recorder.bindings)}")
    for binding in recorder.bindings:
        print(f"    {binding}")
    print(f"UNLAWFUL (not int) = {len(recorder.unlawful())}")
    for binding in recorder.unlawful():
        print(f"    UNLAWFUL: {binding}")
