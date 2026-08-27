"""Turn a Napas BIN into a name a person can act on.

The guest page was rendering "Ngân hàng 970407". That is a routing code, and
nobody in Vietnam knows their bank by it. Somebody reading the page has to pick
the right bank inside their banking app, so the page has to say Techcombank.

Found by running the whole slice against a real database rather than by reading
the template again: every test asserted the account number, and none asserted
that the bank was nameable.

Unknown codes keep the number and label it as a code, rather than inventing a
name. A wrong bank name is worse than a raw code: it sends somebody confidently
into the wrong app, and only the transfer failing tells them.
"""

from __future__ import annotations

__all__ = ["bank_display_name", "BANKS"]

# Napas BINs for the banks a Vietnamese student is most likely to hold.
# Not exhaustive on purpose: an unfamiliar code degrades honestly.
BANKS = {
    "970400": "SaigonBank",
    "970403": "Sacombank",
    "970405": "Agribank",
    "970407": "Techcombank",
    "970409": "BacABank",
    "970412": "PVcomBank",
    "970415": "VietinBank",
    "970416": "ACB",
    "970418": "BIDV",
    "970422": "MB Bank",
    "970423": "TPBank",
    "970425": "ABBANK",
    "970426": "MSB",
    "970427": "VietABank",
    "970429": "SCB",
    "970432": "VPBank",
    "970436": "Vietcombank",
    "970437": "HDBank",
    "970440": "SeABank",
    "970441": "VIB",
    "970443": "SHB",
    "970448": "OCB",
}


def bank_display_name(bank_bin: str) -> str:
    """Name if known, otherwise the code labelled as a code."""
    name = BANKS.get(bank_bin)
    if name:
        return name
    # "Mã ngân hàng" rather than "Ngân hàng": the reader is told this is a code
    # to look up, not a name to go searching for.
    return f"Mã ngân hàng {bank_bin}"
