#!/usr/bin/env python3
"""Regenerate the five-row `ground_reel` table, on the real domain function.

The F37 report claims the grounding gate "có thật và bắt được" and prints five
rows to back it. Those rows had no script behind them -- `grep -rn ground_reel`
over the toolkit returned nothing -- so the table was a paragraph, not a
measurement anyone could re-run. This file is the missing half.

It calls `app.domain.reel.ground_reel` directly. No server, no database, no key:
the claim is about a pure function, so measuring it through HTTP would only add
ways for the answer to be about something else.

The row that earns its place is the fourth. `MAX_PICKS` is 6, and a fabricated
identifier sitting at position 7 is one the display cap would drop anyway. If
the unknown-id check ran after the cap, the answer would be served with the
fabrication silently trimmed and the gate would report success. `reel.py` runs
the check over the complete list first, on purpose; this row is what holds that
ordering in place, and it is the one that would go quiet if someone "optimised"
the cap upward.

The fifth row is the whitelist: a model that volunteers its own `image_url`
must not have it echoed. The server's URL is a server-owned fact.

    do-ground-reel.py

Exit 0 when all five rows match, 1 otherwise.
"""

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
# `tests/qa/` is not on the path when a file here is run directly, and the
# domain package lives under services/api.
sys.path.insert(0, str(REPO / "services" / "api"))

from app.domain.reel import ReelError, ground_reel  # noqa: E402

MAY_CHU = "https://may-chu.noi-bo/anh"

KY_UC = [
    {
        "id": f"ky-uc-{i}",
        "image_url": f"{MAY_CHU}/{i}.jpg",
        "caption": f"MOC-DEADBEEF tấm {i}",
        "place_name": "Đồi chè",
        "created_at": "2026-08-31T10:00:00+07:00",
        "reaction_count": i,
        "comment_count": 0,
    }
    # Six, not four: row 4 needs a full cap's worth of REAL picks so the single
    # fabrication can sit at position 7, alone, past the cap. With fewer real
    # memories a cap-first implementation would still trip over a fabrication
    # inside the first six, and the row would pass without testing the ordering
    # it is named for.
    for i in range(1, 7)
]
CO_THAT = [k["id"] for k in KY_UC]
BON = CO_THAT[:4]


def pick(mid, note="Một câu.", **them):
    return {"memory_id": mid, "note": note, **them}


def moi_pick_that():
    return {"title": "Một ngày ở đồi chè", "picks": [pick(m) for m in BON]}


def bia_o_cuoi():
    return {"title": "T", "picks": [pick(m) for m in BON] + [pick("ky-uc-BIA")]}


def bia_o_dau():
    return {"title": "T", "picks": [pick("ky-uc-BIA")] + [pick(m) for m in BON]}


def bia_vuot_cap():
    # Seven picks: SIX REAL ones filling the display cap exactly, then a single
    # fabrication at position 7. An implementation that applied the cap before
    # checking identifiers would trim to six all-real picks and answer ĐẬU --
    # `co_lot_neu_cap_truoc()` below asserts that is really what would happen,
    # so this row cannot quietly stop discriminating.
    return {"title": "T", "picks": [pick(m) for m in CO_THAT] + [pick("ky-uc-BIA")]}


def co_lot_neu_cap_truoc() -> bool:
    """Would a cap-first implementation have accepted row 4's answer?

    If this is False the row proves nothing about ordering, because the
    fabrication is reachable inside the cap and any check order would catch it.
    """
    picks = bia_vuot_cap()["picks"][:6]
    return all(p["memory_id"] in set(CO_THAT) for p in picks)


def model_tu_them_url():
    return {
        "title": "T",
        "picks": [pick(m, image_url="https://ke-tan-cong/lay-cap.png") for m in BON],
    }


def chay(ten, dung_ra):
    """Run one case; return (dat, mo_ta)."""
    try:
        ket = ground_reel(dung_ra(), KY_UC)
    except ReelError as e:
        return f"TỪ CHỐI {e.code}", ket_qua_tu_choi(e)
    return "ĐẬU", ket


def ket_qua_tu_choi(e):
    return {"code": e.code}


# ten, dung_ra, ket cuc mong doi, kiem them
CAC_CA = [
    ("mọi pick thật", moi_pick_that, "ĐẬU", None),
    ("một pick BỊA ở cuối", bia_o_cuoi, "TỪ CHỐI unknown_memory", None),
    ("một pick BỊA ở đầu", bia_o_dau, "TỪ CHỐI unknown_memory", None),
    ("BỊA vượt quá cap 6 pick", bia_vuot_cap, "TỪ CHỐI unknown_memory", None),
    ("model tự thêm image_url", model_tu_them_url, "ĐẬU", "url_may_chu"),
]


def main() -> int:
    hong = []
    print(f"ground_reel — MAX_PICKS=6, {len(CO_THAT)} ký ức thật\n")
    if not co_lot_neu_cap_truoc():
        print("HỎNG: hàng 4 không còn phân biệt được — pick bịa nằm TRONG cap.")
        return 1
    for ten, dung_ra, mong, them in CAC_CA:
        duoc, ket = chay(ten, dung_ra)
        ghi = ""
        loi = []
        if duoc != mong:
            loi.append(f"ra {duoc!r}, mong {mong!r}")
        if duoc == "ĐẬU":
            urls = [p["image_url"] for p in ket["picks"]]
            ghi = f"{len(ket['picks'])} pick, image_url = url của máy chủ"
            if not all(u.startswith(MAY_CHU) for u in urls):
                loi.append(f"image_url KHÔNG phải của máy chủ: {urls}")
            if them == "url_may_chu":
                ghi = "image_url của model bị bỏ, dùng url máy chủ"
                if any("ke-tan-cong" in u for u in urls):
                    loi.append("URL của model LỌT ra wire")
                # The model's own field must not survive anywhere in the pick.
                if any("ke-tan-cong" in str(p) for p in ket["picks"]):
                    loi.append("chuỗi của model còn sót trong pick")
        if loi:
            hong.append((ten, loi))
        print(f"{ten:<32} -> {duoc:<26} {ghi}")

    print()
    if hong:
        for ten, loi in hong:
            print(f"HỎNG {ten}: {'; '.join(loi)}")
        return 1
    print(f"ĐẠT {len(CAC_CA)}/{len(CAC_CA)} hàng.")
    print("Hàng 4 là hàng đáng giá: pick bịa NGOÀI cap vẫn làm chìm cả câu trả lời.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
