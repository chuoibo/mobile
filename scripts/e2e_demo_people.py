#!/usr/bin/env python3
"""The three demo people the e2e slice drives, read out of the client source.

`scripts/e2e_slice.sh` needs their `personId` values to mint a session for each
one, and the ids live in `apps/mobile/src/rudi/nhom-demo.ts` as literals
because the slice's own group bootstrap addresses them by slug.

Read rather than duplicated: a second copy of three UUIDs is a second thing to
drift, and the failure it produces -- a session minted for somebody the client
never acts as -- shows up as a 401 that reads like a server fault.

Exits non-zero when a slug is missing rather than printing a short list. A
regex that silently stops matching would mint no sessions at all, and the slice
would then fail with the exact symptom this file exists to prevent.
"""

from __future__ import annotations

import re
import sys

#: The three the slice signs in as. `SLUGS` in
#: `apps/mobile/tests/e2e/vertical-slice.test.mjs` is the other end of this
#: agreement; adding a fourth person there needs a fourth line here.
WANTED = ("minh", "trang", "ngoc")

_PERSON = re.compile(
    r'\{\s*id:\s*"(?P<slug>[a-z]+)",\s*'
    r'personId:\s*"(?P<person_id>[0-9a-fA-F-]{36})",\s*'
    r'name:\s*"(?P<name>[^"]+)"'
)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: e2e_demo_people.py <nhom-demo.ts>", file=sys.stderr)
        return 2

    source = open(argv[1], encoding="utf-8").read()
    found = {
        match.group("slug"): (match.group("person_id"), match.group("name"))
        for match in _PERSON.finditer(source)
    }
    missing = [slug for slug in WANTED if slug not in found]
    if missing:
        print(
            f"khong doc duoc demo person: {missing}. "
            f"nhom-demo.ts doi hinh dang, hoac WANTED o day da cu.",
            file=sys.stderr,
        )
        return 1

    for slug in WANTED:
        person_id, name = found[slug]
        print(f"{person_id}\t{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
