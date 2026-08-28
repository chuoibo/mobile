"""Export golden allocator vectors as fixtures the mobile app can replay.

Why this script exists at all: the app once carried its own split, written in
TypeScript, in the same file whose docstring said "Nothing here computes money".
That was a second allocator implementation and it divided with `/`, producing
float intermediates -- both forbidden. A demo that shows a number it computed
itself is a demo that can disagree with the server about money.

So the fake stops computing and starts replaying. Every fixture below is an
answer the real Python allocator produced for a vector that was computed by
hand first, which makes this file a projection of the existing oracle rather
than a second source of truth. Regenerate it, never hand-edit it:

    cd services/api && python3 tools/build_mobile_fixtures.py

Only vectors that are a plain even split survive the filter -- items,
surcharges and discounts have no screen in the app yet, and a fixture the UI
cannot render is a fixture nobody checks.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
API = HERE.parent
sys.path.insert(0, str(API))

GOLDEN = API / "tests" / "domain" / "golden"
# Emitted as TypeScript, not JSON: Node's ESM loader demands an import
# attribute for JSON, and Metro and tsc disagree about whether that
# attribute is allowed. A .ts module is plainly readable by all three.
OUT = API.parent.parent / "apps" / "mobile" / "src" / "fixtures" / "proposals.ts"

# The corpus identifies people by single letters. The app has to show something
# a person would recognise, so map them to obviously-synthetic Vietnamese names.
# `z` exists because one vector puts the advancer OUTSIDE the participant set.
NAMES = {
    "a": "Nam",
    "b": "Hà",
    "c": "Quyên",
    "d": "Tuấn",
    "e": "Linh",
    "z": "Người ngoài nhóm",
    "á": "Ánh",
    "aa": "An",
}

OCCASIONS = {
    3: "bữa lẩu tối thứ bảy",
    2: "cà phê sáng chủ nhật",
    4: "tiền xe về Vũng Tàu",
    5: "thuê nhà nghỉ hai đêm",
}


def load_vectors() -> list[dict]:
    cases = []
    for path in sorted(GOLDEN.glob("*.json")):
        cases.extend(json.loads(path.read_text(encoding="utf-8")))
    return cases


def is_plain_even_split(case: dict) -> bool:
    supplied = case["input"]
    expected = case.get("expect", {})
    return (
        "allocations" in expected
        and not supplied.get("items")
        and not supplied.get("surcharges")
        and not supplied.get("discounts")
    )


def to_fixture(case: dict) -> dict:
    supplied = case["input"]
    expected = case["expect"]
    participants = [
        {"id": pid, "name": NAMES.get(pid, pid.upper())} for pid in supplied["participants"]
    ]
    return {
        "id": case["id"],
        "note": case["note"],
        "occasion": OCCASIONS.get(len(participants), "khoản chi chung"),
        "totalVnd": supplied["total_vnd"],
        "advancerId": supplied.get("advancer_id"),
        "participants": participants,
        "allocations": expected["allocations"],
        "roundingGainers": expected.get("rounding_gainers", []),
    }


CORPUS = API / "tests" / "skills" / "corpus" / "doc-luong-nhom.json"
THREAD_OUT = API.parent.parent / "apps" / "mobile" / "src" / "fixtures" / "threads.ts"

# Which hand-written cases the demo shows. Chosen to cover the three shapes a
# person needs to recognise: a clean read, a read that has to ask before it can
# proceed, and money mentioned in a way that must NOT become an expense.
DEMO_CASES = ("01-ro-rang", "11-khong-du-chac-chan", "04-noi-dua-khong-phai-khoan-chi")


def build_threads() -> list[dict]:
    """Export corpus cases as thread + extraction pairs for the proposal card.

    The corpus is the oracle: it was written by hand, before any code, and its
    `expected` block is what a correct extractor would produce. Exporting from
    it means the demo cannot drift into showing something the contract never
    promised.
    """
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases", [])
    wanted = {case["case_id"]: case for case in cases}

    threads = []
    for case_id in DEMO_CASES:
        case = wanted.get(case_id)
        if case is None:
            raise SystemExit(f"{case_id} is not in the corpus any more")
        expected = case.get("expected", {})
        threads.append(
            {
                "id": case_id,
                "note": case.get("vi_sao", ""),
                "messages": case["messages"],
                "extraction": {
                    "expenses": [
                        {
                            "totalVnd": item["total_vnd"],
                            "paidBy": item["paid_by"],
                            "label": item["label"],
                            "sourceMessageIds": item["source_message_ids"],
                        }
                        for item in expected.get("expenses", [])
                    ],
                    "questions": list(expected.get("must_ask", [])),
                },
            }
        )
    return threads


def write_threads(threads: list[dict]) -> None:
    for thread in threads:
        known = {message["id"] for message in thread["messages"]}
        for expense in thread["extraction"]["expenses"]:
            missing = [i for i in expense["sourceMessageIds"] if i not in known]
            if missing:
                raise SystemExit(
                    f"{thread['id']}: expense cites {missing}, not in the thread"
                )
    body = json.dumps(threads, ensure_ascii=False, indent=2)
    THREAD_OUT.parent.mkdir(parents=True, exist_ok=True)
    THREAD_OUT.write_text(
        "/* GENERATED by services/api/tools/build_mobile_fixtures.py -- do not edit.\n"
        " *\n"
        " * Hand-written corpus cases, exported so the proposal card demonstrates\n"
        " * what the contract actually promises rather than something invented for\n"
        " * the demo. Every cited message id is checked to exist before writing.\n"
        " */\n"
        "import type { Extraction, ThreadMessage } from \"../extraction\";\n\n"
        "export type DemoThread = {\n"
        "  id: string;\n"
        "  note: string;\n"
        "  messages: ThreadMessage[];\n"
        "  extraction: Extraction;\n"
        "};\n\n"
        f"export const DEMO_THREADS: DemoThread[] = {body};\n",
        encoding="utf-8",
    )
    print(f"wrote {len(threads)} threads to {THREAD_OUT.relative_to(API.parent.parent)}")


def main() -> None:
    fixtures = [to_fixture(case) for case in load_vectors() if is_plain_even_split(case)]

    # A fixture whose parts do not add up would be worse than no fixture: it
    # would put a wrong number on screen with the authority of the corpus.
    for fixture in fixtures:
        total = sum(fixture["allocations"].values())
        if total != fixture["totalVnd"]:
            raise SystemExit(
                f"{fixture['id']}: allocations sum to {total}, expected {fixture['totalVnd']}"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(fixtures, ensure_ascii=False, indent=2)
    OUT.write_text(
        "/* GENERATED by services/api/tools/build_mobile_fixtures.py -- do not edit.\n"
        " *\n"
        " * Every answer here came from the real Python allocator running a golden\n"
        " * vector that was computed by hand first. The app replays these instead of\n"
        " * splitting anything itself.\n"
        " */\n"
        "import type { Fixture } from \"../api\";\n\n"
        f"export const PROPOSAL_FIXTURES: Fixture[] = {body};\n",
        encoding="utf-8",
    )
    print(f"wrote {len(fixtures)} fixtures to {OUT.relative_to(API.parent.parent)}")
    write_threads(build_threads())


if __name__ == "__main__":
    main()
