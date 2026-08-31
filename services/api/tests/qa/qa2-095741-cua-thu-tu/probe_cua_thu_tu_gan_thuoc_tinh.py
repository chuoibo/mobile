"""Door #4 -- POST-CONSTRUCTION ATTRIBUTE ASSIGNMENT -- census and behaviour.

#452 established that `MoneyVnd`'s strict fence is one layer thick, and the
follow-up probe counted seven ways a money value can come into existence
without crossing it. Four of those seven bypass the fence. This probe takes the
fourth door on its own, because it is the one that needs no intent at all:

    obj.amount_vnd = 0.5     # after the model is built. No API. No trick.

The previous probe already printed a number for this door: `gán *_vnd 0 chỗ`.
That number is not reused here, and the reason matters more than the number. It
was produced by ONE shape (`ast.Attribute` whose name ends in `_vnd`) with NO
positive control. A zero from an unproven detector and a zero from a real
absence look identical on the page. This probe separates them:

  * SHAPE COVERAGE -- six mutation shapes, not one (section 2).
  * POSITIVE CONTROL -- a planted file containing all six, to prove the census
    can see a site when a site exists (section 1). A census that has never
    printed a non-zero number has not been shown to work.
  * FULL DENOMINATOR -- every attribute assignment under `app/` is listed, not
    just the money-named ones, so "no money among them" is a claim a reader can
    check instead of trust (section 3).
  * BEHAVIOUR, NOT METADATA -- whether the door is open is measured by
    assigning to a real model, not by reading `model_config` (section 4).
    Declaring `strict=True` in metadata is not the same as the value being
    rejected, and this repo has been burned by that difference before.
  * WHAT IS BEHIND IT -- if someone walks the door tomorrow, which layer
    notices (section 5).

Nothing here mutates the tree. Every number is a call against the code as it
stands on this branch.

Run from `services/api`:

    python tests/qa/qa2-095741-cua-thu-tu/probe_cua_thu_tu_gan_thuoc_tinh.py
"""

from __future__ import annotations

import ast
import pathlib
import sys
import tempfile
import uuid
import warnings

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[3]
sys.path.insert(0, str(API_ROOT))
APP_ROOT = API_ROOT / "app"

# Money names are DERIVED from the code below, never hand-listed; a hand list
# does not know what it is missing. These generic stems are the safety net for
# a money field that never says "vnd" in its name.
MONEY_STEMS = (
    "vnd",
    "amount",
    "total",
    "price",
    "subtotal",
    "fee",
    "discount",
    "share",
    "owed",
    "paid",
    "balance",
    "money",
    "cost",
    # `allocations: dict[UUID, MoneyVnd]` carries money and says none of the
    # words above. Section 2's coverage check is what caught that, which is the
    # whole reason section 2 runs before the count instead of after it.
    "allocation",
)

FAILURES: list[str] = []
# Filled by section 2 from the code itself, consumed by section 3: a name that
# merely LOOKS like money is a candidate, a name that is DECLARED money is a
# finding. Keeping the two apart is what stops `share_percent` from being
# reported as money the product moves.
DECLARED_MONEY: set[str] = set()


def section(number: int, title: str) -> None:
    print("\n" + "=" * 78)
    print(f"ĐO {number}. {title}")
    print("=" * 78)


def check(condition: bool, message: str) -> None:
    print(f"  [{'OK ' if condition else 'SAI'}] {message}")
    if not condition:
        FAILURES.append(message)


def looks_like_money(name: str) -> bool:
    lowered = name.lower()
    return any(stem in lowered for stem in MONEY_STEMS)


# --------------------------------------------------------------------------
# The census itself. Six shapes, one function, used identically on the planted
# control file and on the real tree -- that is what makes the control mean
# something.
# --------------------------------------------------------------------------

SHAPES = (
    "S1 obj.<field> = v",
    "S2 obj.<field> += v",
    "S3 setattr(obj, '<field>', v)",
    "S4 obj.__dict__['<field>'] = v",
    "S5 object.__setattr__(obj, '<field>', v)",
    "S6 mapping['<field>'] = v",
)


