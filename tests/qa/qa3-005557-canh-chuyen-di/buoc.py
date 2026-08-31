"""One tap = one line of evidence: what was tapped, what appeared, what went out.

Run:  python3 buoc.py "<nhãn 1>" "<nhãn 2>" ...

Each argument is tapped in order. After every tap the script prints the screen
(accessibility tree) and the HTTP requests the app made since the previous tap,
read from the proxy log — so "the screen changed" and "the app asked the server"
are two separate observations and neither is inferred from the other.

A tap that finds no node prints KHÔNG THẤY and stops. Stopping is the point: a
click path that dead-ends is the finding, not an error to route around.
"""

from __future__ import annotations

import json
import sys
import time

import lai_native as L

WIRE = "/tmp/qa3-wire.log"


def doc_wire(since: float) -> list[dict]:
    out = []
    try:
        with open(WIRE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec["t"] > since:
                    out.append(rec)
    except FileNotFoundError:
        pass
    return out


def in_wire(recs: list[dict]) -> None:
    if not recs:
        print("    wire: (không gọi gì)")
        return
    for r in recs:
        actor = f" actor={r['actor'][:8]}" if r.get("actor") else ""
        print(
            f"    wire: {r['method']} {r['path']} -> {r['status']} ({r['bytes']}B){actor}"
        )


def main(labels: list[str]) -> int:
    mark = time.time()
    nodes = L.dump()
    print(f"== màn hiện tại ({len(nodes)} node)")
    print("   ", L.screen_text(nodes)[:700])
    for i, label in enumerate(labels, 1):
        nodes = L.dump()
        if L.dismiss_logbox(nodes):
            print(f"[{i}] (đóng dải LogBox trước khi bấm — nó nằm đè lên thanh tab)")
            nodes = L.dump()
        node = L.find(nodes, label)
        if node is None:
            print(f"[{i}] KHÔNG THẤY nút khớp {label!r} — dừng ở đây.")
            print("    màn:", L.screen_text(nodes)[:700])
            return 1
        print(f"[{i}] bấm {node!r}")
        mark = time.time()
        L.tap(node, settle=2.5)
        nodes = L.dump()
        print("    màn:", L.screen_text(nodes)[:700])
        in_wire(doc_wire(mark))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
