"""Small persistence queries that preserve the ledger-derived balance boundary."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import BigInteger, Select, cast, func, select
from sqlalchemy.orm import Session

from app.db.models import CollectionObligation, ReceiptConfirmation


@dataclass(frozen=True, slots=True)
class ObligationAmounts:
    """Stored principal plus the receipt-confirmed sum derived from events."""

    obligation_amount_vnd: int
    confirmed_amount_vnd: int

    @property
    def remaining_amount_vnd(self) -> int:
        return max(self.obligation_amount_vnd - self.confirmed_amount_vnd, 0)


def obligation_amounts_statement(obligation_id: uuid.UUID) -> Select[tuple[int, int]]:
    """Build the aggregate query; no cached status or confirmed total is read."""

    return (
        select(
            CollectionObligation.amount_vnd,
            # Cast in SQL, not `int()` at the caller: PostgreSQL sums a `bigint`
            # as `numeric` and psycopg returns `numeric` as `Decimal`, so the
            # `Select[tuple[int, int]]` annotation above was false and Law 1
            # ("số nguyên đồng, kể cả ở giá trị trung gian") was broken before
            # any caller got a chance to convert. The coalesce needs to be
            # inside the cast because it widens to `numeric` too -- with no
            # receipt rows at all the literal `0` still came back as
            # `Decimal('0')`.
            cast(
                func.coalesce(func.sum(ReceiptConfirmation.amount_vnd), 0),
                BigInteger,
            ),
        )
        .outerjoin(
            ReceiptConfirmation,
            ReceiptConfirmation.obligation_id == CollectionObligation.id,
        )
        .where(CollectionObligation.id == obligation_id)
        .group_by(CollectionObligation.id, CollectionObligation.amount_vnd)
    )


def get_obligation_amounts(
    session: Session, obligation_id: uuid.UUID
) -> ObligationAmounts:
    """Return event-derived amounts, or raise when the obligation does not exist."""

    row = session.execute(obligation_amounts_statement(obligation_id)).one_or_none()
    if row is None:
        raise LookupError(f"Collection obligation {obligation_id} does not exist")
    return ObligationAmounts(
        obligation_amount_vnd=row[0],
        confirmed_amount_vnd=row[1],
    )
