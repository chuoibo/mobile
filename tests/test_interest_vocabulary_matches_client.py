"""The taste vocabulary is one list, and it is written down twice.

The server owns the words (ADR-0019 §2.1) and refuses any tag outside them. The
personalization screen keeps its own copy on purpose -- it is drawn before there
is a session, on a phone that may not reach the server, and `so-thich.ts` says
so in its header. Two copies of one list is a decision, not an accident.

What is an accident is the day they stop agreeing. A chip added to the client
alone answers 422 on the write, on the one screen a brand-new account sees
first; a word added to the server alone is a taste nobody can choose. Neither
side's own tests can see it: each is internally consistent.

So this gate reads both files as text and compares them. It imports neither --
the client half is TypeScript, and the server half would need `services/api` on
the path, which the repo-root suite does not have. `ast` for the Python, one
regex for the TypeScript, and a failure message that names which side moved.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER = REPO_ROOT / "services" / "api" / "app" / "domain" / "interests.py"
CLIENT = REPO_ROOT / "apps" / "mobile" / "src" / "screens" / "vao-cua" / "so-thich.ts"


def _server_lists() -> tuple[list[str], list[str]]:
    """Ids of `INTEREST_TAGS` and `BUDGET_BANDS`, read without importing."""

    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names or names[0] not in ("INTEREST_TAGS", "BUDGET_BANDS"):
            continue
        value = node.value
        assert isinstance(value, ast.Tuple), f"{names[0]} phải là tuple hằng"
        ids = []
        for call in value.elts:
            assert isinstance(call, ast.Call) and call.args, f"{names[0]}: phần tử lạ"
            first = call.args[0]
            assert isinstance(first, ast.Constant), f"{names[0]}: id phải là literal"
            ids.append(first.value)
        found[names[0]] = ids
    assert set(found) == {"INTEREST_TAGS", "BUDGET_BANDS"}, (
        f"không đọc được hai danh sách trong {SERVER}: {sorted(found)}"
    )
    return found["INTEREST_TAGS"], found["BUDGET_BANDS"]


def _client_list(const: str) -> list[str]:
    """Ids inside one `export const X: readonly ... = [ ... ];` block."""

    text = CLIENT.read_text(encoding="utf-8")
    start = text.index(f"export const {const}")
    end = text.index("];", start)
    return re.findall(r'\{\s*id:\s*"([^"]+)"', text[start:end])


def _server_bounds() -> list[tuple[str, int, int | None]]:
    """`(id, min_vnd, max_vnd)` for each band, read from the source."""

    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else getattr(node, "targets", [])
        )
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if names[:1] != ["BUDGET_BANDS"]:
            continue
        out = []
        for call in node.value.elts:  # type: ignore[union-attr]
            band_id, _label, low, high = call.args
            out.append((band_id.value, low.value, high.value))
        return out
    raise AssertionError(f"không thấy BUDGET_BANDS trong {SERVER}")


def _client_bounds() -> list[tuple[str, int, int | None]]:
    """The same three, read out of `NGAN_SACH` in the TypeScript."""

    text = CLIENT.read_text(encoding="utf-8")
    start = text.index("export const NGAN_SACH")
    block = text[start : text.index("];", start)]
    out = []
    for row in re.findall(r"\{[^}]*\}", block):
        band_id = re.search(r'id:\s*"([^"]+)"', row)
        low = re.search(r"tu:\s*([0-9_]+)", row)
        high = re.search(r"den:\s*([0-9_]+|null)", row)
        assert band_id and low and high, f"đọc không ra mức ngân sách: {row}"
        out.append(
            (
                band_id.group(1),
                int(low.group(1).replace("_", "")),
                None
                if high.group(1) == "null"
                else int(high.group(1).replace("_", "")),
            )
        )
    return out


def test_the_interest_words_are_the_same_list_on_both_sides() -> None:
    server, _ = _server_lists()
    client = _client_list("SO_THICH")
    assert client == server, (
        "danh sách sở thích lệch nhau.\n"
        f"  máy chủ ({SERVER.name}): {server}\n"
        f"  máy khách ({CLIENT.name}): {client}\n"
        "Thêm một chip chỉ ở máy khách thì lượt ghi trả 422; thêm một từ chỉ ở "
        "máy chủ thì không ai chọn được nó."
    )


def test_the_budget_bands_are_the_same_list_on_both_sides() -> None:
    _, server = _server_lists()
    client = _client_list("NGAN_SACH")
    assert client == server, (
        f"mức ngân sách lệch nhau. máy chủ: {server}; máy khách: {client}"
    )


def test_the_budget_bounds_are_the_same_money_on_both_sides() -> None:
    """Ids agreeing is not enough: «vua-phai» has to mean the same đồng.

    The client writes the band as `tu`/`den` and the server as
    `min_vnd`/`max_vnd`. If one side moves a boundary, every group budget
    computed from these bands moves with it while the screen keeps printing the
    old range -- the sort of disagreement that shows up as a number nobody can
    reproduce rather than as an error.
    """

    server = _server_bounds()
    client = _client_bounds()
    assert client == server, (
        f"biên của mức ngân sách lệch nhau. máy chủ: {server}; máy khách: {client}"
    )
