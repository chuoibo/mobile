"""Run each non-pydantic source and record what actually reaches `allocate()`.

`dan_xuat_nguon.py` derives NINE sources statically and says five of them never
cross a `MoneyVnd` annotation. Reading that off the AST is not the same as
watching a bad value travel, so this probe drives the four DB sources and the one
computed source for real and prints what comes out the far end.

The HTTP source (`POST /expenses`, four pydantic fields) is deliberately NOT
re-measured here: qa2 already drove all five HTTP paths at #452 and none let a
float or a bool through. Repeating a measurement someone else has already made
buys nothing; the axis nobody had walked is the one that starts at the database.

What each leg answers:

  B2  a writer that does NOT go through `POST /bills` puts a float in a bill row.
      Does PostgreSQL refuse it, round it, or store it? What does `allocate()`
      then divide?
  B3  the same write against the fake repository the API suite runs on -- to see
      what that suite would and would not have noticed.
  C   `allocator_input_from_bill` adds the lines up when no printed total was
      read. That sum is a money value with no annotation anywhere on it.
  D   whether pydantic validates a DEFAULT, i.e. whether a money field with a
      default would be a barrier at all.

Run:  cd services/api && python3 tests/qa/backend-092115-nguon-tien-vao-allocate/probe_nguon_tien.py
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import sys
import uuid
from datetime import UTC, datetime

API_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.api.repository import SqlAlchemyApiRepository  # noqa: E402
from app.domain.allocator import allocate  # noqa: E402
from app.domain.bill import allocator_input_from_bill  # noqa: E402

NOW = datetime(2026, 8, 31, 3, 0, tzinfo=UTC)
DATABASE_URL_ENV = "MOBILE_TEST_DATABASE_URL"


def title(number: str, text: str) -> None:
    print()
    print("=" * 78)
    print(f"CHẶNG {number} — {text}")
    print("=" * 78)


def run_allocate(expense: dict):
    """Return ('ok', allocations) | ('refused', code) | ('crash', repr).

    `refused` is the allocator answering with a contract code. `crash` is any
    other exception: money that produced a 500 rather than an answer.
    """
    try:
        return ("ok", allocate(expense)["allocations"])
    except Exception as exc:  # noqa: BLE001 -- classifying, not handling
        code = getattr(exc, "code", None)
        if code is not None:
            return ("refused", code)
        return ("crash", f"{type(exc).__name__}: {exc}")


def bill_dict(items, *, printed_total_vnd, participants, surcharges=(), discounts=()):
    """The exact shape `split_bill` hands to `allocator_input_from_bill`."""
    return {
        "participants": list(participants),
        "printed_total_vnd": printed_total_vnd,
        "items": [
            {
                "item_key": key,
                "amount_vnd": amount,
                "shares": [{"participant_id": p, "source": "confirmed"} for p in who],
            }
            for key, amount, who in items
        ],
        "surcharges": list(surcharges),
        "discounts": list(discounts),
        "advancer_id": participants[0],
    }


# --------------------------------------------------------------------------
# B2 -- a real PostgreSQL row written by something that is not POST /bills
# --------------------------------------------------------------------------


@contextlib.contextmanager
def postgres_engine():
    """Same recipe as tests/postgres/conftest.py: own schema, Alembic, drop after."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    raw = os.environ.get(DATABASE_URL_ENV)
    if raw is None:
        yield None
        return

    url = make_url(raw)
    schema = f"nguon_probe_{uuid.uuid4().hex[:12]}"
    admin = create_engine(url, pool_pre_ping=True, hide_parameters=True)
    engine = None
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        scoped = url.update_query_dict(
            {"options": f"-csearch_path={schema}"}, append=False
        )
        previous = os.environ.get("MOBILE_DATABASE_URL")
        os.environ["MOBILE_DATABASE_URL"] = scoped.render_as_string(hide_password=False)
        try:
            command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")
        finally:
            if previous is None:
                os.environ.pop("MOBILE_DATABASE_URL", None)
            else:
                os.environ["MOBILE_DATABASE_URL"] = previous
        engine = create_engine(scoped, pool_pre_ping=True, hide_parameters=True)
        with engine.connect() as connection:
            assert connection.scalar(text("select current_schema()")) == schema
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        admin.dispose()


