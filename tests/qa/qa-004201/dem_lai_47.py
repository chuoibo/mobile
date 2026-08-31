"""Re-count the 47 features against a live server, without matching on names.

Version 1 of this count (`apps/mobile/tests/qa-114244/anh-xa-f-route.json`) looked
for a route whose name carried the feature's *distinguishing concept*: "QR Friend
Add" -> hunt for a route containing "qr". When no such route existed it wrote the
empty set, and the empty set was rendered as column `E` = "no route at all". Three
features (F05, F16, F22) were filed that way while the server answered 200 on
routes serving exactly their data.

This version splits the single collapsed axis into two independent ones:

  du_lieu_routes  -- routes reading/writing the data the feature's SPEC SECTION
                     names. Resource nouns were extracted from the spec text, not
                     from the feature title. One route may serve many features.
  nang_luc_route  -- a route dedicated to the feature's distinguishing capability,
                     or None when the server has none.

A feature "has API" when du_lieu_routes is non-empty. That is a claim about the
server, and it is the claim version 1 got wrong.

Every claimed route is filtered against the LIVE `/openapi.json`, so a route that
is misspelled, imagined, or has been removed silently drops out and pushes the
feature toward `E`. That filter is what makes the negative control below bite.

Run:
    MOBILE_QA_API=http://127.0.0.1:8477 python3 tests/qa/qa-004201/dem_lai_47.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# Same shape the count assigns to a feature, kept as constants so the control
# blocks below assert on the classifier rather than on a re-implementation.
CO_DU = "A"  # data routes exist AND the distinguishing capability has its own route
CO_MOT_PHAN = "P"  # data routes exist, no route for the distinguishing capability
KHONG_CO = "E"  # no live route touches this feature's data


def repo_root() -> Path:
    """Locate the repo root without pinning any one machine's home directory."""

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parents[3]


def live_routes(base_url: str) -> set[str]:
    """Return `METHOD /path` for every operation the running server publishes."""

    with urllib.request.urlopen(f"{base_url}/openapi.json", timeout=15) as resp:
        doc = json.load(resp)
    verbs = ("get", "post", "put", "delete", "patch")
    return {
        f"{verb.upper()} {path}"
        for path, ops in doc["paths"].items()
        for verb in ops
        if verb in verbs
    }


def phan_loai(du_lieu: list[str], nang_luc: str | None, co_that: set[str]) -> str:
    """Classify one feature from routes that the live server actually publishes."""

    con_song = [r for r in du_lieu if r in co_that]
    if not con_song:
        return KHONG_CO
    if nang_luc is not None and nang_luc in co_that:
        return CO_DU
    return CO_MOT_PHAN


# Synthetic features used as the negative control. Their data genuinely has no
# home on this server (the product holds no money and books no travel), so the
# classifier must return E for them. Without this, a count that answered "has
# API" for all 47 would look identical to a correct one.
DOI_CHUNG_AM = {
    "G01": {
        "ten": "[bia] Dat ve may bay",
        "du_lieu_routes": ["GET /flights", "POST /flights/bookings"],
        "nang_luc_route": None,
    },
    "G02": {
        "ten": "[bia] Vi tien trong app",
        "du_lieu_routes": ["GET /wallet", "POST /wallet/topup"],
        "nang_luc_route": None,
    },
    "G03": {
        "ten": "[bia] Goi xe",
        "du_lieu_routes": ["POST /rides", "GET /rides/{ride_id}"],
        "nang_luc_route": None,
    },
}

# Fixed by the task: these three were filed E by version 1 and must not be again.
DOI_CHUNG_DUONG = ("F05", "F16", "F22")


