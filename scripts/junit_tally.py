#!/usr/bin/env python3
"""Count what a pytest run actually did, from its JUnit report.

Extracted from ``scripts/gemini_tier.sh`` so it can be called with a report
this repository did not generate -- which is the only way to test the one
distinction it exists to make without a network, a key and three minutes.

## The distinction

``pytest`` exits 0 for a run in which every case skipped, so the exit code
cannot answer "did this prove anything". The ``skipped`` attribute on
``<testsuite>`` cannot either, and the reason is the bug this file was pulled
out of ``gemini_tier.sh`` to fix: pytest records an expected failure as
``<skipped type="pytest.xfail">``, so that attribute counts xfails as skips.
Reading it turned the live-AI stage red on its own first real run, over
``test_a_place_row_cannot_give_the_model_orders`` -- a known defect that has an
owner, a reproduction and a deliberate mark. A gate that fires on correct
behaviour gets switched off, and a switched-off gate is not there on the day it
would have been right.

So:

    pytest.xfail   recorded intent -- somebody wrote down that this fails, why,
                   and who owns it. Not a hole. Counted, reported, not fatal.
    pytest.skip    a case that silently did not run. This is the hole. The
                   caller decides what to do about it; this file names them.

## Output

One line of counts, then one ``SKIP`` line per real skip::

    <ran> <skipped> <xfailed> <failures> <errors>
    SKIP <classname>::<name> -- <first line of the reason>

Callers parse the first line and show the rest. Exit 0 when the report was
read, 1 when it could not be -- an unreadable report is not an empty one, and
answering "0 skips" to a question that was never asked is the shape of every
false green in this repository.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET


def tally(path: str) -> tuple[list[int], list[str]]:
    root = ET.parse(path).getroot()
    # pytest writes <testsuites><testsuite>...; older forms write <testsuite>
    # at the top. Both are handled because a report shape this file guesses
    # wrong at would report zero of everything and read as clean.
    suites = [root] if root.tag == "testsuite" else list(root)

    def total(name: str) -> int:
        return sum(int(suite.get(name, 0) or 0) for suite in suites)

    real_skips: list[str] = []
    xfailed = 0
    for suite in suites:
        for case in suite.iter("testcase"):
            for skip in case.findall("skipped"):
                if skip.get("type") == "pytest.xfail":
                    xfailed += 1
                    continue
                message = (skip.get("message") or "").strip()
                real_skips.append(
                    "SKIP {}::{} -- {}".format(
                        case.get("classname", "?"),
                        case.get("name", "?"),
                        message.splitlines()[0] if message else "không nêu lý do",
                    )
                )

    counts = [
        total("tests"),
        len(real_skips),
        xfailed,
        total("failures"),
        total("errors"),
    ]
    return counts, real_skips


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: junit_tally.py <junit-xml>", file=sys.stderr)
        return 2
    try:
        counts, real_skips = tally(argv[1])
    except (OSError, ET.ParseError) as exc:
        print(f"không đọc được báo cáo JUnit: {exc}", file=sys.stderr)
        return 1
    print(" ".join(str(count) for count in counts))
    for line in real_skips:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
