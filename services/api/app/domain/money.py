"""Share one integer-shape check across đồng amounts and non-money counts.

Python makes ``bool`` a subclass of ``int``, so ``isinstance(True, int)`` is
true and an ordinary integer check would silently turn ``True`` into one đồng.
Both public violation helpers therefore share exactly one spelling of the
integer-shape rule: :func:`_not_an_integer`.
"""

from __future__ import annotations

NOT_INTEGER = "not_integer"
NEGATIVE = "negative"
NON_POSITIVE = "non_positive"
BELOW_MINIMUM = "below_minimum"


def _not_an_integer(value) -> bool:
    """Reject non-integers and bool, which Python would treat as an integer."""
    return isinstance(value, bool) or not isinstance(value, int)


def vnd_violation(
    value, *, allow_negative: bool = False, positive: bool = False
) -> str | None:
    """Return the first violation of an integer-đồng value, if any.

    ``allow_negative`` exists for ``settlement_plan``: it validates signed
    balances whose total must be zero, so negative values are required.
    """
    if _not_an_integer(value):
        return NOT_INTEGER
    if value < 0 and not allow_negative:
        return NEGATIVE
    if positive and value == 0:
        return NON_POSITIVE
    return None


def count_violation(value, *, minimum: int | None = 0) -> str | None:
    """Return the first violation of an integer count, if any.

    A number of people is not an amount of đồng, so a helper named ``vnd_``
    must not validate it. This helper shares only the integer-shape predicate
    :func:`_not_an_integer` with :func:`vnd_violation`.
    """
    if _not_an_integer(value):
        return NOT_INTEGER
    if minimum is not None and value < minimum:
        return BELOW_MINIMUM
    return None
