"""Trace one money value from HTTP to `allocate()` and count the barriers.

Backend counted CALL SITES of `allocate()`. This probe counts BARRIERS along the
path a single amount travels -- route -> schema -> service -> allocator -- and
asks at each layer: can a `float` (or a `bool`) cross it unchanged?

Nothing here mutates the tree. Every measurement is a call against the code as
it stands on the branch, and each section prints what it proves and what it does
not.

Run from `services/api`:

    python tests/qa/qa2-082907-luat-1-o-allocator/probe_duong_di_cua_mot_so_tien.py
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[3]
sys.path.insert(0, str(API_ROOT))

import anyio  # noqa: E402
import httpx  # noqa: E402

from app.domain import ledger as ledger_module  # noqa: E402
from app.domain.allocator import allocate  # noqa: E402
from app.domain.bill import allocator_input_from_bill  # noqa: E402
from app.domain.contract import ERROR_PRECEDENCE, AllocationError  # noqa: E402

# The suite's canonical cast, not a second set. Declaring fresh ids here would
# also trip the repo guard's long-number rule, which reads a 32-digit run as a
# possible account number.
from tests.api.helpers import ADVANCER_ID, CONTEXT_ID, SENDER_ID  # noqa: E402

RULE = "=" * 78

failures: list[str] = []


def section(number: int, title: str) -> None:
    print(f"\n{RULE}\nĐO {number}. {title}\n{RULE}")


# ---------------------------------------------------------------------------
# ĐO 1 -- the allocator itself, four money slots x {float, bool}
# ---------------------------------------------------------------------------


def _even(total):
    return {
        "participants": ["a", "b", "c"],
        "total_vnd": total,
        "items": [],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    }


def _itemized(item_amount, total=100000):
    return {
        "participants": ["a", "b"],
        "total_vnd": total,
        "items": [
            {"item_id": "i1", "amount_vnd": item_amount, "shared_by": ["a", "b"]}
        ],
        "surcharges": [],
        "discounts": [],
        "advancer_id": None,
    }


def _surcharged(surcharge_amount):
    return {
        "participants": ["a", "b"],
        "total_vnd": 110000,
        "items": [{"item_id": "i1", "amount_vnd": 100000, "shared_by": ["a", "b"]}],
        "surcharges": [
            {
                "surcharge_id": "s1",
                "kind": "fee",
                "amount_vnd": surcharge_amount,
                "mode": "even",
            }
        ],
        "discounts": [],
        "advancer_id": None,
    }


def _discounted(discount_amount):
    return {
        "participants": ["a", "b"],
        "total_vnd": 90000,
        "items": [{"item_id": "i1", "amount_vnd": 100000, "shared_by": ["a", "b"]}],
        "surcharges": [],
        "discounts": [
            {
                "discount_id": "d1",
                "amount_vnd": discount_amount,
                "scope": "item",
                "item_id": "i1",
            }
        ],
        "advancer_id": None,
    }


SLOTS = [
    ("total_vnd", _even, 100000),
    ("items[].amount_vnd", _itemized, 100000),
    ("surcharges[].amount_vnd", _surcharged, 10000),
    ("discounts[].amount_vnd", _discounted, 10000),
]


def call(expense):
    """Return one of three outcomes, because there turned out to be three.

    ``ok``    -- allocate() answered; the money it answered with may be wrong.
    ``error`` -- a contract AllocationError, which the API turns into a 422.
    ``crash`` -- any other exception. This one matters on its own: allocate()
                 promises dict-in/dict-out plus AllocationError, and
                 ``app/api/service.py`` catches only AllocationError, so a
                 crash here leaves the route as an unhandled 500.
    """
    try:
        return ("ok", allocate(expense)["allocations"])
    except AllocationError as exc:
        return ("error", exc.code)
    except Exception as exc:  # noqa: BLE001 -- classifying the escape is the point
        return ("crash", f"{type(exc).__name__}: {exc}")


def do_1_allocator_layer() -> None:
    section(1, "Tầng allocator (L0): bốn ô tiền × {int, float, bool}")
    print(
        "Tự kiểm: bản int phải RA ĐÚNG, nếu không thì probe hỏng chứ không phải code.\n"
    )
    print(f"{'ô tiền':<26} {'giá trị':<15} {'kết cục':<8} chi tiết")
    print("-" * 92)
    tally = {"ok": 0, "error": 0, "crash": 0}
    for name, build, good in SLOTS:
        for label, value in (
            ("int (nền)", good),
            ("float .0", float(good)),
            ("float lẻ", good + 0.5),
            ("bool True", True),
        ):
            kind, payload = call(build(value))
            if kind == "ok":
                total = sum(payload.values())
                shown = f"Σ={total!r} ({type(total).__name__})"
            else:
                shown = str(payload)
            if label != "int (nền)":
                tally[kind] += 1
            elif kind != "ok":
                failures.append(f"ĐO 1: nền int ở {name} không chạy được -- probe hỏng")
            print(f"{name:<26} {label:<15} {kind:<8} {shown[:44]}")
        print()
    print(f"12 ca phi-int trên 4 ô tiền: {tally}")
    if tally["error"] == 12:
        failures.append(
            "ĐO 1: mọi ca đều bị chặn -- phát hiện của backend KHÔNG tái lập"
        )
    print(
        "\nBa kết cục, KHÔNG phải hai. 'error' là mã hợp đồng -> 422 đúng nghĩa.\n"
        "'ok' là tiền sai đi tiếp im lặng. 'crash' là 500: allocate() ném ra thứ\n"
        "ngoài AllocationError, mà app/api/service.py chỉ bắt AllocationError.\n"
        "\nChứng minh: allocate() không có phép kiểm kiểu số nguyên nào.\n"
        "KHÔNG chứng minh: người dùng thật gửi được float tới đây (xem ĐO 3)."
    )


# ---------------------------------------------------------------------------
# ĐO 2 -- money that is WRONG, not merely typed loosely
# ---------------------------------------------------------------------------


def do_2_the_money_is_wrong() -> None:
    section(2, "Không chỉ lọt kiểu -- tiền RA SAI")
    print("a) bool True ở total_vnd: một hoá đơn thành 1 đồng\n")
    kind, payload = call(_even(True))
    print(f"   allocate(total_vnd=True) -> {kind}: {payload}")
    if kind == "ok":
        print(f"   Σ = {sum(payload.values())!r}  (bữa ăn 1 đồng, chia ba)")
    else:
        failures.append("ĐO 2a: bool bị chặn -- khác kết luận backend")

    print("\nb) float ở total_vnd: luật 2 (Σ = tổng) tính bằng số dấu phẩy động\n")
    kind, payload = call(_even(0.1 + 0.2))
    print(f"   allocate(total_vnd=0.1+0.2) -> {kind}: {payload}")

    print(
        "\nc) float mang phần lẻ: luật 2 (Σ phân bổ = tổng khoản chi) còn đúng không?\n"
    )
    for total in (100000.5, 99999.99, 1e15, 3.0):
        kind, payload = call(_even(total))
        if kind == "ok":
            s = sum(payload.values())
            verdict = "Σ KHỚP" if s == total else f"Σ LỆCH {s - total!r}"
            print(f"   total_vnd={total!r:<12} -> {kind:<6} Σ={s!r:<22} {verdict}")
        else:
            print(f"   total_vnd={total!r:<12} -> {kind:<6} {payload}")

    print(
        "\nd) 6/12 ca ở ĐO 1 bị RECONCILIATION_MISMATCH chặn. Đó là MAY, không phải\n"
        "   phòng thủ: probe đổi MỘT ô còn các ô khác giữ int, nên tổng không khớp.\n"
        "   Một client tuần tự hoá MỌI số tiền thành float thì các số vẫn khớp nhau.\n"
    )
    consistent = [
        ("mọi ô float .0, khớp nhau", 90000.0, 60000.0, 30000.0),
        ("mọi ô float lẻ, khớp nhau", 90000.5, 60000.25, 30000.25),
    ]
    for label, total, first, second in consistent:
        expense = {
            "participants": ["a", "b"],
            "total_vnd": total,
            "items": [
                {"item_id": "i1", "amount_vnd": first, "shared_by": ["a"]},
                {"item_id": "i2", "amount_vnd": second, "shared_by": ["b"]},
            ],
            "surcharges": [],
            "discounts": [],
            "advancer_id": None,
        }
        kind, payload = call(expense)
        detail = payload
        if kind == "ok":
            total_out = sum(payload.values())
            detail = f"{payload} Σ={total_out!r} ({type(total_out).__name__})"
        print(f"   {label:<28} -> {kind:<6} {detail}")
    print(
        "\n   Đây mới là hình dạng đáng lo: không ô nào lệch ô nào, nên phép đối\n"
        "   chiếu số học không có gì để bắt. Nó chỉ còn lại luật 1, và luật 1\n"
        "   không được cưỡng chế ở đây."
    )

    print("\ne) so với ledger.require_vnd, cùng repo, cùng luật 1:\n")
    for value in (True, 100000.0):
        try:
            ledger_module.require_vnd(value)
            print(f"   require_vnd({value!r}) -> ĐI QUA")
            failures.append("ĐO 2d: require_vnd không chặn -- nền so sánh hỏng")
        except Exception as exc:  # noqa: BLE001 -- reporting the code is the point
            print(f"   require_vnd({value!r}) -> {type(exc).__name__}({exc})")
    print(
        "\nHai hàm trong CÙNG app/domain/, cùng luật 1, trả lời NGƯỢC NHAU "
        "cho cùng một giá trị."
    )


# ---------------------------------------------------------------------------
# ĐO 3 -- the HTTP boundary: how wide is the radius?
# ---------------------------------------------------------------------------


def _payload(total=82000, item_amount=None):
    body = {
        "context_id": str(CONTEXT_ID),
        "description": "Bữa tối",
        "recorded_by_id": str(ADVANCER_ID),
        "paid_by_id": str(ADVANCER_ID),
        "verification_scope": "totals_only",
        "occurred_at": "2030-08-27T12:00:00+07:00",
        "participants": [str(SENDER_ID), str(ADVANCER_ID)],
        "total_amount_vnd": total,
        "items": [],
        "surcharges": [],
        "discounts": [],
    }
    if item_amount is not None:
        body["items"] = [
            {
                "item_id": "i1",
                "amount_vnd": item_amount,
                "shared_by": [str(SENDER_ID), str(ADVANCER_ID)],
            }
        ]
    return body


def _build_client():
    """Real FastAPI app over the fake repository from tests/api/conftest.py."""
    from app.api.deps import get_repository
    from app.api.main import create_app
    from tests.api.conftest import FakeRepository

    real_run_sync = anyio.to_thread.run_sync

    async def run_sync_inline(function, *args, **kwargs):
        del kwargs
        return function(*args)

    anyio.to_thread.run_sync = run_sync_inline

    repository = FakeRepository()
    for person_id in (SENDER_ID, ADVANCER_ID):
        repository.active_memberships.add((CONTEXT_ID, person_id))
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    return app, repository, real_run_sync


def do_3_http_boundary() -> None:
    section(3, "Biên HTTP (L3): float/bool có tới được allocate() từ ngoài không?")
    app, repository, real_run_sync = _build_client()
    transport = httpx.ASGITransport(app=app)

    cases = [
        ("int 82000 (nền dương)", _payload(82000), 201),
        ("float 82000.0", _payload(82000.0), None),
        ("float 82000.5", _payload(82000.5), None),
        ("bool true", _payload(True), None),
        ("chuỗi '82000'", _payload("82000"), None),
        ("item float", _payload(82000, item_amount=82000.0), None),
    ]

    async def run():
        out = []
        async with httpx.AsyncClient(
            transport=transport, base_url="http://probe"
        ) as client:
            for label, body, _ in cases:
                response = await client.post("/expenses", json=body)
                out.append((label, response.status_code, response.text[:110]))
        return out

    try:
        results = anyio.run(run)
    finally:
        anyio.to_thread.run_sync = real_run_sync

    print(f"{'thân JSON gửi lên':<26} {'HTTP':<6} trích lỗi")
    print("-" * 86)
    baseline_ok = False
    leaked = 0
    for (label, _, expected), (_, status, text) in zip(cases, results, strict=True):
        print(f"{label:<26} {status:<6} {text[:52]}")
        if expected == 201:
            baseline_ok = status == 201
        elif status < 400:
            leaked += 1
    print()
    if not baseline_ok:
        failures.append("ĐO 3: nền dương không 201 -- phép đo hỏng, đừng đọc số dưới")
        print("!! NỀN DƯƠNG KHÔNG 201 -- phép đo này hỏng, mọi 422 dưới là vô nghĩa")
    else:
        print("Nền dương 201: máy chủ sống, route đúng, quyền qua được.")
    print(f"Số thân phi-int lọt qua biên HTTP: {leaked}/5")
    print(f"Số bản ghi khoản chi được tạo: {len(repository.expenses)} (nền dương = 1)")


# ---------------------------------------------------------------------------
# ĐO 4 -- how thick is the barrier? (passthrough measurement)
# ---------------------------------------------------------------------------


def do_4_barrier_thickness() -> None:
    section(4, "Rào dày mấy lớp? Bỏ qua pydantic rồi đo phần còn lại")
    from app.api.schemas import ExpenseInput
    from app.api.service import _allocator_input

    print(
        "`model_construct` dựng model KHÔNG chạy validator. Nó đóng vai\n"
        "'giả sử một float bằng cách nào đó qua được lớp pydantic'. Câu hỏi:\n"
        "phía sau lớp đó còn ai kiểm nữa không?\n"
    )
    proposal = ExpenseInput.model_construct(
        context_id=CONTEXT_ID,
        description="Bữa tối",
        recorded_by_id=ADVANCER_ID,
        paid_by_id=ADVANCER_ID,
        verification_scope="totals_only",
        occurred_at=None,
        participants=[SENDER_ID, ADVANCER_ID],
        total_amount_vnd=82000.5,
        items=[],
        surcharges=[],
        discounts=[],
    )
    domain_expense = _allocator_input(proposal)
    got = domain_expense["total_vnd"]
    print(f"   _allocator_input(...)['total_vnd'] = {got!r} ({type(got).__name__})")
    if type(got) is not float:
        failures.append("ĐO 4: _allocator_input đã ép kiểu -- rào dày hơn 1 lớp")
    kind, payload = call(domain_expense)
    print(f"   allocate(...) -> {kind}: {payload}")
    print(
        "\n   => giữa pydantic và allocate() KHÔNG có lớp kiểm nào nữa.\n"
        "      _allocator_input chỉ đổi tên khoá, không ép kiểu."
    )

    print("\nĐường thứ hai -- bill đã quét (allocator_input_from_bill):\n")
    bill = {
        "items": [
            {
                "item_key": "i1",
                "amount_vnd": 60000.5,
                "shares": [{"participant_id": "a", "source": "confirmed"}],
            },
            {
                "item_key": "i2",
                "amount_vnd": 30000,
                "shares": [{"participant_id": "b", "source": "confirmed"}],
            },
        ],
        "surcharges": [],
        "discounts": [],
        "printed_total_vnd": None,
        "participants": ["a", "b"],
        "advancer_id": "a",
    }
    projected = allocator_input_from_bill(bill)
    total = projected["expense"]["total_vnd"]
    print(
        f"   printed_total_vnd=None -> total_vnd cộng ra {total!r} ({type(total).__name__})"
    )
    kind, payload = call(projected["expense"])
    print(f"   allocate(...) -> {kind}: {payload}")
    print(
        "\n   => bill.py cũng là ống dẫn thuần (docstring của nó tự nói:\n"
        '      "arranges; it never computes"). Một float ở dòng món đi thẳng\n'
        "      vào tổng, rồi vào allocate()."
    )


# ---------------------------------------------------------------------------
# ĐO 5 -- which gate could have seen this?
# ---------------------------------------------------------------------------


def do_5_gate_blindness() -> None:
    section(5, "Hai cổng ĐANG gác luật 1 -- không cổng nào nhìn thấy allocator")
    from tests.test_one_money_check import SCOPE, inline_quantity_checks, scoped_files

    allocator_src = (API_ROOT / "app/domain/allocator.py").read_text(encoding="utf-8")
    print("Cổng A -- tests/test_one_money_check.py (đếm BẢN SAO của phép kiểm):")
    print(f"   SCOPE = {SCOPE}")
    in_scope = any(p.name == "allocator.py" for p in scoped_files())
    print(f"   allocator.py NẰM TRONG scope của cổng A: {in_scope}")
    print(
        f"   phép kiểm tìm thấy trong allocator.py: {inline_quantity_checks(allocator_src) or 'không có'}"
    )
    print(
        "   Cổng A khẳng định 'không ai được chép lại phép kiểm'. Một file KHÔNG\n"
        "   HỀ kiểm gì cả thoả mãn nó hoàn hảo. Vắng mặt là màu xanh.\n"
    )
    if in_scope and inline_quantity_checks(allocator_src):
        failures.append("ĐO 5: allocator.py CÓ phép kiểm -- kết luận sai")

    print("Cổng B -- tests/domain/test_ledger.py (quét float+bool từng THAM SỐ):")
    print(f"   vũ trụ của nó = ledger.__all__ ({len(ledger_module.__all__)} tên)")
    print(
        f"   'allocate' có trong ledger.__all__: {'allocate' in ledger_module.__all__}"
    )
    print(
        "   Cổng B quét đúng thứ cần quét, nhưng chỉ trong một module. allocate()\n"
        "   ở module khác nên không bao giờ vào được danh sách.\n"
    )

    print("Và cổng A sẽ CHỐNG LẠI bản vá hiển nhiên nhất:")
    natural_fix = (
        "def _validate_structure(expense):\n"
        "    for _, amount in amounts:\n"
        "        if isinstance(amount, bool) or not isinstance(amount, int):\n"
        "            raise AllocationError('X')\n"
    )
    print(f"   vá nội tuyến -> cổng A bắt được: {inline_quantity_checks(natural_fix)}")
    print(
        "   Người sửa viết phép kiểm thẳng vào allocator.py sẽ làm cổng A ĐỎ.\n"
        "   Bản vá hợp lệ phải gọi app.domain.money.vnd_violation."
    )


# ---------------------------------------------------------------------------
# ĐO 6 -- the frozen contract has no word for this failure
# ---------------------------------------------------------------------------


def do_6_no_error_code() -> None:
    section(6, "Hợp đồng ADR-0004 đông lạnh KHÔNG có mã lỗi cho 'không phải số nguyên'")
    print(f"ERROR_PRECEDENCE có {len(ERROR_PRECEDENCE)} mã:")
    for code in ERROR_PRECEDENCE:
        print(f"   {code}")
    integerish = [c for c in ERROR_PRECEDENCE if "INTEGER" in c or "TYPE" in c]
    print(f"\nmã nói về kiểu số nguyên: {integerish or 'KHÔNG CÓ'}")
    if integerish:
        failures.append("ĐO 6: có mã kiểu -- kết luận sai")
    print("\nNếu người sửa viết raise AllocationError('AMOUNT_NOT_INTEGER'):")
    try:
        raise AllocationError("AMOUNT_NOT_INTEGER")
    except AllocationError as exc:
        print(f"   -> AllocationError({exc.code}) -- đi qua, kết luận này SAI")
        failures.append("ĐO 6: mã lạ được nhận -- kết luận sai")
    except ValueError as exc:
        print(f"   -> ValueError: {exc}")
        print(
            "   Không phải AllocationError. app/api/service.py chỉ bắt\n"
            "   AllocationError, nên nó thành 500 chứ không phải 422."
        )
    print(
        "\n=> Bản vá KHÔNG nằm gọn trong từ vựng hiện có. Ba đường đi, mỗi đường\n"
        "   một cái giá, đây là quyết định của người sở hữu domain chứ không\n"
        "   phải của tôi:\n"
        "   (a) thêm mã vào ERROR_PRECEDENCE = sửa hợp đồng đã đông lạnh -> ADR;\n"
        "   (b) dùng lại một mã có sẵn -> mã nói sai chuyện gì đã xảy ra;\n"
        "   (c) chặn TRƯỚC allocator (ở service) -> allocator vẫn hở cho mọi\n"
        "       người gọi sau này, kể cả test và script."
    )


# ---------------------------------------------------------------------------
# ĐO 7 -- why 41 golden vectors never caught it
# ---------------------------------------------------------------------------


def do_7_golden_corpus() -> None:
    section(7, "41 vector golden: có vector nào dùng giá trị không phải int không?")
    root = API_ROOT / "tests/domain/golden"
    files = sorted(root.glob("*.json"))
    leaves: list[tuple[str, str, object]] = []

    def walk(node, path, name):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}", name)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]", name)
        elif isinstance(node, int | float):
            leaves.append((name, path, node))

    total_vectors = 0
    for path in files:
        vectors = json.loads(path.read_text(encoding="utf-8"))
        total_vectors += len(vectors)
        walk(vectors, "", path.name)

    non_int = [leaf for leaf in leaves if type(leaf[2]) is not int]
    print(f"file: {len(files)}   vector: {total_vectors}   lá số: {len(leaves)}")
    print(f"lá KHÔNG phải int: {len(non_int)}  {non_int[:5]}")
    if total_vectors != 41:
        failures.append(f"ĐO 7: đếm ra {total_vectors} vector, đề bài nói 41")
    codes = sorted(
        {
            vector["expect_error"]
            for path in files
            for vector in json.loads(path.read_text(encoding="utf-8"))
            if "expect_error" in vector
        }
    )
    missing = [code for code in ERROR_PRECEDENCE if code not in codes]
    print(f"\nmã lỗi được 41 vector phủ: {len(codes)}/{len(ERROR_PRECEDENCE)}")
    print(f"mã KHÔNG có vector nào: {missing}")
    print(
        "\n=> Trả lời câu hỏi 2 của đề bài: KHÔNG, không vector nào dùng giá trị\n"
        "   phi-int. Đó chính là lý do corpus không bao giờ bắt được lỗi này --\n"
        "   nó chỉ kiểm phép TÍNH trên đầu vào hợp lệ, không kiểm phép NHẬN."
    )


# ---------------------------------------------------------------------------
# ĐO 8 -- bool hunting along the money path
# ---------------------------------------------------------------------------


def do_8_bool_slots() -> None:
    section(8, "Săn bool: ô tiền nào có thể nhận True mà không ai kêu?")
    import app.api.schemas as schemas

    money_fields: list[tuple[str, str, str]] = []
    for name in dir(schemas):
        model = getattr(schemas, name)
        if not isinstance(model, type) or not hasattr(model, "model_fields"):
            continue
        for field_name, field in model.model_fields.items():
            if not field_name.endswith("_vnd"):
                continue
            money_fields.append(
                (name, field_name, str(field.annotation).replace("typing.", ""))
            )
    optional = [f for f in money_fields if "None" in f[2] or "Optional" in f[2]]
    print(f"Tổng ô tiền (*_vnd) khai trong schemas.py: {len(money_fields)}")
    print(f"Trong đó nhận None (optional): {len(optional)}")
    for model_name, field_name, annotation in optional[:12]:
        print(f"   {model_name}.{field_name}: {annotation}")

    print("\nĐo thật một ô optional với true, qua pydantic:")
    from pydantic import ValidationError

    from app.api.schemas import BillCreateRequest

    print("   (thân cố tình thiếu vài trường bắt buộc; chỉ đọc lỗi Ở ĐÚNG ô tiền)")
    for value in (True, 1000.0, 1000):
        try:
            BillCreateRequest.model_validate(
                {
                    "context_id": str(CONTEXT_ID),
                    "printed_total_vnd": value,
                    "items_total_vnd": 1000,
                    "items": [],
                }
            )
            verdict = "ĐI QUA pydantic"
        except ValidationError as exc:
            mine = [e for e in exc.errors() if e["loc"][-1] == "printed_total_vnd"]
            verdict = (
                f"ô tiền bị bắt: {mine[0]['type']}"
                if mine
                else "ô tiền KHÔNG bị bắt (chỉ lỗi ở trường khác)"
            )
        print(f"   printed_total_vnd={value!r:<10} -> {verdict}")

    print("\nCòn ở tầng domain, cùng ô đó, không qua pydantic:")
    bill = {
        "items": [
            {
                "item_key": "i1",
                "amount_vnd": 60000,
                "shares": [{"participant_id": "a", "source": "confirmed"}],
            }
        ],
        "surcharges": [],
        "discounts": [],
        "printed_total_vnd": True,
        "participants": ["a"],
        "advancer_id": "a",
    }
    projected = allocator_input_from_bill(bill)
    print(
        f"   allocator_input_from_bill(printed_total_vnd=True) -> total_vnd={projected['expense']['total_vnd']!r}"
    )
    kind, payload = call(projected["expense"])
    print(f"   allocate(...) -> {kind}: {payload}")
    print(
        "\n   RECONCILIATION_MISMATCH ở đây là MAY, không phải phòng thủ: nó bắt\n"
        "   được chỉ vì 1 != 60000. Đo luôn hình dạng mà nó KHÔNG bắt được --\n"
        "   một bill mà con số True tự khớp với chính nó:\n"
    )
    self_consistent = {
        "items": [
            {
                "item_key": "i1",
                "amount_vnd": True,
                "shares": [{"participant_id": "a", "source": "confirmed"}],
            }
        ],
        "surcharges": [],
        "discounts": [],
        "printed_total_vnd": True,
        "participants": ["a", "b"],
        "advancer_id": "a",
    }
    projected = allocator_input_from_bill(self_consistent)
    kind, payload = call(projected["expense"])
    print(f"   bill 1 món, amount=True, printed_total=True -> {kind}: {payload}")
    if kind != "ok":
        failures.append("ĐO 8: ca True tự khớp bị chặn -- kết luận cần viết lại")
    else:
        print(
            "   => đi lọt. Đối chiếu số học chỉ so số với số; nó không có ý kiến\n"
            "      gì về việc con số đó là một lá cờ boolean."
        )


def main() -> int:
    print(RULE)
    print("KIỂM ĐỘC LẬP: luật 1 (số nguyên đồng) dọc ĐƯỜNG ĐI CỦA MỘT SỐ TIỀN")
    print("trục đo: route -> schema -> service -> allocator (không đếm call site)")
    print(RULE)
    do_1_allocator_layer()
    do_2_the_money_is_wrong()
    do_3_http_boundary()
    do_4_barrier_thickness()
    do_5_gate_blindness()
    do_6_no_error_code()
    do_7_golden_corpus()
    do_8_bool_slots()

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