def leg_b2() -> None:
    from sqlalchemy.orm import Session

    from app.db.models import Context, Person

    title(
        "B2",
        "PostgreSQL THẬT: một người ghi bill KHÔNG qua POST /bills",
    )
    print(
        "Bốn nguồn DB_RECORD không có rào nào KHI ĐỌC — chúng là dataclass frozen.\n"
        "Rào duy nhất trên đường đó là rào lúc GHI, ở một request KHÁC, sớm hơn.\n"
        "Câu hỏi: nếu người ghi không đi qua request đó thì còn gì chặn?\n"
    )

    with postgres_engine() as engine:
        if engine is None:
            print(f"KHÔNG ĐO ĐƯỢC — thiếu {DATABASE_URL_ENV}")
            return

        for label, overrides in (
            ("line_total_vnd = 1500.5 (float)", {"line_total_vnd": 1500.5}),
            ("line_total_vnd = True (bool)", {"line_total_vnd": True}),
            ("printed_total_vnd = 135000.7 (float)", {"printed_total_vnd": 135000.7}),
        ):
            with Session(engine, expire_on_commit=False) as session:
                repository = SqlAlchemyApiRepository(session)
                creator = Person(display_name="Người ghi thẳng")
                an = Person(display_name="An")
                binh = Person(display_name="Bình")
                session.add_all([creator, an, binh])
                session.flush()
                context_id = uuid.uuid4()
                session.add(
                    Context(
                        id=context_id,
                        display_name="Nhóm probe",
                        created_by_id=creator.id,
                    )
                )
                session.flush()

                items = [
                    {
                        "item_key": "i1",
                        "name": "Phở",
                        "quantity": 1,
                        "unit_price_vnd": 65000,
                        "line_total_vnd": 65000,
                        "position": 0,
                        "suggested_participant_ids": [an.id],
                    },
                    {
                        "item_key": "i2",
                        "name": "Bún chả",
                        "quantity": 1,
                        "unit_price_vnd": 70000,
                        "line_total_vnd": 70000,
                        "position": 1,
                        "suggested_participant_ids": [binh.id],
                    },
                ]
                payload = {
                    "context_id": context_id,
                    "created_by_id": creator.id,
                    "printed_total_vnd": 135000,
                    "items_total_vnd": 135000,
                    "confidence": 88,
                    "needs_review": False,
                    "items": items,
                    "surcharges": [],
                    "discounts": [],
                    "now": NOW,
                }
                if "line_total_vnd" in overrides:
                    items[0]["line_total_vnd"] = overrides["line_total_vnd"]
                else:
                    payload.update(overrides)

                print(f"-- {label}")
                try:
                    record = repository.create_bill(**payload)
                    session.commit()
                except Exception as exc:  # noqa: BLE001 -- classifying, not handling
                    session.rollback()
                    line = str(exc).strip().splitlines()[0]
                    print(f"   GHI BỊ TỪ CHỐI: {type(exc).__name__}: {line[:160]}")
                    print()
                    continue

                reread = repository.get_bill(record.id)
                stored = [
                    (
                        item.item_key,
                        item.line_total_vnd,
                        type(item.line_total_vnd).__name__,
                    )
                    for item in reread.items
                ]
                print(
                    f"   GHI ĐƯỢC. Đọc lại: printed_total_vnd={reread.printed_total_vnd!r}"
                )
                print(f"                    items={stored}")

                projection = allocator_input_from_bill(
                    bill_dict(
                        [
                            (item.item_key, item.line_total_vnd, [str(an.id)])
                            if item.item_key == "i1"
                            else (item.item_key, item.line_total_vnd, [str(binh.id)])
                            for item in reread.items
                        ],
                        printed_total_vnd=reread.printed_total_vnd,
                        participants=[str(an.id), str(binh.id)],
                    )
                )
                kind, payload_out = run_allocate(projection["expense"])
                print(f"   allocate() -> {kind}: {payload_out}")
                print()


