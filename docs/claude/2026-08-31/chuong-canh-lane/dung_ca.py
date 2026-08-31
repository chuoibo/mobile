#!/usr/bin/env python3
"""Build a sandbox harness root for one bell test case.

The bell reads exactly three things: state/lanes/<lane>/state.json (state + ts),
state/events.jsonl (ASSIGNED events -> its notion of queue depth), and
state/lanes/<lane>/*.done (markers it subtracts). This builds all three so a
case is fully described by its arguments -- no hidden state, no real lane.

Age is expressed in minutes BEFORE now, so the clock stays real: the bell still
calls datetime.now(). Nothing here freezes or fakes time.
"""

import datetime
import json
import os
import sys

root, lane, state, age_min = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
n_assigned, n_done = int(sys.argv[5]), int(sys.argv[6])
# Optional: file this many tasks the way `bug-to` does (BUG_FILED, not ASSIGNED).
n_bug = int(sys.argv[7]) if len(sys.argv) > 7 else 0

lane_dir = os.path.join(root, "state", "lanes", lane)
os.makedirs(lane_dir, exist_ok=True)

now = datetime.datetime.now().astimezone()
ts = (now - datetime.timedelta(minutes=age_min)).strftime("%Y-%m-%dT%H:%M:%S%z")
with open(os.path.join(lane_dir, "state.json"), "w") as fh:
    json.dump(
        {"lane": lane, "state": state, "ts": ts, "task_id": f"{lane}-ca-thu"},
        fh,
        ensure_ascii=False,
    )

events = []
for i in range(n_assigned):
    events.append(
        {"type": "ASSIGNED", "lane": lane, "task_id": f"{lane}-viec-{i:03d}", "ts": ts}
    )
for i in range(n_bug):
    # `bug-to` emits BUG_FILED and files a P0 into the inbox. Real queued work.
    events.append(
        {"type": "BUG_FILED", "lane": lane, "task_id": f"{lane}-loi-{i:03d}", "ts": ts}
    )
with open(os.path.join(root, "state", "events.jsonl"), "w") as fh:
    for e in events:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")

for i in range(n_done):
    open(os.path.join(lane_dir, f"{lane}-viec-{i:03d}.done"), "w").write(
        "HARNESS_TASK_COMPLETE\n"
    )

print(
    f"{lane}: state={state} ts={ts} (cach day {age_min:g} phut) "
    f"assigned={n_assigned} bug_filed={n_bug} done={n_done}"
)