def _const_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def census(tree: ast.Module, rel: str) -> list[tuple[str, str, str]]:
    """Return (shape, field-name, "path:line") for every mutation site found."""
    hits: list[tuple[str, str, str]] = []

    def add(shape: str, field: str, node: ast.AST) -> None:
        hits.append((shape, field, f"{rel}:{node.lineno}"))

    for node in ast.walk(tree):
        # S1 / S2 / S4 / S6 -- assignment targets.
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]

        for target in targets:
            if isinstance(target, ast.Attribute):
                shape = SHAPES[1] if isinstance(node, ast.AugAssign) else SHAPES[0]
                add(shape, target.attr, node)
            elif isinstance(target, ast.Subscript):
                key = _const_str(target.slice)
                if key is None:
                    continue
                base = target.value
                # `obj.__dict__["x"] = v` is S4; any other mapping write is S6.
                if isinstance(base, ast.Attribute) and base.attr == "__dict__":
                    add(SHAPES[3], key, node)
                else:
                    add(SHAPES[5], key, node)

        # S3 / S5 -- assignment spelled as a call.
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "setattr" and len(node.args) >= 2:
                add(SHAPES[2], _const_str(node.args[1]) or "<dynamic>", node)
            elif name == "__setattr__" and len(node.args) >= 2:
                add(SHAPES[4], _const_str(node.args[1]) or "<dynamic>", node)

    return hits


CONTROL_SOURCE = '''
"""Planted control. Every shape below IS a door-4 site and must be seen."""


def plant(obj, mapping):
    obj.amount_vnd = 0.5
    obj.total_vnd += 0.5
    setattr(obj, "line_total_vnd", 0.5)
    obj.__dict__["unit_price_vnd"] = 0.5
    object.__setattr__(obj, "items_total_vnd", 0.5)
    mapping["subtotal_amount_vnd"] = 0.5
    obj.display_name = "not money"
'''


def do_1_positive_control() -> None:
    section(1, "ĐỐI CHỨNG DƯƠNG — phép đếm có nhìn thấy gì không")
    print("Một số 0 từ máy đếm chưa bao giờ đếm được gì thì không phải bằng chứng.")
    print("Trước khi tin số 0 ở mục 3, trồng sẵn 6 chỗ và bắt máy đếm tìm ra.\n")

    with tempfile.TemporaryDirectory() as tmp:
        planted = pathlib.Path(tmp) / "planted_control.py"
        planted.write_text(CONTROL_SOURCE)
        hits = census(ast.parse(planted.read_text()), "planted_control.py")

    money_hits = [h for h in hits if looks_like_money(h[1])]
    seen_shapes = {shape for shape, _, _ in money_hits}

    for shape in SHAPES:
        found = shape in seen_shapes
        check(found, f"thấy {shape}")
    check(
        len(seen_shapes) == len(SHAPES),
        f"6/6 hình dạng bị bắt (thực tế {len(seen_shapes)}/6)",
    )
    non_money = [h for h in hits if not looks_like_money(h[1])]
    check(
        len(non_money) == 1 and non_money[0][1] == "display_name",
        f"lọc tên tiền không ăn nhầm dòng không phải tiền ({len(non_money)} dòng bị loại)",
    )
    print("\n  Máy đếm ở mục 3 là ĐÚNG hàm này, không phải một bản viết lại.")


def do_2_name_coverage() -> None:
    section(2, "PHỦ TÊN — bộ lọc tên tiền có bỏ sót trường tiền thật nào không")
    print("Bộ lọc bắt theo gốc từ, không theo danh sách tay. Kiểm nó trên các")
    print("trường tiền ĐANG khai trong schema pydantic và cột ORM.\n")

    declared: set[str] = set()

    schemas = ast.parse((APP_ROOT / "api" / "schemas.py").read_text())
    for node in ast.walk(schemas):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotation = ast.unparse(node.annotation)
            if "MoneyVnd" in annotation:
                declared.add(node.target.id)

    models = ast.parse((APP_ROOT / "db" / "models.py").read_text())
    for node in ast.walk(models):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
            and "mapped_column" in ast.unparse(node.value)
            and "BigInteger" in ast.unparse(node.value)
        ):
            declared.add(node.target.id)

    DECLARED_MONEY.update(declared)
    missed = sorted(name for name in declared if not looks_like_money(name))
    print(f"  Trường tiền khai trong schemas.py + models.py: {len(declared)}")
    print(f"  Ví dụ: {', '.join(sorted(declared)[:6])} ...")
    check(not missed, f"bộ lọc phủ hết {len(declared)} tên (sót: {missed or 'không'})")
    print("\n  KHÔNG chứng minh: một trường tiền đặt tên không có gốc nào ở trên")
    print("  (ví dụ `so_tien`) vẫn sẽ lọt bộ lọc — nên mục 3 in CẢ MẪU SỐ.")