def leg_b2b() -> None:
    """The same rounding, with nothing left to make it visible.

    Above, RECONCILIATION_MISMATCH masked the rounding: the lines no longer added
    up to the printed total, so the allocator refused for an unrelated reason.
    Take the printed total away -- `allocator_input_from_bill` then defines the
    total as the sum of the lines -- and the bill is self-consistent again. The
    allocation succeeds, and the money it returns is not the money that was written.
    """
    from sqlalchemy.orm import Session

    from app.db.models import Context, Person

    title("B2b", "Cùng phép làm tròn, nhưng không còn gì che nó")

    with postgres_engine() as engine:
        if engine is None:
            print(f"KHÔNG ĐO ĐƯỢC — thiếu {DATABASE_URL_ENV}")
            return

        written = [("i1", 1500.5), ("i2", 1501.5)]
        with Session(engine, expire_on_commit=False) as session:
            repository = SqlAlchemyApiRepository(session)
            creator = Person(display_name="Người ghi thẳng")
            an = Person(display_name="An")
            binh = Person(display_name="Bình")
            session.add_all([creator, an, binh])
            session.flush()
            context_id = uuid.uuid4()
            session.add(
                Context(
                    id=context_id,
                    display_name="Nhóm probe",
                    created_by_id=creator.id,
                )
            )
            session.flush()
            record = repository.create_bill(
                context_id=context_id,
                created_by_id=creator.id,
                printed_total_vnd=None,
                items_total_vnd=3002,
                confidence=88,
                needs_review=False,
                items=[
                    {
                        "item_key": key,
                        "name": key,
                        "quantity": 1,
                        "unit_price_vnd": None,
                        "line_total_vnd": amount,
                        "position": position,
                        "suggested_participant_ids": [],
                    }
                    for position, (key, amount) in enumerate(written)
                ],
                surcharges=[],
                discounts=[],
                now=NOW,
            )
            session.commit()
            reread = repository.get_bill(record.id)

            print(
                f"   ghi   : {written}  (tổng ý định = {sum(a for _k, a in written)})"
            )
            print(
                f"   đọc lại: {[(i.item_key, i.line_total_vnd) for i in reread.items]}"
                f"  (tổng thật = {sum(i.line_total_vnd for i in reread.items)})"
            )
            projection = allocator_input_from_bill(
                bill_dict(
                    [
                        (
                            reread.items[0].item_key,
                            reread.items[0].line_total_vnd,
                            [str(an.id)],
                        ),
                        (
                            reread.items[1].item_key,
                            reread.items[1].line_total_vnd,
                            [str(binh.id)],
                        ),
                    ],
                    printed_total_vnd=None,
                    participants=[str(an.id), str(binh.id)],
                )
            )
            kind, payload = run_allocate(projection["expense"])
            print(f"   allocate() -> {kind}: {payload}")
            print(
                "\n   1500.5 -> 1500 và 1501.5 -> 1502: làm tròn NỬA VỀ CHẴN, không phải\n"
                "   làm tròn lên. Không có lỗi, không có cảnh báo, không có mã nào trả về."
            )


def leg_b3() -> None:
    title("B3", "Fake repository của tests/api — cùng phép ghi, không có rào nào")
    print(
        "Bộ test API chạy trên fake này. Nó không có kiểu cột, không có CHECK.\n"
        "Đây là lý do một dấu xanh ở tầng đó không nói gì về tầng persistence.\n"
    )
    import importlib

    module = importlib.import_module("tests.api.conftest")
    print(
        f"   FakeRepository.create_bill có kiểm kiểu không? -> {_fake_checks(module)}"
    )

    repository = module.FakeRepository()
    record = repository.create_bill(
        context_id=uuid.uuid4(),
        created_by_id=uuid.uuid4(),
        printed_total_vnd=135000.7,
        items_total_vnd=135000,
        confidence=88,
        needs_review=False,
        items=[
            {
                "item_key": "i1",
                "name": "Phở",
                "quantity": 1,
                "unit_price_vnd": None,
                "line_total_vnd": 1500.5,
                "position": 0,
                "suggested_participant_ids": [],
            }
        ],
        surcharges=[],
        discounts=[],
        now=NOW,
    )
    stored = repository.get_bill(record.id)
    print(
        f"   Ghi 1500.5 / 135000.7 -> đọc lại "
        f"{stored.items[0].line_total_vnd!r} / {stored.printed_total_vnd!r}"
    )
    print(
        "   => fake giữ NGUYÊN float. Postgres làm tròn. Hai tầng trả hai số khác nhau\n"
        "      cho cùng một phép ghi, nên một dấu xanh ở tầng fake không nói gì về tầng kia."
    )


