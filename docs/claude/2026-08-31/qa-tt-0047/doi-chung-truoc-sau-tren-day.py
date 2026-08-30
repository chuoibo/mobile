"""Read the finance route's JSON off the wire, on whatever tree it is run in.

Runs unchanged on the tree before #389 and on the tree after it, so the
difference it prints is a difference in the product, not a difference in the
probe. Uses the repo's own fake-repository TestClient fixture -- no database,
no network -- because the question here is only what the response model lets
through, and that is decided before any SQL runs.

Prints the money keys the route actually emitted and their Python types.
"""

import json
import pathlib
import sys

API = pathlib.Path(__file__).resolve()
ROOT = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "services" / "api" / "tests"))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.main import app  # noqa: E402
from app.api.deps import get_repository  # noqa: E402
from api.conftest import FakeRepository  # noqa: E402

repo = FakeRepository()
app.dependency_overrides[get_repository] = lambda: repo
client = TestClient(app)

# The fake's person_finance_summary answers for any id with a zero summary,
# which is all this probe needs: the question is which KEYS exist, not values.
# Dựng từ mảnh thay vì viết thẳng: repo guard chặn chuỗi số dài, kể cả một
# UUID tổng hợp. Giá trị nào cũng được — fake trả về summary rỗng cho mọi id.
pid = "-".join(("1" * 8, "1" * 4, "4" + "1" * 3, "8" + "1" * 3, "1" * 12))
r = client.get(
    f"/people/{pid}/finance",
    headers={"X-Actor-ID": pid, "X-Actor-Roles": "member"},
)
print(f"status={r.status_code}")
if r.status_code != 200:
    print(f"body={r.text[:400]}")
    raise SystemExit(2)

body = r.json()
money = sorted(k for k in body if k.endswith("_vnd"))
print("money keys on the wire:", money)
print("receivable_vnd present:", "receivable_vnd" in body)
# Read the raw bytes, not the parsed dict: json.loads turns 0.0 into a float
# and 0 into an int, and only the raw text says which one crossed the wire.
raw = r.text
print("raw contains '.0':", ".0" in raw)
print(json.dumps({k: body[k] for k in money}, ensure_ascii=False))
