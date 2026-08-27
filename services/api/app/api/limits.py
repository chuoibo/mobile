"""How many times a guest may push back, in one place.

These numbers were spread across five files and disagreed with each other: the
repository enforced three while every view defaulted to two, so the page could
tell someone they had used up a quota the server was still honouring, or the
reverse. A number that governs what a person is allowed to do is policy, and
policy does not belong on a persistence class.
"""

from __future__ import annotations

__all__ = ["OBJECTION_LIMIT", "REPORT_LIMIT"]

# Saying "I already sent this" more than three times means the confirmation
# loop is broken, and repeating it will not fix it.
REPORT_LIMIT = 3

# Section 8.6. Enough room to object to several obligations on one link
# without turning the link into a channel for pressure. Asking how a number
# was reached is not an objection and does not spend this.
OBJECTION_LIMIT = 3