def _fake_checks(module) -> str:
    import inspect

    source = inspect.getsource(module.FakeRepository.create_bill)
    for needle in ("isinstance", "vnd_violation", "raise TypeError"):
        if needle in source:
            return f"CÓ ({needle})"
    return "KHÔNG — lưu nguyên xi thứ được đưa vào"


def leg_c() -> None:
    title("C", "Nguồn COMPUTED: tổng do domain tự cộng khi không đọc được tổng in")
    print(
        "app/domain/bill.py:103-107. Không có annotation nào trên giá trị này;\n"
        "kiểu của nó là kiểu của các số hạng.\n"
    )
    for label, amounts in (
        ("các dòng đều int", [65000, 70000]),
        ("một dòng là float", [65000.5, 70000]),
        ("một dòng là bool", [True, 70000]),
    ):
        projection = allocator_input_from_bill(
            bill_dict(
                [("i1", amounts[0], ["an"]), ("i2", amounts[1], ["binh"])],
                printed_total_vnd=None,
                participants=["an", "binh"],
            )
        )
        total = projection["expense"]["total_vnd"]
        kind, payload = run_allocate(projection["expense"])
        print(f"-- {label}")
        print(f"   total_vnd tự cộng = {total!r} ({type(total).__name__})")
        print(f"   allocate() -> {kind}: {payload}")
        print()


def leg_d() -> None:
    import ast

    from pydantic import BaseModel

    from app.api.schemas import MoneyVnd

    title("D", "Giá trị mặc định trong schema: pydantic có kiểm không?")

    class Thu(BaseModel):
        x: MoneyVnd = 0.5  # noqa: RUF100 -- the point of the probe

    from_default = Thu().x
    print(
        f"   Thu().x (dùng mặc định) = {from_default!r} ({type(from_default).__name__})"
    )
    try:
        Thu(x=0.5)
        sent = "NHẬN"
    except Exception as exc:  # noqa: BLE001 -- classifying, not handling
        sent = f"TỪ CHỐI ({type(exc).__name__})"
    print(f"   Thu(x=0.5) (gửi vào)    = {sent}")
    print(
        "\n   => cùng một annotation: từ chối khi được GỬI, nhận khi là MẶC ĐỊNH.\n"
        "      pydantic 2 không kiểm default trừ khi validate_default=True.\n"
    )

    source = (API_ROOT / "app" / "api" / "schemas.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    with_default = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                if (
                    isinstance(statement, ast.AnnAssign)
                    and statement.value is not None
                    and isinstance(statement.target, ast.Name)
                    and statement.target.id.endswith("_vnd")
                ):
                    with_default.append(
                        f"{node.name}.{statement.target.id} = "
                        f"{ast.get_source_segment(source, statement.value)}"
                    )
    print(
        f"   Trường tiền CÓ giá trị mặc định trong schemas.py hôm nay: {len(with_default)}"
    )
    for entry in with_default:
        print(f"      {entry}")
    print(
        "\n   Không cái nào nằm trên đường tới allocate() (xem bảng của dan_xuat_nguon.py).\n"
        "   Nên đây là lỗ NGỦ: chưa mở, và không cổng nào sẽ kêu vào ngày nó mở."
    )


def main() -> int:
    print("PROBE NGUỒN TIỀN VÀO allocate() — đo tại cf16166 (= origin/main)")
    leg_b2()
    leg_b2b()
    leg_b3()
    leg_c()
    leg_d()
    return 0


if __name__ == "__main__":
    sys.exit(main())
