"""Is every row in `.server-routes-uncalled.json` still a real debt?

The debt pin is a list of "no screen calls this". Rows go stale silently: a lane
ships the screen, the route gets a caller, and the row keeps sitting there
inflating the "still to do" number. `check_server_routes_called.py` does have a
stale-pin branch -- it appends to `stale` when a route is both mentioned and
pinned -- and today that branch prints nothing.

Printing nothing is also what a dead branch prints, and the gate's own
`--selftest` cannot tell the two apart: `_run_canary` passes an EMPTY debt dict
on purpose, so all six built-in canaries exercise the *findings* path and none
of them exercises the *stale* path. So "0 stale rows" arrives here unproven.

This probe proves it, five stages, all against the REAL contract and the REAL
client mention set (no hand-built canary contract):

  [A] POSITIVE CONTROL -- pin a route the client demonstrably calls. The stale
      branch must name it. If this is silent, the branch is dead and every
      other result in this file is worthless.
  [B] NEGATIVE CONTROL -- the pin file exactly as committed. Expect zero stale.
      Only meaningful because [A] passed.
  [C] PER-ROW MUTATION -- drop one pinned row at a time and re-run. A row that
      is genuine debt makes the gate RED (the route lands in `findings`). A row
      that has quietly been paid shows up in `stale` instead, or vanishes into
      neither -- both of which mean the row should be deleted.
  [D] TAIL-FRAGMENT SWEEP -- the class [C] structurally cannot reach. A client
      writing `${prefix}/budget` leaves only the bare suffix in the mention
      set, so the gate calls the route uncalled with full confidence and the
      stale branch never fires. This is how four rows sat stale from #382.
  [E] MUTATION OF [D] ITSELF -- flip a row back to its pre-audit label and
      confirm [D] flips to NGO. A [D] that cannot go red is decoration.

[C] is the part that reading cannot replace: it asks the gate to re-derive each
row from scratch instead of trusting the sentence written next to it. [D] is
the part [C] cannot replace, and [E] is what keeps [D] honest.

One caveat this probe cannot design away, and states instead of hiding: for a
row the reader is blind to (`loai: cong-mu`), [C] going red is NOT evidence the
feature is unreachable -- the reader structurally cannot see that caller, for
either of the two reasons the pin file's `_doc` lists. Those rows are reported
separately rather than counted as debt, and [D] is what checks their claim.

Run from the repository root:
    python3 tests/qa/qa2-ghim-cu-routes-uncalled/probe_ghim_cu.py
Exit 0 every row accounted for, 1 a row is stale or a control failed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"không nạp được {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gate = _load(
    "check_server_routes_called",
    REPO_ROOT / "scripts" / "check_server_routes_called.py",
)

# `loai` is not read by the gate, only by humans. It is read HERE because it is
# the one field that says whether a red [C] means "still to build" or "the
# reader is blind on this row by construction".
GATE_BLIND = "cong-mu"


def real_inputs():
    """The same three inputs the gate feeds itself on a normal run."""
    contract = gate.twin.read_contract(gate.twin.load_openapi())
    if not contract.routes:
        raise RuntimeError("OpenAPI không có route nào — từ chối coi là đạt")
    mentions = gate.client_mentions()
    if not mentions:
        raise RuntimeError("không đọc được đường dẫn nào trong client — bộ đọc hỏng")
    return contract, mentions, gate.load_exemptions()


def pinned_rows() -> list[dict]:
    raw = json.loads(gate.DEBT_PIN.read_text(encoding="utf-8"))
    return list(raw.get("uncalled", []))


def as_debt(rows: list[dict]) -> dict:
    """Rows -> the dict shape `uncalled()` expects, without touching the file."""
    return {
        gate.twin.normalise(r["route"]): gate.Accounted(r["route"], r["reason"], "no")
        for r in rows
    }


def tail_fragment_hits(
    rows: list[dict], mentions: dict
) -> list[tuple[dict, str, object]]:
    """Pinned rows whose trailing literal segment IS a standalone client mention.

    This is the shape `uncalled()` cannot see: a client writing
    `${prefix}/budget` leaves the bare suffix in the mention set and the full
    path nowhere, so the gate reports the route as uncalled with full
    confidence and the stale branch never fires.
    """
    hits = []
    for row in rows:
        segs = row["route"].strip("/").split("/")
        if not segs or segs[-1].startswith("{"):
            continue
        frag = gate.twin.normalise("/" + segs[-1])
        if frag in mentions:
            hits.append((row, frag, mentions[frag][0]))
    return hits


def judge_hit(row: dict) -> tuple[bool, bool]:
    """(is_accounted_for, reason_cites_a_call_site) for one suffix hit.

    A hit only counts as accounted for when the row ALREADY says the gate is
    blind on it AND its reason points at a file:line, which is the rule the
    pin file's own `_doc` states. A hit on any other row is the silent-stale
    condition: the number is read as "still to build" while a screen may
    already call it.
    """
    cites = ".ts:" in row["reason"] or ".tsx:" in row["reason"]
    return (row.get("loai") == GATE_BLIND and cites), cites


def main() -> int:
    contract, mentions, exemptions = real_inputs()
    rows = pinned_rows()
    failures: list[str] = []

    print(
        f"Hợp đồng: {len(contract.routes)} route máy chủ, "
        f"{len(mentions)} đường dẫn client đọc được, {len(rows)} dòng ghim.\n"
    )

    # ---- [A] positive control: does the stale branch fire at all? ----------
    called = sorted(k for k in mentions if k in contract.routes)
    if not called:
        raise RuntimeError(
            "không route nào vừa được khai vừa được gọi — không dựng được đối chứng dương"
        )
    bait_key = called[0]
    bait = contract.spelling.get(bait_key, bait_key)
    _, _, stale_a = gate.uncalled(
        contract,
        mentions,
        exemptions,
        as_debt(rows + [{"route": bait, "reason": "ĐỐI CHỨNG DƯƠNG — không commit"}]),
    )
    fired = any(bait in s for s in stale_a)
    print(f"[A] ĐỐI CHỨNG DƯƠNG — ghim {bait} (client có gọi thật)")
    print(
        f"    nhánh GHIM CŨ: {'CÓ kêu' if fired else 'CÂM'} -> {stale_a or 'không có dòng nào'}"
    )
    if not fired:
        failures.append(
            "[A] nhánh ghim-cũ CÂM: mọi kết luận 'không dòng nào hết hạn' đều vô nghĩa"
        )
    print(f"    => {'ĐẠT' if fired else 'HỎNG'}\n")

    # ---- [B] negative control: the file as committed -----------------------
    findings_b, _, stale_b = gate.uncalled(
        contract, mentions, exemptions, as_debt(rows)
    )
    print("[B] ĐỐI CHỨNG ÂM — file đúng như đã commit")
    print(
        f"    ghim cũ: {stale_b or 'không dòng nào'} · route không ai gọi: "
        f"{[f.route for f in findings_b] or 'không dòng nào'}"
    )
    if stale_b:
        failures.append(f"[B] có dòng hết hạn: {stale_b}")
    print(f"    => {'ĐẠT' if not stale_b else 'HỎNG'}\n")

    # ---- [C] per-row mutation ---------------------------------------------
    print("[C] ĐỘT BIẾN TỪNG DÒNG — gỡ một dòng, hỏi lại cổng")
    print(f"    {'dòng ghim':52} {'loại':10} {'cổng nói gì khi gỡ':28} kết luận")
    blind_rows: list[str] = []
    for row in rows:
        route = row["route"]
        loai = row.get("loai", "(chưa phân loại)")
        kept = [r for r in rows if r["route"] != route]
        findings_c, _, stale_c = gate.uncalled(
            contract, mentions, exemptions, as_debt(kept)
        )
        key = gate.twin.normalise(route)
        in_findings = any(gate.twin.normalise(f.route) == key for f in findings_c)
        in_stale = any(route in s for s in stale_c)

        if in_findings and loai == GATE_BLIND:
            says, verdict = "ĐỎ (nhưng đọc mù ở đây)", "GIỮ — cổng không thấy được"
            blind_rows.append(route)
        elif in_findings:
            says, verdict = "ĐỎ: không ai gọi", "GIỮ — còn nợ thật"
        elif in_stale:
            says, verdict = "GHIM CŨ: đã có người gọi", "GỠ — hết nợ"
            failures.append(
                f"[C] {route} đã có người gọi, phải gỡ khỏi {gate.DEBT_PIN.name}"
            )
        else:
            says, verdict = "im lặng", "GỠ — máy chủ không còn khai"
            failures.append(
                f"[C] {route} không đỏ mà cũng không hết hạn — dòng chỉ vào hư không"
            )
        print(f"    {route:52} {loai:10} {says:28} {verdict}")

    # ---- [D] the class [C] structurally cannot reach ----------------------
    # [C] asks the gate, and the gate reads one literal at a time. A client that
    # writes `${prefix}/budget` leaves the bare suffix `/budget` in the mention
    # set and the full path nowhere, so [C] says "still debt" with total
    # confidence. This stage looks for exactly that shape: a pinned route whose
    # trailing literal segment IS a standalone client mention.
    #
    # A hit is not proof of a caller -- `/budget` could be some other server's
    # path -- so a hit on a row already marked `cong-mu` WITH a file:line in its
    # reason is expected and fine. A hit on any other row is the silent-stale
    # condition and fails, because that row's number is being read as "still to
    # build" while a screen may already call it.
    print("[D] QUÉT MẢNH ĐUÔI — bắt lớp mà [C] không với tới được")
    hits = tail_fragment_hits(rows, mentions)
    for row, frag, where in hits:
        ok, cites = judge_hit(row)
        print(f"    {row['route']:52} mảnh {frag!r} @ {where.file}:{where.line}")
        print(
            f"    {'':52} loai={row.get('loai')} · reason chỉ ra file:dòng? {cites}"
            f" -> {'ĐẠT (đã khai là cổng mù, có dẫn chứng)' if ok else 'NGỜ'}"
        )
        if not ok:
            failures.append(
                f"[D] {row['route']}: client có mảnh {frag!r} ({where.file}:{where.line}) nhưng "
                f"dòng ghim khai loai={row.get('loai')}"
                + ("" if cites else " và reason không chỉ ra chỗ gọi")
                + " — có thể đã hết nợ mà cổng không thấy"
            )
    if not hits:
        print("    không dòng nào có mảnh đuôi trùng literal client")
    print()

    # ---- [E] can [D] go red? ----------------------------------------------
    # [D] passing is only worth reading if [D] is capable of failing. Flip one
    # row back to the classification it carried before this audit and check the
    # judgement flips too. Without this, [D] is exactly the kind of gate that
    # prints reassurance because its condition is unreachable -- which is the
    # defect this whole probe was written to expose in the gate's own selftest.
    print("[E] ĐỘT BIẾN CHÍNH [D] — [D] có đỏ được không?")
    if hits:
        victim = dict(hits[0][0])
        victim["loai"] = "tinh-nang"  # the label it carried before this audit
        would_pass, _ = judge_hit(victim)
        print(
            f"    đặt lại {victim['route']} về loai=tinh-nang -> "
            f"[D] {'vẫn ĐẠT' if would_pass else 'kêu NGỜ'}"
        )
        if would_pass:
            failures.append("[E] [D] không đỏ được: nó ĐẠT cả khi dòng bị đặt sai loại")
        print(f"    => {'ĐẠT' if not would_pass else 'HỎNG'}\n")
    else:
        failures.append(
            "[E] không có mảnh đuôi nào để đột biến — [D] chưa được chứng minh"
        )
        print("    => HỎNG (không dựng được đột biến)\n")

    if blind_rows:
        print("Ghi chú bắt buộc — dòng cổng KHÔNG thấy được người gọi (loai=cong-mu):")
        for r in blind_rows:
            print(f"  {r}")
        print("  Số 0 của cổng ở những dòng này KHÔNG đọc được thành 'route chết'.\n")

    if failures:
        print("KHÔNG ĐẠT:")
        for f in failures:
            print(f"  - {f}")
        return 1
    that_owe = [r for r in rows if r.get("loai") != GATE_BLIND]
    print(
        f"ĐẠT — {len(rows)} dòng ghim đều còn ĐÚNG CHỖ, nhưng 'đúng chỗ' không "
        f"đồng nghĩa 'còn nợ':\n"
        f"  {len(that_owe)} dòng cổng thật sự không thấy người gọi nào "
        f"({', '.join(r['route'] for r in that_owe) or '—'})\n"
        f"  {len(blind_rows)} dòng ĐÃ CÓ người gọi, giữ lại chỉ vì cổng mù theo cấu tạo\n"
        f"  Số 'còn phải làm' = "
        f"{sum(1 for r in that_owe if r.get('loai') == 'tinh-nang')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
