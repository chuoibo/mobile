"""F17 voting probed against the real uvicorn app and a real PostgreSQL database.

The postgres tier in this PR is honest about its own blind spot: its module
docstring says it "uses ``flush``, never ``commit``" because ``postgres_session``
rolls back per test. A transaction that never commits cannot race another
transaction, so no test in the repository can observe what two simultaneous
ballots from the same voter actually do. That is the question this probe exists
to answer, and it answers it over HTTP against a server the probe did not build.

Every count here is read straight from ``vote_ballots`` with a separate psycopg
connection, never from the API response, so a server that lies about what it
wrote cannot make this probe agree with it.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import uuid
from dataclasses import dataclass, field

import httpx
import psycopg

BASE_URL = "http://127.0.0.1:8232"
DB_URL = "postgresql://mobile:mobile-dev-only@localhost:5432/mobile_qa24"

TIMEOUT = httpx.Timeout(30.0)


# --------------------------------------------------------------------------
# result bookkeeping
# --------------------------------------------------------------------------
@dataclass
class Report:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, bool(ok), detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" -- {detail}" if detail else ""), flush=True)

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [c for c in self.checks if not c[1]]


REPORT = Report()


# --------------------------------------------------------------------------
# HTTP helpers -- always through the real server, never through the ORM
# --------------------------------------------------------------------------
def headers(actor: str, roles: str = "member") -> dict[str, str]:
    return {
        "X-Actor-ID": actor,
        "X-Actor-Roles": roles,
        "Content-Type": "application/json",
    }


def call(
    method: str,
    path: str,
    actor: str,
    body: dict | None = None,
    client: httpx.Client | None = None,
    roles: str = "member",
) -> httpx.Response:
    owned = client is None
    client = client or httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
    try:
        return client.request(method, path, headers=headers(actor, roles), json=body)
    finally:
        if owned:
            client.close()


def must(response: httpx.Response, expected: int, what: str) -> dict:
    if response.status_code != expected:
        raise SystemExit(
            f"setup failed: {what} returned {response.status_code}, "
            f"expected {expected}: {response.text[:400]}"
        )
    return response.json() if response.content else {}


# --------------------------------------------------------------------------
# database helpers -- the probe's own eyes, independent of the API
# --------------------------------------------------------------------------
def db_rows(sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def ballot_rows(vote_id: str) -> list[tuple]:
    return db_rows(
        "select voter_id, option_id, created_at, updated_at "
        "from vote_ballots where vote_id = %s order by created_at",
        (vote_id,),
    )


def ballot_count(vote_id: str) -> int:
    return db_rows("select count(*) from vote_ballots where vote_id = %s", (vote_id,))[
        0
    ][0]


def ballot_count_for(vote_id: str, voter_id: str) -> int:
    return db_rows(
        "select count(*) from vote_ballots where vote_id = %s and voter_id = %s",
        (vote_id, voter_id),
    )[0][0]


# --------------------------------------------------------------------------
# fixtures built over real HTTP
# --------------------------------------------------------------------------
def register(name: str) -> str:
    person_id = str(uuid.uuid4())
    response = call("PUT", f"/people/{person_id}", person_id, {"display_name": name})
    if response.status_code not in (200, 201):
        raise SystemExit(
            f"register {name}: HTTP {response.status_code} {response.text[:300]}"
        )
    return person_id


def make_group(owner: str, members: list[str], label: str) -> str:
    created = must(
        call("POST", "/contexts", owner, {"display_name": label}),
        201,
        "create context",
    )
    context_id = created["id"]
    for person in members:
        invite = must(
            call(
                "POST",
                f"/contexts/{context_id}/members",
                owner,
                {"person_id": person},
                roles="group_admin,member",
            ),
            201,
            "invite member",
        )
        membership_id = invite.get("id") or invite.get("membership_id")
        must(
            call("POST", f"/memberships/{membership_id}/accept", person),
            200,
            "accept membership",
        )
    return context_id


def make_vote(context_id: str, creator: str, question: str, labels: list[str]) -> dict:
    return must(
        call(
            "POST",
            f"/contexts/{context_id}/votes",
            creator,
            {
                "question": question,
                "options": [{"label": label, "place_name": label} for label in labels],
            },
        ),
        201,
        "create vote",
    )


# --------------------------------------------------------------------------
# 1. one person, one ballot -- the second is a replacement, not an append
# --------------------------------------------------------------------------
def probe_one_person_one_ballot(context_id: str, people: dict[str, str]) -> None:
    print("\n[1] Mot nguoi mot phieu: bo phieu HAI LAN")
    vote = make_vote(context_id, people["an"], "An gi toi nay?", ["Pizza", "Bun cha"])
    vote_id, options = vote["id"], vote["options"]

    before = ballot_count(vote_id)
    REPORT.check("bang trong truoc khi bo phieu", before == 0, f"rows={before}")

    first = call(
        "POST",
        f"/votes/{vote_id}/ballots",
        people["an"],
        {"option_id": options[0]["id"]},
    )
    REPORT.check("phieu dau 200", first.status_code == 200, f"http={first.status_code}")
    after_first = ballot_count(vote_id)
    REPORT.check("sau phieu dau: 1 hang", after_first == 1, f"rows={after_first}")
    REPORT.check(
        "phieu dau: replaced_previous_ballot = false",
        first.json().get("replaced_previous_ballot") is False,
        json.dumps(first.json().get("replaced_previous_ballot")),
    )

    second = call(
        "POST",
        f"/votes/{vote_id}/ballots",
        people["an"],
        {"option_id": options[1]["id"]},
    )
    REPORT.check(
        "phieu thu hai 200", second.status_code == 200, f"http={second.status_code}"
    )
    after_second = ballot_count(vote_id)
    REPORT.check(
        "sau phieu thu hai: VAN 1 hang (thay the, khong them)",
        after_second == 1,
        f"rows={after_second}",
    )
    REPORT.check(
        "phieu thu hai: replaced_previous_ballot = true",
        second.json().get("replaced_previous_ballot") is True,
        json.dumps(second.json().get("replaced_previous_ballot")),
    )

    rows = ballot_rows(vote_id)
    REPORT.check(
        "hang duy nhat tro sang lua chon MOI",
        len(rows) == 1 and str(rows[0][1]) == options[1]["id"],
        f"option_id trong DB={rows[0][1] if rows else None}, mong doi={options[1]['id']}",
    )
    REPORT.check(
        "created_at giu nguyen, updated_at moi hon (la UPDATE chu khong phai INSERT)",
        len(rows) == 1 and rows[0][3] > rows[0][2],
        f"created={rows[0][2]}, updated={rows[0][3]}" if rows else "khong co hang",
    )

    results = must(call("GET", f"/votes/{vote_id}", people["an"]), 200, "read results")
    REPORT.check(
        "ket qua doc ra dung 1 phieu, nam o lua chon moi",
        results["total_ballots"] == 1
        and results["decided_option_id"] == options[1]["id"],
        f"total={results['total_ballots']}, decided={results['decided_option_id']}",
    )


# --------------------------------------------------------------------------
# 2. changing your mind before the close, refused after it
# --------------------------------------------------------------------------
def probe_change_before_and_after_close(
    context_id: str, people: dict[str, str]
) -> None:
    print("\n[2] Doi phieu TRUOC khi dong duoc, SAU khi dong khong")
    vote = make_vote(
        context_id, people["an"], "Di dau cuoi tuan?", ["Da Lat", "Vung Tau"]
    )
    vote_id, options = vote["id"], vote["options"]

    must(
        call(
            "POST",
            f"/votes/{vote_id}/ballots",
            people["binh"],
            {"option_id": options[0]["id"]},
        ),
        200,
        "first ballot",
    )
    change_open = call(
        "POST",
        f"/votes/{vote_id}/ballots",
        people["binh"],
        {"option_id": options[1]["id"]},
    )
    REPORT.check(
        "truoc khi dong: doi phieu duoc (200)",
        change_open.status_code == 200,
        f"http={change_open.status_code}",
    )

    closed = call("POST", f"/votes/{vote_id}/close", people["an"])
    REPORT.check(
        "dong cuoc binh chon 200",
        closed.status_code == 200,
        f"http={closed.status_code}",
    )
    REPORT.check(
        "sau khi dong: is_closed = true",
        closed.json().get("is_closed") is True,
        json.dumps(closed.json().get("is_closed")),
    )

    rows_before = ballot_count(vote_id)
    change_closed = call(
        "POST",
        f"/votes/{vote_id}/ballots",
        people["binh"],
        {"option_id": options[0]["id"]},
    )
    rows_after = ballot_count(vote_id)
    REPORT.check(
        "sau khi dong: doi phieu bi tu choi 409",
        change_closed.status_code == 409,
        f"http={change_closed.status_code} body={change_closed.text[:160]}",
    )
    REPORT.check(
        "sau khi dong: bo phieu MOI cung bi tu choi",
        call(
            "POST",
            f"/votes/{vote_id}/ballots",
            people["cuong"],
            {"option_id": options[0]["id"]},
        ).status_code
        == 409,
    )
    REPORT.check(
        "lan tu choi khong ghi gi vao bang",
        rows_after == rows_before,
        f"truoc={rows_before}, sau={rows_after}",
    )

    after = must(call("GET", f"/votes/{vote_id}", people["binh"]), 200, "read closed")
    REPORT.check(
        "phieu con nguyen o lua chon da doi sang",
        after["decided_option_id"] == options[1]["id"],
        f"decided={after['decided_option_id']}",
    )


# --------------------------------------------------------------------------
# 3. a tie is displayed as a tie -- the machine does not pick a side
# --------------------------------------------------------------------------
def probe_tie(context_id: str, people: dict[str, str]) -> None:
    print("\n[3] Hoa thi HIEN hoa, may khong chon ho")
    vote = make_vote(context_id, people["an"], "Quan nao?", ["Lau", "Nuong", "Chay"])
    vote_id, options = vote["id"], vote["options"]

    must(
        call(
            "POST",
            f"/votes/{vote_id}/ballots",
            people["an"],
            {"option_id": options[0]["id"]},
        ),
        200,
        "an votes",
    )
    must(
        call(
            "POST",
            f"/votes/{vote_id}/ballots",
            people["binh"],
            {"option_id": options[1]["id"]},
        ),
        200,
        "binh votes",
    )

    tied = must(call("GET", f"/votes/{vote_id}", people["an"]), 200, "read tie")
    REPORT.check(
        "hoa 1-1: is_tie = true", tied["is_tie"] is True, json.dumps(tied["is_tie"])
    )
    REPORT.check(
        "hoa 1-1: decided_option_id = null (khong chon ho)",
        tied["decided_option_id"] is None,
        f"decided={tied['decided_option_id']}",
    )
    REPORT.check(
        "hoa 1-1: leading_option_ids liet ke CA HAI",
        set(tied["leading_option_ids"]) == {options[0]["id"], options[1]["id"]},
        f"leading={tied['leading_option_ids']}",
    )

    closed = must(
        call("POST", f"/votes/{vote_id}/close", people["an"]), 200, "close tie"
    )
    REPORT.check(
        "DONG mot cuoc hoa van doc ra hoa (dong khong pha the hoa)",
        closed["is_tie"] is True and closed["decided_option_id"] is None,
        f"is_tie={closed['is_tie']}, decided={closed['decided_option_id']}",
    )

    reread = must(call("GET", f"/votes/{vote_id}", people["binh"]), 200, "reread tie")
    REPORT.check(
        "doc lai sau khi dong: van hoa",
        reread["is_tie"] is True and reread["decided_option_id"] is None,
        f"is_tie={reread['is_tie']}, decided={reread['decided_option_id']}",
    )

    # three-way tie, on a fresh vote
    vote3 = make_vote(context_id, people["an"], "Ba ben?", ["A", "B", "C"])
    o3 = vote3["options"]
    for person, option in zip(["an", "binh", "cuong"], o3, strict=True):
        must(
            call(
                "POST",
                f"/votes/{vote3['id']}/ballots",
                people[person],
                {"option_id": option["id"]},
            ),
            200,
            "three-way ballot",
        )
    three = must(call("GET", f"/votes/{vote3['id']}", people["an"]), 200, "read 3-way")
    REPORT.check(
        "hoa ba ben: liet ke ca ba, khong chon ai",
        three["is_tie"] is True
        and three["decided_option_id"] is None
        and len(three["leading_option_ids"]) == 3,
        f"leading={len(three['leading_option_ids'])}, decided={three['decided_option_id']}",
    )


# --------------------------------------------------------------------------
# 4. an outsider is refused, told nothing, and writes nothing
# --------------------------------------------------------------------------
def probe_outsider(context_id: str, people: dict[str, str], outsider: str) -> None:
    print("\n[4] Nguoi ngoai nhom: 403, than rong, khong ghi gi")
    vote = make_vote(context_id, people["an"], "Ai di duoc?", ["Thu 7", "Chu nhat"])
    vote_id, options = vote["id"], vote["options"]
    must(
        call(
            "POST",
            f"/votes/{vote_id}/ballots",
            people["an"],
            {"option_id": options[0]["id"]},
        ),
        200,
        "insider ballot",
    )

    before_all = ballot_count(vote_id)
    attempt = call(
        "POST",
        f"/votes/{vote_id}/ballots",
        outsider,
        {"option_id": options[1]["id"]},
    )
    after_all = ballot_count(vote_id)

    REPORT.check(
        "nguoi ngoai bo phieu -> 403",
        attempt.status_code == 403,
        f"http={attempt.status_code} body={attempt.text[:200]}",
    )
    REPORT.check(
        "so ban ghi khong doi sau lan tu choi",
        after_all == before_all,
        f"truoc={before_all}, sau={after_all}",
    )
    REPORT.check(
        "nguoi ngoai khong co hang nao trong bang",
        ballot_count_for(vote_id, outsider) == 0,
    )

    body = attempt.text
    leaks = [
        needle
        for needle in (
            "Pizza",
            "Thu 7",
            "Chu nhat",
            "Ai di duoc",
            people["an"],
            people["binh"],
            options[0]["id"],
            options[1]["id"],
        )
        if needle in body
    ]
    REPORT.check(
        "than 403 khong lo cau hoi / lua chon / id nguoi trong nhom",
        not leaks,
        f"ro ri={leaks}" if leaks else f"body={body[:160]}",
    )

    read = call("GET", f"/votes/{vote_id}", outsider)
    REPORT.check(
        "nguoi ngoai DOC ket qua cung bi chan (403)",
        read.status_code == 403,
        f"http={read.status_code}",
    )
    read_leaks = [n for n in ("Thu 7", "Chu nhat", "Ai di duoc") if n in read.text]
    REPORT.check(
        "than 403 khi doc cung khong lo noi dung",
        not read_leaks,
        f"ro ri={read_leaks}" if read_leaks else "",
    )

    listed = call("GET", f"/contexts/{context_id}/votes", outsider)
    REPORT.check(
        "nguoi ngoai liet ke vote cua nhom -> 403",
        listed.status_code == 403,
        f"http={listed.status_code}",
    )


# --------------------------------------------------------------------------
# 5. the case the whole repository is blind to: two ballots at the same instant
# --------------------------------------------------------------------------
def fire_together(
    requests_: list[tuple[str, str, dict]],
) -> list[httpx.Response | Exception]:
    """Release N HTTP requests from a barrier so they overlap in the server."""
    barrier = threading.Barrier(len(requests_))
    results: list[httpx.Response | Exception | None] = [None] * len(requests_)

    def worker(index: int, actor: str, path: str, body: dict) -> None:
        client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
        try:
            barrier.wait()
            results[index] = client.post(path, headers=headers(actor), json=body)
        except Exception as exc:  # noqa: BLE001 - the probe reports, it does not fix
            results[index] = exc
        finally:
            client.close()

    threads = [
        threading.Thread(target=worker, args=(i, a, p, b))
        for i, (a, p, b) in enumerate(requests_)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results  # type: ignore[return-value]


def probe_concurrent_same_voter(
    context_id: str,
    people: dict[str, str],
    rounds: int,
    fanout: int = 2,
    warm_first: bool = False,
) -> None:
    """Fire ``fanout`` ballots from ONE voter at one instant, ``rounds`` times.

    ``warm_first`` decides which race is under test. False means the voter has
    no row yet, so every request races to INSERT and the unique constraint is
    the only thing standing between them -- that is the case where a
    ``SELECT ... FOR UPDATE`` on the ballot row locks nothing, because the row
    does not exist yet. True means the row already exists, so the requests race
    to UPDATE the same row instead.
    """
    label = (
        "UPDATE vs UPDATE (da co phieu)"
        if warm_first
        else "INSERT vs INSERT (chua co phieu)"
    )
    print(
        f"\n[5] Ca DONG THOI: {fanout} phieu cung luc, mot nguoi, x{rounds} vong -- {label}"
    )
    duplicate_rows = 0
    server_errors: list[str] = []
    non_200: list[str] = []
    reread_failures: list[str] = []
    both_ok = 0

    for round_no in range(rounds):
        vote = make_vote(
            context_id, people["an"], f"Dong thoi vong {round_no}", ["X", "Y"]
        )
        vote_id, options = vote["id"], vote["options"]
        voter = people["binh"]

        if warm_first:
            must(
                call(
                    "POST",
                    f"/votes/{vote_id}/ballots",
                    voter,
                    {"option_id": options[0]["id"]},
                ),
                200,
                "warm-up ballot",
            )

        responses = fire_together(
            [
                (
                    voter,
                    f"/votes/{vote_id}/ballots",
                    {"option_id": options[i % len(options)]["id"]},
                )
                for i in range(fanout)
            ]
        )

        rows = ballot_count_for(vote_id, voter)
        if rows != 1:
            duplicate_rows += 1
            print(f"    vong {round_no}: {rows} hang cho MOT nguoi", flush=True)

        codes = []
        for response in responses:
            if isinstance(response, Exception):
                server_errors.append(
                    f"vong {round_no}: {type(response).__name__} {response}"
                )
                codes.append("exc")
                continue
            codes.append(response.status_code)
            if response.status_code >= 500:
                server_errors.append(
                    f"vong {round_no}: HTTP {response.status_code} {response.text[:200]}"
                )
            elif response.status_code != 200:
                non_200.append(
                    f"vong {round_no}: HTTP {response.status_code} {response.text[:200]}"
                )
        if codes == [200] * fanout:
            both_ok += 1

        reread = call("GET", f"/votes/{vote_id}", voter)
        if reread.status_code != 200:
            reread_failures.append(f"vong {round_no}: HTTP {reread.status_code}")
        else:
            payload = reread.json()
            chosen = {options[0]["id"], options[1]["id"]}
            if (
                payload["total_ballots"] != 1
                or payload["decided_option_id"] not in chosen
            ):
                reread_failures.append(
                    f"vong {round_no}: total={payload['total_ballots']} "
                    f"decided={payload['decided_option_id']}"
                )

    REPORT.check(
        f"dung MOT hang thang o ca {rounds} vong",
        duplicate_rows == 0,
        f"so vong sai so hang={duplicate_rows}",
    )
    REPORT.check(
        "khong lan nao 500 (khong co DUPLICATE_BALLOT lot ra ngoai)",
        not server_errors,
        "; ".join(server_errors[:3]) if server_errors else "0 loi 5xx",
    )
    REPORT.check(
        "khong lan nao tra ma la ngoai 200",
        not non_200,
        "; ".join(non_200[:3]) if non_200 else "moi request deu 200",
    )
    REPORT.check(
        "doc ket qua sau do luon 200 va dung 1 phieu",
        not reread_failures,
        "; ".join(reread_failures[:3]) if reread_failures else "moi lan doc deu dung",
    )
    print(f"    (moi request deu 200 o {both_ok}/{rounds} vong)")


def probe_concurrent_different_voters(context_id: str, people: dict[str, str]) -> None:
    print("\n[5b] Dong thoi: BA nguoi KHAC NHAU bo phieu cung luc")
    vote = make_vote(context_id, people["an"], "Ba nguoi cung luc", ["P", "Q"])
    vote_id, options = vote["id"], vote["options"]

    responses = fire_together(
        [
            (
                people["an"],
                f"/votes/{vote_id}/ballots",
                {"option_id": options[0]["id"]},
            ),
            (
                people["binh"],
                f"/votes/{vote_id}/ballots",
                {"option_id": options[0]["id"]},
            ),
            (
                people["cuong"],
                f"/votes/{vote_id}/ballots",
                {"option_id": options[1]["id"]},
            ),
        ]
    )
    codes = [
        r.status_code if isinstance(r, httpx.Response) else "exc" for r in responses
    ]
    REPORT.check(
        "ba nguoi khac nhau: ca ba deu 200", codes == [200, 200, 200], f"codes={codes}"
    )
    rows = ballot_count(vote_id)
    REPORT.check(
        "ba nguoi khac nhau: DU ba hang, khong mat phieu ai", rows == 3, f"rows={rows}"
    )
    tally = must(call("GET", f"/votes/{vote_id}", people["an"]), 200, "read 3 voters")
    REPORT.check(
        "dem lai tu so: 2-1, khong hoa",
        tally["total_ballots"] == 3
        and tally["is_tie"] is False
        and tally["decided_option_id"] == options[0]["id"],
        f"total={tally['total_ballots']}, tie={tally['is_tie']}",
    )


def probe_concurrent_ballot_and_close(context_id: str, people: dict[str, str]) -> None:
    print("\n[5c] Dong thoi: bo phieu VA dong cuoc binh chon cung luc")
    inconsistent: list[str] = []
    crashes: list[str] = []
    for round_no in range(10):
        vote = make_vote(context_id, people["an"], f"Dong vs bo {round_no}", ["M", "N"])
        vote_id, options = vote["id"], vote["options"]
        responses = fire_together(
            [
                (
                    people["binh"],
                    f"/votes/{vote_id}/ballots",
                    {"option_id": options[0]["id"]},
                ),
                (people["an"], f"/votes/{vote_id}/close", {}),
            ]
        )
        ballot_response, close_response = responses
        for response in responses:
            if isinstance(response, Exception) or response.status_code >= 500:
                crashes.append(f"vong {round_no}: {response}")

        rows = ballot_count(vote_id)
        if isinstance(ballot_response, httpx.Response):
            # A 200 must mean the row landed; a 409 must mean it did not.
            if ballot_response.status_code == 200 and rows != 1:
                inconsistent.append(f"vong {round_no}: 200 nhung {rows} hang")
            if ballot_response.status_code == 409 and rows != 0:
                inconsistent.append(f"vong {round_no}: 409 nhung {rows} hang")
        if (
            isinstance(close_response, httpx.Response)
            and close_response.status_code != 200
        ):
            inconsistent.append(
                f"vong {round_no}: close HTTP {close_response.status_code}"
            )

    REPORT.check(
        "bo phieu vs dong: khong lan nao 5xx", not crashes, "; ".join(crashes[:3])
    )
    REPORT.check(
        "bo phieu vs dong: ma tra ve luon khop voi cai da ghi",
        not inconsistent,
        "; ".join(inconsistent[:3]) if inconsistent else "10/10 vong khop",
    )


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=30)
    parser.add_argument("--only", default="", help="chi chay mot probe: 1..5d")
    parser.add_argument("--fanout", type=int, default=2)
    args = parser.parse_args()

    health = httpx.get(f"{BASE_URL}/healthz", timeout=TIMEOUT)
    if health.status_code != 200:
        raise SystemExit(
            f"khong co server tai {BASE_URL} (healthz={health.status_code})"
        )

    people = {name: register(name) for name in ("an", "binh", "cuong")}
    outsider = register("nguoi ngoai")
    context_id = make_group(
        people["an"], [people["binh"], people["cuong"]], "Nhom QA24"
    )
    print(f"nhom={context_id}  nguoi={ {k: v[:8] for k, v in people.items()} }")

    only = args.only
    if not only or only == "1":
        probe_one_person_one_ballot(context_id, people)
    if not only or only == "2":
        probe_change_before_and_after_close(context_id, people)
    if not only or only == "3":
        probe_tie(context_id, people)
    if not only or only == "4":
        probe_outsider(context_id, people, outsider)
    if not only or only == "5":
        probe_concurrent_same_voter(context_id, people, args.rounds, args.fanout)
    if not only or only == "5d":
        probe_concurrent_same_voter(
            context_id, people, args.rounds, args.fanout, warm_first=True
        )
    if not only or only == "5b":
        probe_concurrent_different_voters(context_id, people)
    if not only or only == "5c":
        probe_concurrent_ballot_and_close(context_id, people)

    total = len(REPORT.checks)
    bad = REPORT.failed
    print(f"\n=== {total - len(bad)}/{total} phep kiem DAT ===")
    for name, _, detail in bad:
        print(f"  FAIL: {name} -- {detail}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
