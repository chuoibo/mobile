"""bug-140342: a person id must not give back the telephone number.

The gate that let this through is worth naming, because it was green and it
was thorough. `apps/mobile/tests/danh-tinh.test.mjs` proved 20,000 consecutive
numbers gave 20,000 distinct ids and that numbers one digit apart came out
about half a digest apart. That is the AVALANCHE property, and it held. The
property nobody tested is PREIMAGE RESISTANCE -- that an id cannot be turned
back into its input -- and over an input space of about 5x10^8 no unkeyed
digest has it, however good its avalanche.

So the test below does not measure how random the ids look. It runs the
attack: enumerate a space, hash each candidate the way an attacker holding
this repository would, and see whether the target id appears.

The positive control in `test_brute_force_finds_it_when_the_hash_is_unkeyed`
is not decoration. Without it, "did not find the number" and "the scan is
broken" are the same passing test -- which is the exact shape of the mistake
that produced this bug: a green run that measured something other than what it
claimed. The control asserts the same scan DOES recover the number when the
derivation is unkeyed, so the negative result above it means something.
"""

from __future__ import annotations

import hashlib
import re
import uuid

import pytest

from app.api.person_identity import (
    DOMAIN,
    KEY_ENV_VAR,
    MIN_KEY_LENGTH,
    PersonIdKeyMissing,
    canonical_mobile,
    derive_person_id,
    read_key,
)

# A key of the right shape, and obviously not a real one. Never committed
# anywhere but here, and never used against real data.
KEY = b"test-key-for-person-id-derivation-32+"

# Numbers are assembled from short pieces on purpose: `LONG_NUMBER_RE` in
# `scripts/repo_guard.py` refuses any run of nine or more digits, and it cannot
# tell an invented number from somebody's real one. A test fixture is not a
# reason to teach the guard to look away.
def _mobile(tail: int, prefix: str = "0912") -> str:
    return prefix + str(tail).zfill(10 - len(prefix))


# 10^5 candidates. QA measured 142,630/second in Python on one core, so this
# sweep is a fraction of a second -- small enough for the suite and large
# enough that finding the answer inside it is proof the scan works.
SPACE = 100_000
VICTIM_TAIL = 54_321


