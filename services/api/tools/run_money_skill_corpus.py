"""Run the independent deterministic baseline over all handwritten cases.

Usage, from ``services/api``::

    python3 tools/run_money_skill_corpus.py

The command prints every outcome before returning non-zero when any case fails.
It uses synthetic corpus data only and never calls a network service.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from tests.skills.corpus_harness import evaluate_corpus  # noqa: E402


def main() -> int:
    outcomes = evaluate_corpus()
    failed = 0

    for outcome in outcomes:
        status = "PASS" if outcome.passed else "FAIL"
        print(f"{status} {outcome.case_id}")
        if not outcome.passed:
            failed += 1
            print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))

    print(
        f"SUMMARY passed={len(outcomes) - failed} failed={failed} total={len(outcomes)}"
    )
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
