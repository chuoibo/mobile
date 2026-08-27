"""Small persistence queries that preserve the ledger-derived balance boundary."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
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
            func.coalesce(func.sum(ReceiptConfirmation.amount_vnd), 0),
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