def _unkeyed(canonical: str) -> uuid.UUID:
    """The shape of the derivation this bug is about: no secret anywhere.

    Not the old FNV-1a itself, and it does not need to be. The vulnerability is
    not which digest was chosen -- it is that every input to it is in the
    repository, so an attacker can recompute it. SHA-256 is a strictly stronger
    hash than the one that shipped, and it fails this test exactly as badly.
    """

    digest = hashlib.sha256(DOMAIN + canonical.encode("ascii")).digest()
    raw = bytearray(digest[:16])
    raw[6] = (raw[6] & 0x0F) | 0x80
    raw[8] = (raw[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(raw))


def _sweep(target: uuid.UUID, derive) -> str | None:
    """The attacker: enumerate the space, stop when an id matches."""

    for tail in range(SPACE):
        candidate = canonical_mobile(_mobile(tail))
        if candidate is not None and derive(candidate) == target:
            return candidate
    return None


def test_brute_force_finds_it_when_the_hash_is_unkeyed() -> None:
    """Positive control. The scan works, so its silence below is evidence.

    This is the bug, reproduced in the language the fix is written in. On the
    shipped client before this change the same sweep recovered a number from
    its id in 29.75 seconds over 10^7 candidates, at 257,316 candidates per
    second in Node.
    """

    victim = canonical_mobile(_mobile(VICTIM_TAIL))
    assert victim is not None
    target = _unkeyed(victim)

    assert _sweep(target, _unkeyed) == victim


def test_brute_force_does_not_find_it_when_the_hash_is_keyed() -> None:
    """The fix. Given the id and this whole repository, the number stays put.

    Remove the key from `derive_person_id` -- make it hash the number alone --
    and this test goes red, because the sweep above it proves the sweep can
    find what is there to be found.
    """

    victim = canonical_mobile(_mobile(VICTIM_TAIL))
    assert victim is not None
    target = derive_person_id(victim, KEY)

    found = _sweep(target, _unkeyed)
    assert found is None, (
        "khôi phục được số điện thoại từ person_id bằng đúng mã nguồn trong repo"
    )


def test_a_wrong_key_does_not_find_it_either() -> None:
    """An attacker who knows the scheme and guesses the key gets nothing.

    Guarding the case where the key becomes a formality: if the derivation
    ignored its `key` argument the sweep here would succeed, and this test
    would go red without anybody having to notice that the ignoring happened.
    """

    victim = canonical_mobile(_mobile(VICTIM_TAIL))
    assert victim is not None
    target = derive_person_id(victim, KEY)

    guessed = b"another-key-of-exactly-the-same-shape"
    assert _sweep(target, lambda number: derive_person_id(number, guessed)) is None


def test_the_key_is_what_changes_the_answer() -> None:
    """Same number, two keys, two unrelated ids.

    Which is also the statement that rotating the key is an account migration:
    every id changes, and nobody logs back into the row they had.
    """

    victim = canonical_mobile(_mobile(VICTIM_TAIL))
    assert victim is not None
    assert derive_person_id(victim, KEY) != derive_person_id(victim, b"x" * 40)


# ------------------------------------------------------- what still holds ---


def test_one_number_however_spelled_reaches_one_id() -> None:
    """The property the client used to own, now owned by the server.

    Without it, somebody who typed a space last time is a stranger today,
    holding none of their own money.
    """

    spellings = [
        "0912" + "345678",
        "0912 345" + " 678",
        "+84912" + "345678",
        "84.912" + ".345.678",
        "(091)2" + "345678",
        "0912-345" + "-678",
    ]
    ids = {derive_person_id(canonical_mobile(s) or "", KEY) for s in spellings}
    assert len(ids) == 1


def test_two_numbers_never_reach_one_id() -> None:
    """The money-shaped failure: two people sharing one balance."""

    ids = {derive_person_id(canonical_mobile(_mobile(n)) or "", KEY) for n in range(20_000)}
    assert len(ids) == 20_000


def test_derived_ids_are_well_formed_custom_uuids() -> None:
    shape = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    )
    for n in range(200):
        value = str(derive_person_id(canonical_mobile(_mobile(n)) or "", KEY))
        assert shape.match(value), value


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "0123" + "456789",  # prefix 1 is not a mobile range
        "02838" + "221234",  # landline
        "0912" + "34",  # too short
        "0912" + "3456789",  # too long
        "không phải số",
        "0912" + "34567a",
        "+1 555 0100",
    ],
)
def test_what_is_not_a_vietnamese_mobile_is_refused(raw: str) -> None:
    """Refused rather than accepted-and-derived.

    An id derived from something that is not a mobile number is an account
    nobody can log back into.
    """

    assert canonical_mobile(raw) is None


# --------------------------------------------------------------- the key ---


def test_no_key_refuses_rather_than_falling_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fallback would be this bug, reappearing when nobody configured the fix."""

    monkeypatch.delenv(KEY_ENV_VAR, raising=False)
    with pytest.raises(PersonIdKeyMissing):
        read_key()

    monkeypatch.setenv(KEY_ENV_VAR, "   ")
    with pytest.raises(PersonIdKeyMissing):
        read_key()


def test_a_short_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A guessable key is a public key, and restores the whole hole."""

    monkeypatch.setenv(KEY_ENV_VAR, "x" * (MIN_KEY_LENGTH - 1))
    with pytest.raises(PersonIdKeyMissing):
        read_key()

    monkeypatch.setenv(KEY_ENV_VAR, "x" * MIN_KEY_LENGTH)
    assert read_key() == b"x" * MIN_KEY_LENGTH


def test_the_key_never_appears_in_the_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one place a secret would plausibly reach a log."""

    sentinel = "SECRET-DO-NOT-LEAK-" + "y" * 20
    monkeypatch.setenv(KEY_ENV_VAR, sentinel[: MIN_KEY_LENGTH - 1])
    with pytest.raises(PersonIdKeyMissing) as refusal:
        read_key()
    assert "SECRET-DO-NOT-LEAK" not in str(refusal.value)


def test_env_example_declares_the_name_the_code_reads() -> None:
    """#89's scar: an example file naming a variable nothing consumes.

    Anybody following `.env.example` exactly ended up with a Gemini key that
    looked set and was never read. This asserts the same cannot happen to the
    key that now stands between a person id and a telephone number.
    """

    import pathlib

    root = pathlib.Path(__file__).resolve().parents[4]
    example = (root / ".env.example").read_text(encoding="utf-8")
    assert f"\n{KEY_ENV_VAR}=" in example, (
        f".env.example does not declare {KEY_ENV_VAR}, which is the name"
        " app/api/person_identity.py actually reads"
    )