def main() -> int:
    root = repo_root()
    base_url = os.environ.get("MOBILE_QA_API", "http://127.0.0.1:8477").rstrip("/")

    v2 = json.loads(
        (root / "tests/qa/qa-004201/anh-xa-f-route-v2.json").read_text("utf-8")
    )
    v1_path = root / "apps/mobile/tests/qa-114244/anh-xa-f-route.json"
    v1 = json.loads(v1_path.read_text("utf-8")) if v1_path.exists() else {}

    co_that = live_routes(base_url)
    print(f"may chu      : {base_url}")
    print(f"route song   : {len(co_that)} (method x path)")

    features = {k: v for k, v in v2.items() if not k.startswith("_")}
    if len(features) != 47:
        print(f"HONG: mong 47 tinh nang, doc duoc {len(features)}")
        return 2

    # A claimed route that the live server does not publish is a bug in the map,
    # not a feature gap. Report it loudly instead of letting it sink a cell to E.
    ma = sorted(
        {
            r
            for f in features.values()
            for r in f["du_lieu_routes"] + [f["nang_luc_route"]]
            if r and r not in co_that
        }
    )
    if ma:
        print(f"HONG: {len(ma)} route khai trong ban do KHONG co tren may chu: {ma}")
        return 2

    ket = {
        fid: phan_loai(f["du_lieu_routes"], f["nang_luc_route"], co_that)
        for fid, f in features.items()
    }
    dem = {
        k: sum(1 for v in ket.values() if v == k)
        for k in (CO_DU, CO_MOT_PHAN, KHONG_CO)
    }

    print(
        "\n--- BANG 47 (A = du | P = co API cho du lieu, thieu route nang luc | E = khong co API) ---"
    )
    for fid in sorted(features):
        nhan = ket[fid]
        sao = "  <-- doi chung duong" if fid in DOI_CHUNG_DUONG else ""
        print(f"{fid} {nhan}  {features[fid]['ten']}{sao}")
    print(
        f"\nA={dem[CO_DU]}  P={dem[CO_MOT_PHAN]}  E={dem[KHONG_CO]}   (tong {len(features)})"
    )
    print(f"CO API (A+P) = {dem[CO_DU] + dem[CO_MOT_PHAN]}/47")

    loi: list[str] = []

    # --- reproduction: what version 1 said about the same three features -------
    print("\n--- TAI LAP LOI CUA BAN 1 ---")
    for fid in DOI_CHUNG_DUONG:
        cu = v1.get(fid, {}).get("routes", None)
        moi = ket[fid]
        print(
            f"{fid} {features[fid]['ten']}: ban 1 -> {cu!r} (doc thanh E) | "
            f"ban 2 -> {moi} ({len([r for r in features[fid]['du_lieu_routes'] if r in co_that])} route song)"
        )
        if v1 and cu != []:
            loi.append(
                f"{fid}: ban 1 dang le phai la [] de tai lap duoc loi, doc ra {cu!r}"
            )

    # --- positive control -----------------------------------------------------
    print("\n--- DOI CHUNG DUONG (bat buoc) ---")
    for fid in DOI_CHUNG_DUONG:
        ok = ket[fid] in (CO_DU, CO_MOT_PHAN)
        print(f"{fid} -> {ket[fid]}  {'DAT' if ok else 'TRUOT'}")
        if not ok:
            loi.append(f"{fid} van bi xep E: phep dem van hong, dung nop")

    # --- negative control -----------------------------------------------------
    print("\n--- DOI CHUNG AM (phep dem con phan biet duoc khong) ---")
    for gid, g in DOI_CHUNG_AM.items():
        nhan = phan_loai(g["du_lieu_routes"], g["nang_luc_route"], co_that)
        ok = nhan == KHONG_CO
        print(f"{gid} {g['ten']} -> {nhan}  {'DAT' if ok else 'TRUOT'}")
        if not ok:
            loi.append(f"{gid} dang le phai ra E: phep dem khong con phan biet duoc gi")

    print()
    if loi:
        for m in loi:
            print(f"TRUOT: {m}")
        return 1
    print("TAT CA DOI CHUNG DAT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
