"""Which server routes have a client wrapper that no screen ever calls.

`scripts/check_server_routes_called.py` counts a route as called when any file
under `apps/mobile/src` names it in a string literal -- and `src/api.ts` names
every route it wraps. So a route reaches "có người gọi" the moment somebody
writes the wrapper, whether or not a screen ever imports it. The gate is
honest about what it measures; this measures the next question, which is the
one a feature count actually needs: is there a screen on the other end?

Reads exported wrappers out of `src/api.ts`, then looks for a call site
anywhere else in the app. Report is per wrapper, with the route literal it
sends to, so each line is either "a screen calls this" or "nobody does".
"""

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]
MOBILE = ROOT / "apps" / "mobile"
API_TS = MOBILE / "src" / "api.ts"

src = API_TS.read_text(encoding="utf-8")
lines = src.splitlines()

# export async function <name>(  -- the wrapper surface of the client.
wrappers = []
for i, line in enumerate(lines):
    m = re.match(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(", line)
    if m:
        wrappers.append((m.group(1), i + 1))

# The route literal a wrapper sends to: first backtick/quoted path after it.
route_of = {}
for idx, (name, ln) in enumerate(wrappers):
    end = wrappers[idx + 1][1] - 1 if idx + 1 < len(wrappers) else len(lines)
    body = "\n".join(lines[ln:end])
    m = re.search(r"[\"'`](/[A-Za-z0-9_\-{}$/.:?=&]*)", body)
    route_of[name] = m.group(1) if m else None


def co_nguoi_goi(name: str) -> list[str]:
    """Call sites outside api.ts itself, in .ts/.tsx under the app."""
    out = subprocess.run(
        [
            "grep",
            "-rn",
            "--include=*.ts",
            "--include=*.tsx",
            r"\b" + name + r"\b",
            str(MOBILE / "src"),
            str(MOBILE / "App.tsx"),
        ],
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return [ln for ln in out if "/src/api.ts:" not in ln and "/node_modules/" not in ln]


mo_coi = []
co_goi = []
for name, ln in wrappers:
    hits = co_nguoi_goi(name)
    (co_goi if hits else mo_coi).append(
        {
            "ham": name,
            "dong_api_ts": ln,
            "route": route_of[name],
            "so_noi_goi": len(hits),
        }
    )

report = {
    "tong_vo_boc": len(wrappers),
    "co_man_goi": len(co_goi),
    "khong_ai_goi_ngoai_api_ts": len(mo_coi),
    "danh_sach_mo_coi": mo_coi,
}
print(json.dumps(report, ensure_ascii=False, indent=2))