def do_3_census_of_app() -> None:
    section(3, "ĐẾM THẬT — mọi phép gán thuộc tính dưới app/, có in mẫu số")

    all_hits: list[tuple[str, str, str]] = []
    files = 0
    for path in sorted(APP_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        files += 1
        all_hits.extend(census(tree, str(path.relative_to(API_ROOT))))

    money = [h for h in all_hits if h[1] in DECLARED_MONEY]
    suspect = [
        h for h in all_hits if h[1] not in DECLARED_MONEY and looks_like_money(h[1])
    ]
    other = [h for h in all_hits if not looks_like_money(h[1])]

    print(f"  File quét: {files}")
    print(f"  MẪU SỐ — tổng chỗ gán/đặt thuộc tính mọi loại: {len(all_hits)}")
    by_shape: dict[str, int] = {}
    for shape, _, _ in all_hits:
        by_shape[shape] = by_shape.get(shape, 0) + 1
    for shape in SHAPES:
        print(f"       {shape:38} {by_shape.get(shape, 0)}")

    print(f"\n  A. TRƯỜNG TIỀN ĐÃ KHAI bị gán sau khi dựng: {len(money)}")
    for shape, field, where in money:
        print(f"       {where}  {field}   [{shape}]")
    if not money:
        print("       (không có chỗ nào)")

    print(f"\n  B. Tên GIỐNG tiền nhưng không phải trường tiền đã khai: {len(suspect)}")
    print("     In ra để người đọc tự phán, không lặng lẽ bỏ:")
    for shape, field, where in suspect:
        print(f"       {where}  {field}   [{shape}]")
    if not suspect:
        print("       (không có chỗ nào)")

    print(f"\n  Còn lại {len(other)} chỗ không phải tiền — in hết để người đọc tự soi,")
    print("  vì 'không có tiền trong đám này' là khẳng định phải kiểm được:")
    for _, field, where in sorted(other, key=lambda h: h[2]):
        print(f"       {where}  {field}")

    print()
    check(
        len(all_hits) > 0,
        f"phép đếm chạm được vào cây thật ({len(all_hits)} chỗ, không phải 0 vì hỏng)",
    )
    print(f"  TRẢ LỜI: cửa thứ tư có {len(money)} chỗ đang đi qua trong app/.")
    return money, suspect


def do_4_is_the_door_open() -> None:
    section(4, "CỬA CÓ MỞ KHÔNG — đo bằng HÀNH VI, không đọc model_config")
    print("Khai `strict=True` trong metadata không chứng minh giá trị bị chặn.")
    print("Nên gán thẳng vào một model đã dựng xong và xem có ai kêu không.\n")

    from app.api.schemas import ApiModel, ExpenseItemInput

    obj = ExpenseItemInput(item_id="i1", amount_vnd=82000, shared_by=[uuid.uuid4()])
    print(
        f"  Dựng hợp lệ: amount_vnd={obj.amount_vnd!r} ({type(obj.amount_vnd).__name__})"
    )

    for label, value in (("float", 0.5), ("bool", True), ("str", "82000")):
        try:
            obj.amount_vnd = value  # type: ignore[assignment]
            landed = obj.amount_vnd
            print(
                f"  gán {label:5} {value!r:9} -> {landed!r} "
                f"({type(landed).__name__})  KHÔNG chặn"
            )
        except Exception as exc:  # noqa: BLE001 -- any rejection counts as closed
            print(f"  gán {label:5} {value!r:9} -> bị chặn: {type(exc).__name__}")

    obj.amount_vnd = 0.5  # type: ignore[assignment]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dumped = obj.model_dump()["amount_vnd"]
    print(
        f"\n  Sau khi gán 0.5, model_dump() trả: {dumped!r} ({type(dumped).__name__})"
    )
    check(
        isinstance(dumped, float),
        "float đi xuyên model_dump — giá trị bẩn KHÔNG bị giặt lại ở đường ra",
    )

    # There IS one voice in the whole stack, and knowing exactly how loud it is
    # matters: a UserWarning does not fail a request, does not fail a test run,
    # and is not read by anyone in production. "Warns" is not "catches".
    print(f"\n  Có ai kêu không khi 0.5 đi ra? {len(caught)} cảnh báo:")
    for item in caught:
        print(f"       {item.category.__name__}: {str(item.message).strip()[:110]}")
    check(
        any(issubclass(item.category, UserWarning) for item in caught),
        "pydantic CÓ cảnh báo lúc serialize — nhưng là UserWarning, không phải lỗi",
    )
    print("       => cảnh báo này không làm hỏng request, không làm đỏ test,")
    print("          và không ai đọc nó lúc chạy thật. Kêu KHÔNG phải là chặn.")

    validate_assignment = ApiModel.model_config.get("validate_assignment", False)
    print("\n  Kèm theo (chỉ để đối chiếu, không phải bằng chứng chính):")
    print(f"       ApiModel.model_config = {dict(ApiModel.model_config)}")
    check(
        validate_assignment is False,
        "validate_assignment KHÔNG bật — khớp với hành vi đo ở trên",
    )


def do_5_layers_behind_the_door() -> None:
    section(5, "SAU CỬA — nếu ngày mai có người gán, tầng nào kêu")

    from app.db import models as db_models

    # Construct through the real constructor. An instance made with `__new__`
    # has no `_sa_instance_state`, so assignment raises AttributeError and the
    # probe reads "ORM blocks it" -- a clean-looking false negative produced by
    # the measurement rather than by the code under test.
    row = db_models.ExpenseItem()
    try:
        row.amount_vnd = 0.5
        print(f"  ORM ExpenseItem.amount_vnd = 0.5 -> {row.amount_vnd!r}  KHÔNG chặn")
        orm_blocks = False
    except Exception as exc:  # noqa: BLE001
        print(f"  ORM ExpenseItem.amount_vnd = 0.5 -> bị chặn: {type(exc).__name__}")
        orm_blocks = True

    print("\n  Cột là BigInteger, và CheckConstraint chỉ gác DẤU (> 0 / >= 0),")
    print("  không gác KIỂU. Tầng cuối cùng là Postgres.")
    print("\n  TRÍCH DẪN, KHÔNG PHẢI PHÉP ĐO CỦA PROBE NÀY: #460 (đã merge) đo")
    print("  trên PostgreSQL 16 thật và thấy Postgres KHÔNG từ chối float — nó")
    print("  làm tròn nửa-về-chẵn và im lặng (1500.5 -> 1500, 1501.5 -> 1502);")
    print("  bool thì bị từ chối. Probe này không dựng DB nên KHÔNG kiểm lại số")
    print("  đó; ghi là dẫn nguồn để người đọc biết đi hỏi ở đâu, không phải để")
    print("  cộng thêm một dấu xanh.")
    check(
        not orm_blocks,
        "ORM không chặn ở tầng Python — tầng duy nhất còn lại là DB",
    )
    print("\n  Ghép lại thành chuỗi: pydantic KHÔNG chặn lúc gán (mục 4) ->")
    print("  ORM KHÔNG chặn -> Postgres làm tròn im lặng (#460). Không tầng nào")
    print("  ĐỎ. Nên nếu cửa thứ tư có người đi, triệu chứng sẽ là một con số hơi")
    print("  lệch trong sổ, không phải một lỗi 500 ai đó nhìn thấy.")


def main() -> int:
    print("CỬA THỨ TƯ: GÁN THUỘC TÍNH SAU KHI MODEL ĐÃ DỰNG XONG")
    print(f"app/ = {APP_ROOT}")
    do_1_positive_control()
    do_2_name_coverage()
    money, suspect = do_3_census_of_app()
    do_4_is_the_door_open()
    do_5_layers_behind_the_door()

    section(6, "TÓM TẮT MỘT DÒNG")
    print(f"  Trường tiền đã khai bị gán sau khi dựng: {len(money)} chỗ")
    print(f"  Tên giống tiền cần người phán:            {len(suspect)} chỗ")
    if money:
        print("\n  >>> CÓ TIỀN ĐANG ĐI QUA CỬA THỨ TƯ. Báo Lead ngay.")
    else:
        print(
            "\n  >>> Cửa thứ tư MỞ nhưng CHƯA AI ĐI QUA (mục 4 đo cửa, mục 3 đếm người)."
        )
        print(
            "  Đây là 'đóng một cửa trước khi có người đi', không phải 'vá lỗ đang chảy'."
        )

    print("\n" + "=" * 78)
    if FAILURES:
        print(f"KẾT: {len(FAILURES)} phép kiểm SAI")
        for item in FAILURES:
            print(f"  - {item}")
        return 1
    print("KẾT: mọi phép kiểm của probe tự nhất quán.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
