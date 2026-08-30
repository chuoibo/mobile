"""Probe: does the person-shaped-key denylist deliver its stated property?

PR #286 claims: a model returning a person-shaped key is refused loudly (422)
because "silently ignoring it is a hole that sleeps until someone reads that key".
This measures which shapes are actually refused and which are silently ignored.
"""

import pathlib
import sys

# app/domain/chat_expense.py ships in PR #286. On a tree without that PR this
# probe has nothing to measure, so say so instead of dying on an import error.
sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parents[3] / "services" / "api")
)
try:
    from app.domain.chat_expense import ChatExpenseError, read_chat_expense
except ModuleNotFoundError:
    print("BO QUA: app/domain/chat_expense.py chua co trong cay nay.")
    print(
        "Chay lai tren nhanh cua #286 (backend/rd-be-27-tien-tu-chat-anh-va-ngan-sach)."
    )
    raise SystemExit(0) from None

BASE = {"is_expense": True, "title": "Bun bo", "amount_text": "180k"}

ENGLISH = [
    "paid_by",
    "payer",
    "person_id",
    "shared_by",
    "shared_with",
    "participants",
    "attendees",
    "author_id",
    "advancer",
    "members",
    "recipient",
    "split_with",
    "who_paid",
    "beneficiary",
]
VIETNAMESE = [
    "nguoi_tra",
    "nguoitra",
    "ai_tra",
    "chia_cho",
    "nguoi_chia",
    "thanh_vien",
    "nguoi_ung",
    "ban_be",
    "khach",
    "chu_chi",
    "nguoi_nhan",
    "cung_di",
    "hoi_ban",
    "ai_an",
]
OTHER = [
    "uid",
    "who",
    "by",
    "user_id",
    "account_id",
    "actor",
    "owner",
    "creator",
    "guest",
    "diner",
    "payerId_",
    "名前",
]


def probe(keys, label):
    refused, ignored = [], []
    for k in keys:
        raw = dict(BASE)
        raw[k] = "Ha"
        try:
            out = read_chat_expense(raw)
            ignored.append(k)
            # the load-bearing check: did the smuggled value reach the output?
            assert "Ha" not in str(out), f"LEAK: {k} value reached output {out}"
        except ChatExpenseError as e:
            if e.code == "MODEL_NAMED_A_PERSON":
                refused.append(k)
            else:
                ignored.append(f"{k}({e.code})")
    print(f"\n[{label}] refused {len(refused)}/{len(keys)}")
    print(f"  REFUSED (422): {refused}")
    print(f"  SILENTLY IGNORED: {ignored}")
    return refused, ignored


r1, i1 = probe(ENGLISH, "english person-shaped")
r2, i2 = probe(VIETNAMESE, "vietnamese person-shaped")
r3, i3 = probe(OTHER, "other identity-ish")

print("\n=== KET LUAN ===")
print(f"english  refused {len(r1)}/{len(ENGLISH)}")
print(f"vietnamese refused {len(r2)}/{len(VIETNAMESE)}  <-- san pham tieng Viet")
print(f"other    refused {len(r3)}/{len(OTHER)}")
print("KHONG co ca nao lam gia tri buon lau lot vao output (assert da chay).")
