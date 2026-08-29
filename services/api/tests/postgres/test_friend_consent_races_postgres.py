"""rd-qa-36 · Hai chỗ đồ thị bạn bè hở khi có hơn một yêu cầu cùng lúc.

`test_friend_requests_postgres.py` chứng minh `uq_friend_edge_live` bằng hai lời
gọi **tuần tự trong cùng một session**. Điều đó chứng minh chỉ mục tồn tại và
bắn. Nó không chạm được câu hỏi khác: hai yêu cầu HTTP **riêng biệt**, mỗi cái
một transaction, cùng đọc một cạnh rồi cùng ghi đè lên nó.

Hai ca dưới đây là hai lỗ đo được trên máy chủ thật (uvicorn + PostgreSQL,
`POST /friends/requests/{id}/respond`), viết lại thành dạng tất định không cần
luồng: thứ tự đọc-ghi được đặt bằng tay, đúng dãy mà service thực hiện
(`get_friend_request` → domain `decide` → `decide_friend_request`).

Đo trên máy chủ sống trước khi viết file này:

* chặn-đấu-với-đồng-ý: 40 lượt chạy thật đồng thời (`threading.Barrier`),
  **18/40 lượt** kết thúc ở `accepted` dù lời gọi block đã trả về `200` với
  `state: "blocked"`; **40/40** lượt cả hai lời gọi cùng trả `200`.
* chặn một hàng `declined` cũ khi cặp đã có hàng `pending` mới:
  `500 Internal Server Error`, `uq_friend_edge_live` nổ ra ngoài mọi handler.

Cả hai đều nằm ở `SqlAlchemyApiRepository.decide_friend_request`: nó khoá hàng
bằng `with_for_update()` rồi **ghi đè trạng thái mà không đọc lại xem trạng thái
đó còn là cái domain vừa duyệt hay không**. Khoá xếp hàng hai lượt ghi; nó không
kiểm lượt ghi thứ hai còn hợp lệ nữa không.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.errors import RepositoryConflict
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import FriendRequest, Person
from app.domain.friendship import decide as decide_friendship

NOW = datetime(2030, 8, 29, 12, tzinfo=UTC)


@pytest.fixture
def two_connections(postgres_engine: Engine) -> Iterator[tuple[Session, Session]]:
    """Hai session độc lập — hai transaction, đúng như hai yêu cầu HTTP.

    Một session duy nhất không diễn tả được lỗi này: trong cùng transaction lượt
    đọc thứ hai đã nhìn thấy lượt ghi thứ nhất, nên TOCTOU biến mất và ca test
    xanh trong khi sản phẩm hỏng — chính hình dạng
    [[live-client-postgres-che-loi-thu-tu-commit]] cảnh báo.
    """
    first = Session(postgres_engine, expire_on_commit=False)
    second = Session(postgres_engine, expire_on_commit=False)
    try:
        yield first, second
    finally:
        first.rollback()
        second.rollback()
        # Ca này COMMIT thật, nên phải dọn CHÍNH XÁC những hàng nó tạo: tầng
        # postgres dùng chung một schema, và một hàng thừa làm đỏ ca đếm hàng ở
        # file khác — [[tests-postgres-dung-chung-mot-schema]].
        with Session(postgres_engine) as cleanup:
            cleanup.execute(
                delete(FriendRequest).where(FriendRequest.requester_id.in_(_CREATED))
            )
            cleanup.execute(delete(Person).where(Person.id.in_(_CREATED)))
            cleanup.commit()
        _CREATED.clear()
        first.close()
        second.close()


#: Id của mọi người ca này tạo, để dọn đúng chúng chứ không dọn cả bảng.
_CREATED: list[uuid.UUID] = []


def _two_people(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    anh = Person(id=uuid.uuid4(), display_name="Anh")
    binh = Person(id=uuid.uuid4(), display_name="Bình")
    session.add_all([anh, binh])
    session.commit()
    _CREATED.extend([anh.id, binh.id])
    return anh.id, binh.id


def test_a_block_survives_an_accept_that_was_decided_on_a_stale_read(
    two_connections: tuple[Session, Session],
):
    """Người GỬI bấm chặn, người NHẬN bấm đồng ý — cái chặn phải thắng.

    Chưa có nút "rút lại lời mời" (PR #196 tự khai), nên `block` là cánh cửa duy
    nhất để người gửi gỡ một lời mời gửi nhầm người. Nếu một lượt đồng ý đến
    cùng lúc xoá được cái chặn đó, sản phẩm nói với người dùng "đã chặn" (200,
    `state: "blocked"`) rồi vẫn đưa họ vào danh sách bạn của người kia.

    `app/domain/friendship.py` viết thẳng: "BLOCKED *is* terminal, because that
    is what the word is for", và `test_accepting_is_not_possible_after_a_block`
    ở tầng domain giữ đúng câu đó — **trong một thế giới một luồng**. Ca này hỏi
    câu ấy ở nơi nó thật sự được quyết định: hai transaction.
    """
    first, second = two_connections
    requester, addressee = _two_people(first)
    repo_first = SqlAlchemyApiRepository(first)
    edge = repo_first.open_friend_request(
        requester_id=requester, addressee_id=addressee, now=NOW
    )
    first.commit()

    # Hai yêu cầu HTTP đến cùng lúc. Mỗi cái đọc cạnh bằng transaction của mình,
    # và cả hai đều thấy `pending` — chưa lượt nào ghi gì.
    seen_by_blocker = repo_first.get_friend_request(edge.id, requester)
    seen_by_accepter = SqlAlchemyApiRepository(second).get_friend_request(
        edge.id, addressee
    )
    assert seen_by_blocker.state == "pending"
    assert seen_by_accepter.state == "pending"

    # Domain duyệt cả hai, vì mỗi bên được đưa cho một cạnh `pending` thật.
    blocked = decide_friendship(
        edge={
            "requester_id": str(requester),
            "addressee_id": str(addressee),
            "state": seen_by_blocker.state,
        },
        actor_id=str(requester),
        decision="block",
    )
    accepted = decide_friendship(
        edge={
            "requester_id": str(requester),
            "addressee_id": str(addressee),
            "state": seen_by_accepter.state,
        },
        actor_id=str(addressee),
        decision="accept",
    )
    assert blocked["state"] == "blocked"
    assert accepted["state"] == "accepted"

    # Lượt chặn ghi trước và đóng transaction: người gửi đã nhận `200 blocked`.
    repo_first.decide_friend_request(
        request_id=edge.id,
        state=blocked["state"],
        decided_by_id=requester,
        now=NOW,
    )
    first.commit()

    # Lượt đồng ý ghi sau. Nó đã được duyệt trên một lần đọc GIỜ ĐÃ CŨ, nên đây
    # là chỗ duy nhất còn có thể từ chối nó.
    #
    # Ca này KHÔNG quy định cách sửa: từ chối có tên, ghi không ăn, hay bất cứ
    # cách nào khác đều được — điều bị khẳng định là trạng thái cuối, ở dưới.
    repo_second = SqlAlchemyApiRepository(second)
    try:
        repo_second.decide_friend_request(
            request_id=edge.id,
            state=accepted["state"],
            decided_by_id=addressee,
            now=NOW,
        )
        second.commit()
    except RepositoryConflict:
        second.rollback()

    with Session(first.get_bind(), expire_on_commit=False) as reader:
        final = SqlAlchemyApiRepository(reader)
        assert final.get_friend_request(edge.id, requester).state == "blocked", (
            "một lượt đồng ý duyệt trên bản đọc cũ đã ghi đè lên lệnh chặn"
        )
        assert final.list_friends(requester) == [], (
            "người gửi đang là bạn của chính người họ vừa chặn"
        )


def test_blocking_a_stale_declined_request_is_refused_not_a_crash(
    two_connections: tuple[Session, Session],
):
    """Chặn một lời mời CŨ đã bị từ chối, khi cặp đã có lời mời mới.

    Đường đi hoàn toàn bình thường của người dùng: Dũng mời Em, Em từ chối, Dũng
    mời lại, rồi Dũng chặn cái thông báo cũ vẫn còn trong máy mình. `open_...`
    bắt `IntegrityError` và đổi thành `RepositoryConflict`; `decide_...`
    **không** bắt gì cả, nên `uq_friend_edge_live` nổ thẳng ra
    `ServerErrorMiddleware` — đo được trên máy chủ sống là
    `500 Internal Server Error`, thân `text/plain`, ngoài mọi middleware.

    Ca này không quy định cách sửa: nó chỉ đòi một lời từ chối có tên
    (`RepositoryConflict`, thứ service đã biết đổi thành 409) thay vì một ngoại
    lệ chưa ai bắt.
    """
    first, _second = two_connections
    requester, addressee = _two_people(first)
    repository = SqlAlchemyApiRepository(first)

    stale = repository.open_friend_request(
        requester_id=requester, addressee_id=addressee, now=NOW
    )
    repository.decide_friend_request(
        request_id=stale.id, state="declined", decided_by_id=addressee, now=NOW
    )
    first.commit()

    # Bị từ chối một lần không phải án chung thân — hàng declined nhường chỗ.
    repository.open_friend_request(
        requester_id=requester, addressee_id=addressee, now=NOW
    )
    first.commit()

    with pytest.raises(RepositoryConflict):
        repository.decide_friend_request(
            request_id=stale.id,
            state="blocked",
            decided_by_id=requester,
            now=NOW,
        )
