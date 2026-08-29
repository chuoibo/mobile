"""Walk the bill money path over real HTTP and check it against the three money laws.

Why this exists as a script and not a pytest case: the repo's bill tests all run
against either the fake repository or a test-owned session, and both of those can
be green while the *deployed* stack refuses differently. This drives the four
routes over the wire against whatever server you point it at, and reads the
ledger with a second connection -- so "the answer came back right" and "nothing
moved in the ledger" are two independent observations, not one.

Four questions, in the order they matter:

  1. Does the allocation sum to exactly the total, including a remainder that
     does not divide evenly by the number of people? (money law 2)
  2. Is an item nobody claimed REFUSED -- or does it quietly become "everyone"?
     The friendly-looking fallback is the one that fabricates an obligation.
  3. Is a bill that read no lines REFUSED -- or does it fall back to an even
     split, dressing a failed read up as an answer?
  4. Do the bill tables stay a DRAFT? Only `expense_versions` may move money
     (invariant 3). A bill row that changes a balance is a blocker.

Usage:
    python3 scripts/qc/probe_duong_tien_bill.py \
        --base-url http://127.0.0.1:8283 \
        --pg-container qa83-postgres-1 \
        --context <ctx-uuid> --participant <uuid> --participant <uuid> --participant <uuid>

Exit code is non-zero if any check fails, so it can be used as a gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

# Tables that can represent money owed. The bill draft tables are deliberately
# NOT here: the whole point is that they must not appear in this set's totals.
LEDGER_TABLES = [
    "expenses",
    "expense_versions",
    "expense_items",
    "expense_item_shares",
    "confirmed_allocations",
    "collection_batches",
    "collection_obligations",
    "collection_envelopes",
    "receipt_confirmations",
    "payment_reports",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8283")
    p.add_argument("--pg-container", default="qa83-postgres-1")
    p.add_argument("--pg-user", default="mobile")
    p.add_argument("--pg-db", default="mobile")
    p.add_argument("--context", required=True)
    p.add_argument(
        "--participant",
        action="append",
        required=True,
        dest="participants",
        help="repeat three times; the first is treated as the actor",
    )
    return p.parse_args()


class Probe:
    def __init__(self, args: argparse.Namespace):
        self.base = args.base_url.rstrip("/")
        self.ctx = args.context
        self.people = args.participants
        self.args = args
        self.results: list[tuple[str, bool, str]] = []

    # ------------------------------------------------------------------ wire
    def call(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            self.base + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Actor-ID": self.people[0],
                "X-Actor-Roles": "member",
                "X-Actor-Contexts": self.ctx,
            },
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw or b"null")
            except ValueError:
                return e.code, raw.decode(errors="replace")[:300]

    # ----------------------------------------------------------------- ledger
    def sql(self, statement: str) -> str:
        return subprocess.run(
            [
                "docker", "exec", self.args.pg_container, "psql",
                "-U", self.args.pg_user, "-d", self.args.pg_db, "-tAF,", "-c", statement,
            ],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def ledger_snapshot(self) -> dict[str, int]:
        """Read the ledger on a SEPARATE connection from the one the API used.

        Reading it back through the API would let a response that was written
        before its transaction committed still look correct.
        """
        query = " union all ".join(
            f"select '{t}' t, count(*) n from {t}" for t in LEDGER_TABLES
        )
        rows = self.sql(query + " order by 1")
        return {
            line.split(",")[0]: int(line.split(",")[1])
            for line in rows.splitlines()
            if line.strip()
        }

    # ------------------------------------------------------------------ check
    def check(self, label: str, ok: bool, detail: str) -> None:
        self.results.append((label, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {label}\n      {detail}")

    @staticmethod
    def item(key: str, name: str, total: int, who: list[str]) -> dict:
        return {
            "item_key": key, "name": name, "quantity": 1,
            "unit_price_vnd": total, "line_total_vnd": total,
            "suggested_participant_ids": who,
        }

    # ------------------------------------------------------------------- runs
    def run(self) -> int:
        people = self.people
        before = self.ledger_snapshot()
        print("so cai truoc:", before, "\n" + "=" * 70)

        # 1 -- a remainder that cannot divide evenly by three.
        odd_total = 100001
        status, bill = self.call("POST", "/bills", {
            "context_id": self.ctx, "printed_total_vnd": odd_total,
            "items_total_vnd": odd_total, "confidence": 91, "needs_review": False,
            "items": [self.item("i1", "Lau chung", odd_total, people)],
        })
        if status != 201:
            self.check("POST /bills tao duoc ban nhap", False, f"status={status} body={bill}")
            return self.report()
        bill_id = bill["id"]
        self.check(
            "POST /bills khong tra confidence ra wire (ADR-0009 qd 4)",
            "confidence" not in bill, f"keys={sorted(bill)}",
        )
        self.call("PUT", f"/bills/{bill_id}/assignments",
                  {"assignments": [{"item_key": "i1", "participant_ids": people}]})
        _, split = self.call("POST", f"/bills/{bill_id}/split", {"for_ledger": False})
        alloc = split["allocation"]["allocations"]
        self.check(
            f"le {odd_total}d chia {len(people)}: sigma == tong, 100%",
            sum(alloc.values()) == odd_total,
            f"sum={sum(alloc.values())} total={odd_total} alloc={alloc}",
        )
        self.check(
            "moi phan la so nguyen dong (luat 1)",
            all(isinstance(v, int) for v in alloc.values()),
            f"types={[type(v).__name__ for v in alloc.values()]}",
        )

        # 2 -- per-dish, uneven: each person eats a different dish.
        amounts = [219000, 148000, 30000]
        total2 = sum(amounts)
        _, bill2 = self.call("POST", "/bills", {
            "context_id": self.ctx, "printed_total_vnd": total2,
            "items_total_vnd": total2, "confidence": 88, "needs_review": False,
            "items": [
                self.item(k, n, a, [p])
                for k, n, a, p in zip("abc", ["Suon", "Ba chi", "Pepsi"], amounts, people)
            ],
        })
        b2 = bill2["id"]
        self.call("PUT", f"/bills/{b2}/assignments", {"assignments": [
            {"item_key": k, "participant_ids": [p]} for k, p in zip("abc", people)
        ]})
        _, sp2 = self.call("POST", f"/bills/{b2}/split", {"for_ledger": False})
        a2 = sp2["allocation"]["allocations"]
        self.check("mon rieng: sigma == tong", sum(a2.values()) == total2,
                   f"sum={sum(a2.values())} alloc={a2}")
        self.check(
            "mon rieng: ai an gi tra dung mon do",
            all(a2.get(p) == amt for p, amt in zip(people, amounts)),
            f"{a2}",
        )

        # 3 -- an item nobody claimed must be refused, not shared with everyone.
        status, bill3 = self.call("POST", "/bills", {
            "context_id": self.ctx, "printed_total_vnd": 50000,
            "items_total_vnd": 50000, "confidence": 95, "needs_review": False,
            "items": [self.item("orphan", "Khong ai nhan", 50000, [])],
        })
        if status == 201:
            st3, body3 = self.call("POST", f"/bills/{bill3['id']}/split", {"for_ledger": False})
            code = body3.get("code") if isinstance(body3, dict) else None
            self.check(
                "mon khong ai nhan bi TU CHOI (khong chia cho tat ca)",
                st3 == 422 and code == "ITEM_HAS_NO_ASSIGNEE",
                f"status={st3} code={code}",
            )
        else:
            self.check("mon khong ai nhan bi TU CHOI ngay o POST /bills",
                       status in (400, 422), f"status={status}")

        # 4 -- a scan that read no lines must be refused, not split evenly.
        status, bill4 = self.call("POST", "/bills", {
            "context_id": self.ctx, "printed_total_vnd": 200000,
            "items_total_vnd": 0, "confidence": 40, "needs_review": True, "items": [],
        })
        if status == 201:
            st4, body4 = self.call("POST", f"/bills/{bill4['id']}/split", {"for_ledger": False})
            code = body4.get("code") if isinstance(body4, dict) else None
            self.check(
                "bill khong ra mon bi TU CHOI (khong lui ve chia deu)",
                st4 == 422 and code == "BILL_HAS_NO_ITEMS",
                f"status={st4} code={code}",
            )
        else:
            self.check("bill khong ra mon bi TU CHOI ngay o POST /bills",
                       status in (400, 422), f"status={status}")

        # 5 -- an AI guess is not a decision, so it must not reach the ledger.
        _, bill5 = self.call("POST", "/bills", {
            "context_id": self.ctx, "printed_total_vnd": 60000,
            "items_total_vnd": 60000, "confidence": 99, "needs_review": False,
            "items": [self.item("s1", "Do AI doan", 60000, [people[0]])],
        })
        st5, body5 = self.call("POST", f"/bills/{bill5['id']}/split",
                               {"for_ledger": True, "paid_by_id": people[0]})
        self.check(
            "goi y AI chua xac nhan KHONG duoc vao so",
            st5 == 422,
            f"status={st5} code={body5.get('code') if isinstance(body5, dict) else None}",
        )

        # 6 -- invariant 3: none of the above may have moved the ledger.
        after = self.ledger_snapshot()
        drift = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        self.check("bang bill la BAN NHAP: so cai khong doi mot hang nao",
                   not drift, f"drift={drift or 'none'}")

        # ...and the counter-check that keeps the line above from passing
        # vacuously: the bill tables DID receive rows.
        counts = self.sql(
            "select (select count(*) from bills)||'/'||(select count(*) from bill_items)"
        )
        self.check("... nhung bill/bill_items THI co ghi (phep do con song)",
                   counts.split("/")[0] not in ("", "0"), f"bills/bill_items = {counts}")
        return self.report()

    def report(self) -> int:
        bad = [r for r in self.results if not r[1]]
        print("=" * 70)
        print(f"{len(self.results) - len(bad)}/{len(self.results)} PASS")
        for label, _, detail in bad:
            print("  FAIL:", label, "|", detail)
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(Probe(parse_args()).run())
