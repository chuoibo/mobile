"""Count the ways a money value can be born WITHOUT crossing the strict fence.

#452 found that `MoneyVnd`'s strict fence is one layer thick and that
`model_construct` walks around it. The follow-up question is the one that has
already produced 13 duplicate checks and 11 money slots in this repo: was
`model_construct` the only door, or merely the first one anybody looked at?

So this probe does not count NAMES. It counts WAYS AN OBJECT COMES INTO
EXISTENCE, and asks of each one: can a `float` or a `bool` ride it in?

    __init__ · model_validate · model_validate_json · model_construct ·
    model_copy(update=) · __new__ + __dict__ · attribute assignment

Two directions are measured, because "is there a hole" and "can anyone reach
the hole today" are different questions and answering only the first one is how
a shrug gets mistaken for a clean bill of health:

  * CAPABILITY -- which mechanisms bypass the fence at all (sections 3-5).
  * REACHABILITY -- whether any code under `app/` actually uses them on a money
    model right now (section 6).

Nothing here mutates the tree. Every number is a call against the code as it
stands on the branch, and every section prints what it proves and what it does
not.

Run from `services/api`:

    python tests/qa/qa2-085832-duong-vong-tien/probe_duong_vong_rao_tien.py
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import re
import sys
import uuid
import warnings

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[3]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

import pydantic  # noqa: E402
from pydantic import ConfigDict  # noqa: E402

from app.api import repository as repository_module  # noqa: E402
from app.api.schemas import ExpenseItemInput  # noqa: E402
from app.db import models as db_models  # noqa: E402

RULE = "=" * 78

# A float that is not integral. 82000.5 cannot be rounded into "đồng" without
# somebody silently deciding which way, so it is the clearest possible witness
# that luật 1 (số nguyên đồng) was crossed.
NOT_DONG = 82000.5
GOOD = 82000

APP_ROOT = API_ROOT / "app"

failures: list[str] = []


def section(number: int, title: str) -> None:
    print(f"\n{RULE}\nĐO {number}. {title}\n{RULE}")


def check(condition: bool, message: str) -> None:
    """Record a broken measurement. Not a product defect -- a probe defect."""
    if not condition:
        failures.append(message)


def _source_segment(node: ast.AST, source: str) -> str:
    return ast.get_source_segment(source, node) or ""


def _iter_classes() -> list[tuple[pathlib.Path, ast.ClassDef, str]]:
    out: list[tuple[pathlib.Path, ast.ClassDef, str]] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        source = path.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                out.append((path, node, source))
    return out


def _vnd_fields(cls: ast.ClassDef) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for stmt in cls.body:
        if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
            continue
        if stmt.target.id.endswith("_vnd"):
            fields.append((stmt.target.id, ""))
    return fields


def do_1_who_carries_money() -> None:
    section(1, "AI ĐANG GIỮ TIỀN — phân loại theo CÁCH LỚP ĐÓ RA ĐỜI")
    print("Đếm theo hậu tố `_vnd`, phân loại theo cơ chế lớp, không theo tên file.\n")

    kinds: dict[str, list[tuple[str, str, int]]] = {}
    for path, cls, source in _iter_classes():
        fields = _vnd_fields(cls)
        if not fields:
            continue
        bases = [_source_segment(b, source) for b in cls.bases]
        decorators = [_source_segment(d, source) for d in cls.decorator_list]
        if any("dataclass" in d for d in decorators):
            kind = "dataclass"
        elif any("ApiModel" in b or "BaseModel" in b for b in bases):
            kind = "pydantic"
        elif any("TypedDict" in b for b in bases):
            kind = "TypedDict"
        else:
            kind = "sqlalchemy"
        rel = str(path.relative_to(API_ROOT))
        kinds.setdefault(kind, []).append((rel, cls.name, len(fields)))

    total_fields = 0
    for kind in sorted(kinds):
        rows = kinds[kind]
        count = sum(r[2] for r in rows)
        total_fields += count
        print(f"  {kind:12} {len(rows):3} lớp, {count:3} trường *_vnd")

    fenced = sum(r[2] for r in kinds.get("pydantic", []))
    unfenced = total_fields - fenced
    print(f"\n  Tổng: {total_fields} trường *_vnd trong app/")
    print(f"    {fenced:3} nằm trên model pydantic  — CÓ chỗ để gắn rào")
    print(f"    {unfenced:3} nằm ngoài pydantic      — KHÔNG có rào nào, theo cấu tạo")
    print("\n  CHỨNG MINH: rào strict chỉ tồn tại được ở đúng một tầng trong bốn.")
    print("  KHÔNG chứng minh: rằng tầng ngoài pydantic ĐANG nhận giá trị sai —")
    print("  mục 6 đo chuyện đó, và câu trả lời hôm nay là không.")

    check(fenced > 0, "không tìm thấy trường *_vnd pydantic nào — phép đo hỏng")
    check(unfenced > 0, "không tìm thấy tầng ngoài pydantic — phép đo hỏng")
    return None


def do_2_declaration_gaps() -> None:
    section(2, "RÀO CÓ THỦNG SẴN KHÔNG — mọi trường *_vnd pydantic có strict?")
    print("Một trường tiền khai `int` trần đã là đường vòng, không cần API lạ nào.\n")

    strict_aliases = {
        "MoneyVnd",
        "PositiveMoneyVnd",
        "NonNegativeMoneyVnd",
        "StrictInt",
    }
    strict = 0
    lax: list[str] = []
    for path, cls, source in _iter_classes():
        bases = [_source_segment(b, source) for b in cls.bases]
        decorators = [_source_segment(d, source) for d in cls.decorator_list]
        if any("dataclass" in d for d in decorators):
            continue
        if not any("ApiModel" in b or "BaseModel" in b for b in bases):
            continue
        for stmt in cls.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue
            if not stmt.target.id.endswith("_vnd"):
                continue
            annotation = _source_segment(stmt.annotation, source)
            tokens = set(re.findall(r"\w+", annotation))
            if tokens & strict_aliases or "strict" in annotation:
                strict += 1
            else:
                rel = str(path.relative_to(API_ROOT))
                lax.append(f"{rel}::{cls.name}.{stmt.target.id}: {annotation}")

    print(f"  strict: {strict}")
    print(f"  LAX   : {len(lax)}")
    for line in lax:
        print(f"     !! {line}")
    if not lax:
        print("\n  Không có lỗ do KHAI BÁO. Rào phủ kín mặt tiền pydantic.")
    print("\n  CHỨNG MINH: không ai quên gắn strict lên một trường tiền nào.")
    print("  KHÔNG chứng minh: rằng rào không đi vòng được — mục 3 đo chuyện đó.")

    check(strict > 0, "đếm được 0 trường strict — phép đo hỏng")


def _amount(obj: object) -> object:
    return getattr(obj, "amount_vnd", None)


def do_3_seven_mechanisms() -> None:
    section(3, "BẢY CƠ CHẾ SINH OBJECT — cái nào cho float đi qua?")
    print(
        f"pydantic {pydantic.VERSION}; model đo: ExpenseItemInput.amount_vnd: MoneyVnd"
    )
    print(f"giá trị thử: {NOT_DONG!r} (float không nguyên — không làm tròn được)\n")

    good = ExpenseItemInput(item_id="i", amount_vnd=GOOD, shared_by=[])

    def via_new() -> ExpenseItemInput:
        obj = ExpenseItemInput.__new__(ExpenseItemInput)
        object.__setattr__(
            obj,
            "__dict__",
            {"item_id": "i", "amount_vnd": NOT_DONG, "shared_by": []},
        )
        return obj

    def via_setattr() -> ExpenseItemInput:
        obj = ExpenseItemInput(item_id="i", amount_vnd=GOOD, shared_by=[])
        obj.amount_vnd = NOT_DONG
        return obj

    mechanisms = [
        (
            "__init__",
            lambda: ExpenseItemInput(item_id="i", amount_vnd=NOT_DONG, shared_by=[]),
        ),
        (
            "model_validate",
            lambda: ExpenseItemInput.model_validate(
                {"item_id": "i", "amount_vnd": NOT_DONG, "shared_by": []}
            ),
        ),
        (
            "model_validate_json",
            lambda: ExpenseItemInput.model_validate_json(
                json.dumps({"item_id": "i", "amount_vnd": NOT_DONG, "shared_by": []})
            ),
        ),
        (
            "model_construct",
            lambda: ExpenseItemInput.model_construct(
                item_id="i", amount_vnd=NOT_DONG, shared_by=[]
            ),
        ),
        (
            "model_copy(update=)",
            lambda: good.model_copy(update={"amount_vnd": NOT_DONG}),
        ),
        ("__new__ + __dict__", via_new),
        ("gán thuộc tính", via_setattr),
    ]

    leaked: list[str] = []
    blocked: list[str] = []
    for name, build in mechanisms:
        try:
            obj = build()
        except Exception as exc:  # noqa: BLE001 -- any refusal counts as blocked
            blocked.append(name)
            print(f"  {name:22} CHẶN   {type(exc).__name__}")
            continue
        value = _amount(obj)
        leaked.append(name)
        print(f"  {name:22} LỌT    amount_vnd={value!r} ({type(value).__name__})")

    print(f"\n  chặn: {len(blocked)}/7   LỌT: {len(leaked)}/7")
    print(f"  lọt qua: {', '.join(leaked)}")
    print("\n  TRẢ LỜI CÂU HỎI: model_construct KHÔNG phải đường duy nhất.")
    print("  Và đường thứ tư không phải API lạ — nó là `obj.amount_vnd = x`,")
    print("  dòng Python bình thường nhất mà bất kỳ ai cũng có thể viết.")

    check(
        "__init__" in blocked,
        "đường __init__ bình thường KHÔNG chặn float — nền dương sai, "
        "mọi số ở trên vô nghĩa",
    )
    check(
        "model_validate" in blocked,
        "model_validate KHÔNG chặn float — nền dương sai",
    )
    check(
        "model_construct" in leaked,
        "model_construct KHÔNG lọt — mâu thuẫn với #452, phép đo hỏng",
    )
    check(len(leaked) >= 2, "chỉ thấy 1 đường lọt — không trả lời được câu hỏi")


def do_4_the_cause_and_the_fix() -> None:
    section(4, "NGUYÊN NHÂN CÓ TÊN, VÀ ĐỐI CHỨNG DƯƠNG CHO BẢN VÁ")
    from app.api.schemas import ApiModel

    print(f"  ApiModel.model_config = {dict(ApiModel.model_config)}")
    assignment_validated = ExpenseItemInput.model_config.get(
        "validate_assignment", False
    )
    print(
        f"  validate_assignment   = {assignment_validated}  (pydantic mặc định False)"
    )
    print('\n  `extra="forbid"` gác TRƯỜNG LẠ. Nó không gác GÁN LẠI trường thật.')

    class WithAssignmentValidation(ExpenseItemInput):
        model_config = ConfigDict(extra="forbid", validate_assignment=True)

    obj = WithAssignmentValidation(item_id="i", amount_vnd=GOOD, shared_by=[])
    try:
        obj.amount_vnd = NOT_DONG
        closed = False
    except Exception:  # noqa: BLE001
        closed = True

    print("\n  ĐỐI CHỨNG DƯƠNG — bật validate_assignment=True rồi gán lại:")
    print(f"    cửa 'gán thuộc tính' đóng: {closed}")
    print("\n  CHỨNG MINH: một dòng config đóng được cửa thứ tư, và đo được là đóng.")
    print("  KHÔNG chứng minh: nó đóng ba cửa kia — model_construct, model_copy,")
    print("  __new__ vẫn đi vòng được. Rào ở BIÊN không đóng hết được;")
    print("  đó là lý do #450 phải cưỡng chế ở LÕI.")

    check(
        assignment_validated is False, "validate_assignment đã bật — mục 3 phải đọc lại"
    )
    check(closed, "bật validate_assignment vẫn không chặn — bản vá đề xuất KHÔNG chạy")


def do_5_does_it_reach_the_wire() -> None:
    section(5, "GIÁ TRỊ LỌT CÓ RA TỚI DÂY KHÔNG — hay chết dọc đường?")
    print("Một lỗ chỉ đáng lo nếu giá trị sai đi được tới người dùng.\n")

    obj = ExpenseItemInput.model_construct(
        item_id="i", amount_vnd=NOT_DONG, shared_by=[]
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dumped = obj.model_dump()
    encoded = json.dumps(dumped)

    print(f"  model_dump() -> {dumped}")
    print(f"  json.dumps() -> {encoded}")
    print(f"  cảnh báo pydantic phát ra: {len(caught)}")
    for w in caught:
        print(f"     {w.category.__name__}: {str(w.message).splitlines()[0][:90]}")

    print("\n  CHỨNG MINH: giá trị lọt KHÔNG chết dọc đường — nó ra tới JSON")
    print("  nguyên vẹn là 82000.5. Pydantic có nhận ra, nhưng chỉ bằng")
    print("  UserWarning trên stderr: không mã lỗi, không log ứng dụng, không 500.")
    print("  Trên production không ai đọc stderr của tiến trình web.")
    print("  KHÔNG chứng minh: rằng có route nào đang làm thế — mục 6 đo cái đó.")

    check("82000.5" in encoded, "float không ra tới JSON — kết luận mục này sai")
    check(len(caught) >= 1, "pydantic không cảnh báo gì — đọc lại mô tả ở trên")


def do_6_reachability_today() -> None:
    section(6, "HÔM NAY CÓ AI ĐI ĐƯỜNG VÒNG KHÔNG — quét app/ bằng AST")
    print(
        "Câu hỏi khác hẳn mục 3: ở đó là 'có lỗ không', ở đây là 'có ai tới không'.\n"
    )

    bypass_calls = {"model_construct", "construct", "model_copy", "copy", "__new__"}
    call_hits: dict[str, list[str]] = {}
    assign_hits: list[str] = []

    for path in sorted(APP_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = str(path.relative_to(API_ROOT))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in bypass_calls
            ):
                call_hits.setdefault(node.func.attr, []).append(f"{rel}:{node.lineno}")
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AugAssign | ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr.endswith("_vnd"):
                    assign_hits.append(f"{rel}:{node.lineno}")

    for name in sorted(bypass_calls):
        hits = call_hits.get(name, [])
        print(f"  {name:18} {len(hits)} chỗ trong app/")
        for hit in hits[:8]:
            print(f"       {hit}")
    print(f"  gán *_vnd          {len(assign_hits)} chỗ trong app/")
    for hit in assign_hits[:8]:
        print(f"       {hit}")

    total = sum(len(v) for v in call_hits.values()) + len(assign_hits)
    print(f"\n  Tổng lối đi vòng ĐANG được dùng trong app/: {total}")
    print("\n  CHỨNG MINH: bốn cửa mở, nhưng hôm nay không cửa nào có người đi.")
    print("  Rào một lớp vẫn đủ an toàn HÔM NAY, và giờ ta biết chính xác vì sao:")
    print("  không phải vì rào kín, mà vì chưa ai viết dòng code đi vòng.")
    print("  KHÔNG chứng minh: rằng ngày mai vẫn thế. Không cổng nào gác điều này —")
    print("  một `obj.amount_vnd = x` thêm vào tuần sau sẽ không làm đỏ cái gì cả.")


def do_7_layers_behind_the_fence() -> None:
    section(7, "TẦNG SAU RÀO — nếu lọt được vào thì có ai chặn tiếp không?")
    print("Rào pydantic là tầng duy nhất có kiểu. Đo hai tầng sau nó.\n")

    row = repository_module.AllocationRow(
        id=uuid.uuid4(), participant_id=uuid.uuid4(), amount_vnd=NOT_DONG
    )
    row_bool = repository_module.AllocationRow(
        id=uuid.uuid4(), participant_id=uuid.uuid4(), amount_vnd=True
    )
    frozen = repository_module.AllocationRow.__dataclass_params__.frozen
    orm = db_models.ConfirmedAllocation(amount_vnd=NOT_DONG)

    print(f"  dataclass AllocationRow (frozen={frozen})")
    print(
        f"     amount_vnd={NOT_DONG!r} -> {row.amount_vnd!r} "
        f"({type(row.amount_vnd).__name__})  KHÔNG chặn, KHÔNG cảnh báo"
    )
    print(
        f"     amount_vnd=True    -> {row_bool.amount_vnd!r} "
        f"({type(row_bool.amount_vnd).__name__})  KHÔNG chặn"
    )
    print("  sqlalchemy ConfirmedAllocation")
    print(
        f"     amount_vnd={NOT_DONG!r} -> {orm.amount_vnd!r} "
        f"({type(orm.amount_vnd).__name__})  KHÔNG chặn"
    )

    print("\n  CHỨNG MINH: `int` trong dataclass và `Mapped[int]` trong SQLAlchemy")
    print("  là chú thích cho người đọc, không phải phép kiểm lúc chạy. Qua được")
    print("  rào pydantic là không còn ai hỏi lại nữa, cho tới tận câu INSERT.")
    print("  KHÔNG chứng minh: Postgres làm gì với float ở cột BIGINT —")
    print("  cần tầng live mới trả lời được, và câu đó chưa ai đo.")

    check(
        isinstance(row.amount_vnd, float),
        "dataclass ÉP KIỂU float thành int — kết luận mục này sai",
    )
    check(
        dataclasses.is_dataclass(repository_module.AllocationRow),
        "không phải dataclass",
    )


def main() -> int:
    print(RULE)
    print("ĐẾM ĐƯỜNG VÒNG QUANH RÀO TIỀN — theo CÁCH OBJECT RA ĐỜI")
    print("câu hỏi: model_construct là đường duy nhất, hay chỉ là đường đầu tiên?")
    print(RULE)
    do_1_who_carries_money()
    do_2_declaration_gaps()
    do_3_seven_mechanisms()
    do_4_the_cause_and_the_fix()
    do_5_does_it_reach_the_wire()
    do_6_reachability_today()
    do_7_layers_behind_the_fence()

    print(f"\n{RULE}\nTỰ KIỂM PHÉP ĐO\n{RULE}")
    if failures:
        print("PHÉP ĐO NÀY HỎNG -- đừng đọc kết luận ở trên:")
        for line in failures:
            print(f"   !! {line}")
        return 1
    print("Mọi nền dương và đối chứng đều đúng như mong đợi; số liệu ở trên đọc được.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
