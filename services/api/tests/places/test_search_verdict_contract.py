"""One verdict vocabulary for the whole product (bug-174904).

Browse and search both put the words AI MATCH on a card, and both decide that
from the same pair: who wrote the sentence, and what that writer concluded. So
both have to ask a model for the *same* three answers.

Two prompts asking for two vocabularies is one of them being the weaker one,
and nobody finds out which until a card on a screen carries a conclusion the
rest of the service does not recognise. The cheapest place to notice is here,
before a model is ever called: the search prompt has to name the closed set the
browse prompt already names, and the grounding gate has to accept exactly that
set and nothing else.
"""

from __future__ import annotations

from app.domain.place_search import VERDICTS as GROUNDED_VERDICTS
from app.places.catalog import PLACES
from app.places.reasons import VERDICTS as BROWSE_VERDICTS
from app.places.search import build_search_prompt

from .nhom_mau import NHOM_MAU


def prompt() -> str:
    return build_search_prompt("quán nướng ngoài trời cho 6 người", PLACES, NHOM_MAU)


def test_the_gate_accepts_exactly_the_vocabulary_the_browse_prompt_asks_for():
    assert set(GROUNDED_VERDICTS) == set(BROWSE_VERDICTS)


def test_the_search_prompt_asks_for_a_verdict_on_every_row():
    text = prompt()
    assert "verdict" in text, (
        "the search prompt never asks for a verdict, so every sentence it gets "
        "back arrives without the conclusion the card needs to be labelled ai"
    )


def test_the_search_prompt_names_every_verdict_the_gate_will_accept():
    """A value the prompt withholds is a value the model can only guess at."""

    text = prompt()
    for verdict in BROWSE_VERDICTS:
        assert f'"{verdict}"' in text, f"the prompt never offers {verdict!r}"


def test_the_search_prompt_still_owes_nothing_to_the_query():
    """The verdict rules are catalogue text, not caller text.

    Pinned here as well as in the byte-swap boundary test because this file is
    where someone will next edit `SEARCH_RULES`, and the temptation while
    editing rules is to make one of them depend on what was asked.
    """

    first = build_search_prompt("cho 6 người ăn nướng ngoài trời", PLACES, NHOM_MAU)
    second = build_search_prompt("XXX", PLACES, NHOM_MAU)
    assert first.replace('"cho 6 người ăn nướng ngoài trời"', '"XXX"') == second
