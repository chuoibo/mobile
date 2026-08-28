"""Napas bank identification numbers, turned into something a person can act on.

A BIN is a routing code. It is correct and it is useless to the person holding
the phone: somebody has to pick the right bank inside their banking app, and
"970418" is not a thing that appears in that list. So the API answers with a
name.

The table is deliberately not exhaustive, and the two failure modes are not
symmetric. Refusing an unlisted code would lock out anyone whose bank we simply
have not typed in yet; inventing a name for it would send them confidently into
the wrong app. So an unknown code is accepted, labelled as a code, and the
caller is told it was not recognised so it can warn.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["BankDescription", "describe_bank"]

# Napas BIN -> the short name the bank uses on its own app.
_DIRECTORY: dict[str, str] = {
    "970400": "SaigonBank",
    "970403": "Sacombank",
    "970405": "Agribank",
    "970406": "DongA Bank",
    "970407": "Techcombank",
    "970409": "BacA Bank",
    "970415": "VietinBank",
    "970416": "ACB",
    "970418": "BIDV",
    "970419": "NCB",
    "970422": "MB Bank",
    "970423": "TPBank",
    "970425": "ABBANK",
    "970426": "MSB",
    "970427": "VietABank",
    "970428": "NamA Bank",
    "970429": "SCB",
    "970430": "PGBank",
    "970431": "Eximbank",
    "970432": "VPBank",
    "970436": "Vietcombank",
    "970437": "HDBank",
    "970438": "Baoviet Bank",
    "970440": "SeABank",
    "970441": "VIB",
    "970443": "SHB",
    "970448": "OCB",
    "970449": "LPBank",
    "970452": "KienlongBank",
    "970454": "BVBank",
    "546034": "Cake by VPBank",
    "963388": "Timo",
}


@dataclass(frozen=True, slots=True)
class BankDescription:
    """What to show for a BIN, and whether it was actually recognised.

    `recognised` is kept separate from `name` on purpose. A caller that only
    read `name` would render "Mã ngân hàng 999999" as though it were a bank,
    with no way to tell that nobody vouched for it.
    """

    name: str
    recognised: bool


def describe_bank(bank_bin: str) -> BankDescription:
    name = _DIRECTORY.get(bank_bin)
    if name is None:
        return BankDescription(name=f"Mã ngân hàng {bank_bin}", recognised=False)
    return BankDescription(name=name, recognised=True)
