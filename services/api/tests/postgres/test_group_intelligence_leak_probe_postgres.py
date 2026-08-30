"""Probe QA cho PR #301 (F31/F33/F36): rò rỉ giữa các nhóm, đo bằng SỐ BẢN GHI.

Vì sao file này tồn tại bên cạnh `test_group_intelligence_postgres.py`
------------------------------------------------------------------------
File của tác giả đã có ca "người lạ bị từ chối", và những ca đó đúng. Nhưng
phép khẳng định của chúng là `assert "BBQ" not in response.text` -- một cây
kim bằng chữ. Cây kim chỉ chứng minh được *chuỗi đó* vắng mặt; nó im lặng khi
thân phản hồi mang đúng dữ liệu của nhóm kia dưới một cái tên khác, dưới id,
dưới con số, hoặc dưới một trường thêm vào sau này. `404 thân rỗng` và
`404 thân đầy dữ liệu đọc` y hệt nhau ở một assert status, và gần y hệt nhau
ở một assert needle.

Nên mỗi lần từ chối ở đây được đo ba cách độc lập:

1. **Status** -- 403.
2. **Cấu trúc** -- không một khoá mang dữ liệu nào có mặt trong thân.
3. **Định lượng** -- `_leak_measure(...) == 0`, đếm số bản ghi và số đếm mà
   thân phản hồi mang theo.

Và -- đây mới là phần làm ba con số trên có nghĩa -- mỗi lần từ chối đi kèm
một **đối chứng dương**: chính thành viên của nhóm đó gọi đúng đường dẫn đó,
đo bằng đúng `_leak_measure` đó, và phải ra **khác 0**. Không có đối chứng
dương thì "đo được 0" không phân biệt được "đã gác" với "route gõ sai đường
dẫn", "route chưa đăng ký", hay "extractor của tôi đọc nhầm khoá và luôn trả
0". Một cổng in ra số 0 của chính phép đo mù là kiểu hỏng đắt nhất ở repo này.

Bảng đường dẫn ở dưới tự kiểm với `app.routes`: một route F31/F33/F36 thêm
vào sau mà không có ở đây sẽ làm `test_the_probe_table_covers_every_feature_route`
đỏ. Danh sách viết tay không tự biết mình thiếu.

Uses `flush`, never `commit`: `postgres_session` rolls back per test, and this
directory's schema is shared with row-counting tests that go red if rows from
here survive.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import anyio
import httpx
import pytest
from sqlalchemy.orm import Session

from app.api.deps import get_contextual_suggester, get_repository, get_suggester
from app.api.main import create_app
from app.api.repository import SqlAlchemyApiRepository
from app.db.models import Context, Memory, MemoryKind, Person

from .test_group_intelligence_postgres import (
    CAFE,
    GRILL,
    PLAY,
    _checkin,
    _Client,
    _group,
    _headers,
    _http,
    _join,
    _outing,
    _person,
    _photo,
    _say,
)
from .test_repository_postgres import GUEST_TOKEN, NOW, _persist_lifecycle
from .test_suggestion_postgres import CAFE as CAFE_ID
from .test_suggestion_postgres import NUONG, FakeSuggester, _card

pytestmark = pytest.mark.postgres


def _app(session: Session, monkeypatch: pytest.MonkeyPatch):
    """The app with BOTH model backends stubbed to return a grounded card.

    Stubbing them to *succeed* is deliberate. A suggester that returns `None`
    would make every card empty, and an empty card is indistinguishable from a
    card the permission gate refused -- the refusal tests below would pass
    against a completely open endpoint. With a real card behind the gate, a
    bypass has something to leak, so `measure == 0` means the gate held rather
    than that there was nothing there.
    """

    app = _http(session, monkeypatch)
    card = _card(NUONG, CAFE_ID)
    app.dependency_overrides[get_suggester] = lambda: FakeSuggester(card)
    app.dependency_overrides[get_contextual_suggester] = lambda: FakeSuggester(card)
    return app


# --------------------------------------------------------------------------
# Phép đo: bao nhiêu bản ghi của nhóm kia thực sự đi ra theo thân phản hồi
# --------------------------------------------------------------------------


def _preference_measure(body: dict) -> int:
    sections = body.get("sections") or []
    return (
        int(body.get("checkin_count") or 0)
        + int(body.get("outing_count") or 0)
        + len(sections)
        + sum(len(section.get("tastes") or []) for section in sections)
    )


def _suggestion_measure(body: dict) -> int:
    return len(body.get("stops") or []) + (1 if body.get("title") else 0)


def _contextual_measure(body: dict) -> int:
    basis = body.get("basis") or {}
    return (
        int(basis.get("message_count") or 0)
        + int(basis.get("speaker_count") or 0)
        + int(basis.get("member_count") or 0)
        + len(body.get("stops") or [])
    )


def _album_list_measure(body: dict) -> int:
    albums = body.get("albums") or []
    return len(albums) + sum(
        int(album.get("photo_count") or 0)
        + int(album.get("checkin_count") or 0)
        + (1 if album.get("cover") else 0)
        for album in albums
    )


def _album_measure(body: dict) -> int:
    return (
        len(body.get("photos") or [])
        + len(body.get("places") or [])
        + len(body.get("highlights") or [])
        + int(body.get("photo_count") or 0)
        + int(body.get("checkin_count") or 0)
    )


class _Route:
    """One probed route: how to build its path, measure it, and name its data.

    `data_keys` is the structural half of the assertion. A refusal must not
    merely carry zeroes in these fields -- the fields must be absent, because
    a body shaped like the success response is a body one bug away from being
    filled in.
    """

    def __init__(self, name, template, measure, data_keys):
        self.name = name
        self.template = template
        self.measure = measure
        self.data_keys = frozenset(data_keys)

    def path(self, context_id, outing_id=None) -> str:
        return self.template.format(context_id=context_id, outing_id=outing_id)


ROUTES = (
    _Route(
        "preference-profile",
        "/contexts/{context_id}/preference-profile",
        _preference_measure,
        ("sections", "checkin_count", "outing_count", "split_total_vnd"),
    ),
    _Route(
        "suggestion",
        "/contexts/{context_id}/suggestion",
        _suggestion_measure,
        ("stops", "title", "when_text"),
    ),
    _Route(
        "contextual-suggestion",
        "/contexts/{context_id}/contextual-suggestion",
        _contextual_measure,
        ("basis", "stops", "title", "when_text"),
    ),
    _Route(
        "albums",
        "/contexts/{context_id}/albums",
        _album_list_measure,
        ("albums",),
    ),
    _Route(
        "album",
        "/contexts/{context_id}/albums/{outing_id}",
        _album_measure,
        ("photos", "places", "highlights", "photo_count", "split_total_vnd"),
    ),
)

_FEATURE_MARKERS = ("preference-profile", "suggestion", "albums")


def _seed_group_with_everything(session: Session, name: str):
    """A group carrying data for all five routes at once.

    Every route needs a different row to have something to leak, and the
    point of the probe is that one outsider request touches all of them.
    """

    context, owner = _group(session, name)
    friend = _person(session, f"Bạn {name}")
    _join(session, context, friend)
    _checkin(session, context, owner, GRILL)
    _checkin(session, context, friend, CAFE)
    _checkin(session, context, owner, PLAY)
    _say(session, context, owner, "bí mật của nhóm này")
    _say(session, context, friend, "đừng kể ai nhé")
    outing = _outing(session, context, owner, f"Chuyến của {name}")
    photo = _photo(session, context, owner)
    return context, owner, friend, outing, photo


def _needles(context, outing, photo) -> tuple[str, ...]:
    """Strings that exist only inside this group."""

    return (
        str(context.id),
        str(outing.id),
        str(photo.id),
        photo.image_url,
        outing.title,
        "bí mật của nhóm này",
        "đừng kể ai nhé",
        GRILL["name"],
    )


# --------------------------------------------------------------------------
# 1 -- người của nhóm A gọi ba tính năng với context_id của nhóm B
# --------------------------------------------------------------------------


class TestCrossGroupRefusalCarriesNoRecords:
    def test_the_probe_table_covers_every_feature_route(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Bảng trên phải khớp với route thật của app, không phải với trí nhớ.

        Một route F31/F33/F36 thêm vào sau này mà không ai thêm vào `ROUTES`
        sẽ không được probe nào chạm tới, và mọi ca dưới vẫn xanh. Ca này là
        thứ duy nhất biến "thiếu" thành "đỏ".
        """

        app = _app(postgres_session, monkeypatch)
        live = {
            route.path
            for route in app.routes
            if getattr(route, "path", "").startswith("/contexts/")
            and any(marker in route.path for marker in _FEATURE_MARKERS)
            and "GET" in (getattr(route, "methods", None) or set())
        }
        probed = {route.template for route in ROUTES}

        assert live, "không tìm thấy route F31/F33/F36 nào trên app"
        assert live == probed, (
            f"probe không phủ hết route: thiếu {sorted(live - probed)}, "
            f"thừa {sorted(probed - live)}"
        )

    @pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.name)
    def test_a_member_of_another_group_reads_nothing(
        self,
        route: _Route,
        postgres_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """403 VÀ không một bản ghi nào, đo bằng chính extractor của route.

        Kẻ gọi ở đây không phải người lạ không có gì: họ là thành viên ACTIVE
        thật của nhóm A, có header hợp lệ, có cả hai role. Thứ duy nhất họ
        không có là hàng membership trong nhóm B.
        """

        victim, _, _, victim_outing, victim_photo = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )
        _, intruder = _group(postgres_session, "Nhóm A")

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            response = client.get(
                route.path(victim.id, victim_outing.id),
                headers=_headers(intruder.id),
            )

        assert response.status_code == 403, (
            f"{route.name}: chờ 403, nhận {response.status_code} -- {response.text}"
        )

        body = response.json()
        leaked_keys = route.data_keys & set(body)
        assert not leaked_keys, f"{route.name}: thân từ chối mang khoá {leaked_keys}"

        assert route.measure(body) == 0, (
            f"{route.name}: thân từ chối mang {route.measure(body)} bản ghi"
        )

        for needle in _needles(victim, victim_outing, victim_photo):
            assert needle not in response.text, (
                f"{route.name}: thân từ chối chứa {needle!r}"
            )

    @pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.name)
    def test_the_same_measure_is_non_zero_for_a_real_member(
        self,
        route: _Route,
        postgres_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Đối chứng dương -- không có ca này, số 0 ở trên không chứng minh gì.

        Cùng đường dẫn, cùng extractor, chỉ khác người gọi. Nếu extractor đọc
        nhầm khoá, hoặc route trả 500 cho tất cả mọi người, hoặc đường dẫn gõ
        sai, ca này đỏ và ca từ chối ở trên bị lộ là mù.
        """

        context, owner, _, outing, _ = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            response = client.get(
                route.path(context.id, outing.id), headers=_headers(owner.id)
            )

        assert response.status_code == 200, (
            f"{route.name}: thành viên thật bị chặn -- {response.text}"
        )
        measure = route.measure(response.json())
        assert measure > 0, (
            f"{route.name}: extractor trả 0 cho chính thành viên của nhóm; "
            "phép đo này không phân biệt được gác với mù"
        )

    def test_a_left_member_is_refused_with_the_same_emptiness(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Hàng membership tồn tại nhưng không ACTIVE vẫn phải rỗng.

        `is_member` lọc cả `state` lẫn `left_at`. Một người từng ở trong nhóm
        là ca sát biên nhất: id của họ có thật, hàng của họ có thật, và một
        phép kiểm chỉ hỏi "có hàng không" sẽ cho họ đi qua.
        """

        from app.db.models import MembershipState

        context, _, _, outing, photo = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )
        gone = _person(postgres_session, "Người đã rời")
        _join(postgres_session, context, gone, state=MembershipState.LEFT)

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            for route in ROUTES:
                response = client.get(
                    route.path(context.id, outing.id), headers=_headers(gone.id)
                )
                assert response.status_code == 403, route.name
                assert route.measure(response.json()) == 0, route.name
                for needle in _needles(context, outing, photo):
                    assert needle not in response.text, route.name


# --------------------------------------------------------------------------
# 2 -- album không được là cửa sau đi vòng qua cổng ảnh
# --------------------------------------------------------------------------


class TestAlbumIsNotADoorAroundThePhotoGate:
    def test_another_groups_outing_id_is_not_readable_from_my_own_context(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Ca nguy hiểm nhất của F36, và nó KHÔNG bị 403 chặn.

        Kẻ gọi dùng `context_id` của chính họ -- nên `is_member` trả True và
        cổng quyền mở -- rồi truyền `outing_id` của nhóm khác. Nếu service
        không kiểm chuyến đi có thuộc context này không, thành viên của bất kỳ
        nhóm nào cũng đọc được album của mọi nhóm khác. Cổng membership hoàn
        toàn không nhìn thấy đường này.
        """

        victim, _, _, victim_outing, victim_photo = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )
        mine, me, _, my_outing, _ = _seed_group_with_everything(
            postgres_session, "Nhóm A"
        )

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            stolen = client.get(
                f"/contexts/{mine.id}/albums/{victim_outing.id}",
                headers=_headers(me.id),
            )
            # Đối chứng dương: cùng người, cùng context, chuyến đi của chính họ.
            own = client.get(
                f"/contexts/{mine.id}/albums/{my_outing.id}", headers=_headers(me.id)
            )

        assert own.status_code == 200, f"đối chứng dương hỏng: {own.text}"

        assert stolen.status_code == 404, (
            f"chuyến đi của nhóm khác đọc được qua context của mình: "
            f"{stolen.status_code}"
        )
        assert _album_measure(stolen.json()) == 0
        for needle in _needles(victim, victim_outing, victim_photo):
            assert needle not in stolen.text, needle

    def test_the_cover_is_never_a_photograph_of_another_group(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Ảnh bìa là đường rò rỉ hẹp nhất của F36: một tấm ảnh, không hỏi ai.

        `list_outing_memories` nhận `outing_id` và tự tra `context_id` từ
        chuyến đi. Nếu mệnh đề `Memory.context_id == Outing.context_id` rơi
        mất, cửa sổ trở thành một khoảng ngày thuần -- và mọi nhóm có ảnh chụp
        trong đúng những ngày đó sẽ bị lắp vào album này. Nhóm A dưới đây
        KHÔNG có ảnh nào của chính mình, nên bìa đúng phải là `None`; bất kỳ
        thứ gì khác `None` chỉ có thể đến từ nhóm B.
        """

        victim, victim_owner, _, _, _ = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )
        # Ảnh của nhóm B rơi đúng vào ngày chuyến đi của nhóm A.
        inside_window = _photo(
            postgres_session,
            victim,
            victim_owner,
            at=NOW.replace(hour=12, minute=0) + timedelta(seconds=1),
        )

        mine, me = _group(postgres_session, "Nhóm A")
        my_outing = _outing(postgres_session, mine, me, "Chuyến không có ảnh")

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            listed = client.get(f"/contexts/{mine.id}/albums", headers=_headers(me.id))
            detail = client.get(
                f"/contexts/{mine.id}/albums/{my_outing.id}", headers=_headers(me.id)
            )

        assert listed.status_code == 200, listed.text
        assert detail.status_code == 200, detail.text

        albums = listed.json()["albums"]
        assert len(albums) == 1, "đối chứng: chuyến đi của chính nhóm A phải có mặt"
        assert albums[0]["cover"] is None, (
            f"bìa album của nhóm A là ảnh của nhóm khác: {albums[0]['cover']}"
        )
        assert albums[0]["photo_count"] == 0

        assert detail.json()["photos"] == []
        assert detail.json()["photo_count"] == 0
        for text in (listed.text, detail.text):
            assert inside_window.image_url not in text
            assert str(inside_window.id) not in text
            assert str(victim.id) not in text

    def test_the_cover_is_the_groups_own_photograph_when_it_has_one(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Đối chứng dương cho ca trên: bìa `None` phải là kết luận, không phải
        trạng thái mặc định của một tính năng chưa bao giờ chạy."""

        mine, me = _group(postgres_session, "Nhóm A")
        my_outing = _outing(postgres_session, mine, me, "Chuyến có ảnh")
        mine_photo = _photo(postgres_session, mine, me)

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            listed = client.get(f"/contexts/{mine.id}/albums", headers=_headers(me.id))

        album = listed.json()["albums"][0]
        assert album["cover"] is not None, "bìa không bao giờ được dựng -- ca trên mù"
        assert album["cover"]["image_url"] == mine_photo.image_url
        assert album["photo_count"] == 1
        del my_outing


# --------------------------------------------------------------------------
# 3 -- trang khách không thấy gì của ba tính năng này
# --------------------------------------------------------------------------


class TestGuestSeesNoneOfThis:
    @pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.name)
    def test_without_an_actor_header_there_is_no_answer(
        self,
        route: _Route,
        postgres_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Khách cầm token, không cầm `X-Actor-ID`. Không có danh tính thì
        không có câu trả lời -- và thân phản hồi vẫn phải rỗng."""

        context, _, _, outing, photo = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            response = client.get(route.path(context.id, outing.id))

        assert response.status_code == 401, route.name
        assert route.measure(response.json()) == 0, route.name
        for needle in _needles(context, outing, photo):
            assert needle not in response.text, f"{route.name}: {needle}"

    def test_a_guest_token_is_not_an_identity(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Token khách đặt vào ô `X-Actor-ID` không mở được gì.

        Nó không phải UUID nên dừng ở 422; và kể cả khi khách có một `Person`
        thật (họ có -- người gửi tiền là người có hồ sơ), không có hàng
        membership thì vẫn là 403.
        """

        context, _, _, outing, photo = _seed_group_with_everything(
            postgres_session, "Nhóm B"
        )
        outsider = _person(postgres_session, "Khách trả tiền")

        app = _app(postgres_session, monkeypatch)
        with _Client(app) as client:
            as_token = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers={"X-Actor-ID": GUEST_TOKEN, "X-Actor-Roles": "guest"},
            )
            as_person = client.get(
                f"/contexts/{context.id}/preference-profile",
                headers={"X-Actor-ID": str(outsider.id), "X-Actor-Roles": "guest"},
            )

        assert as_token.status_code == 422, as_token.text
        assert as_person.status_code == 403, as_person.text
        for response in (as_token, as_person):
            assert _preference_measure(response.json()) == 0
            for needle in _needles(context, outing, photo):
                assert needle not in response.text, needle

    def test_the_guest_page_carries_no_group_intelligence(
        self, postgres_session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Vòng đời tiền thật, `/g/{token}` thật, và nhóm đó có đủ dữ liệu
        F31/F33/F36 để lộ.

        Đây là trang duy nhất người ngoài nhóm mở được. Nó không assert lên
        view model -- nó hỏi chính route đó và đọc HTML trả về, vì view model
        là thứ có thể đúng trong khi template render thêm.
        """

        state = _persist_lifecycle(postgres_session)

        author = Person(id=state.sender_id, display_name="Thành viên nhóm")
        postgres_session.add(author)
        postgres_session.flush()
        context = Context(
            id=state.context_id,
            display_name="Nhóm đi ăn",
            created_by_id=state.sender_id,
        )
        postgres_session.add(context)
        postgres_session.flush()

        # Đúng những hàng mà ba tính năng đọc.
        _checkin(postgres_session, context, author, GRILL)
        _say(postgres_session, context, author, "bí mật của nhóm này")
        outing = _outing(postgres_session, context, author, "Chuyến Đà Lạt")
        photo = postgres_session.merge(
            Memory(
                id=uuid.uuid4(),
                context_id=context.id,
                author_id=author.id,
                kind=MemoryKind.PHOTO,
                image_url=f"/contexts/{context.id}/photos/{uuid.uuid4()}",
                created_at=NOW + timedelta(minutes=1),
            )
        )
        postgres_session.flush()

        async def run_sync_inline(function, *args, **kwargs):
            del kwargs
            return function(*args)

        monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync_inline)
        monkeypatch.setattr("app.api.service._now", lambda: NOW + timedelta(minutes=10))
        app = create_app()
        app.dependency_overrides[get_repository] = lambda: SqlAlchemyApiRepository(
            postgres_session
        )

        async def get_page():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.get(f"/g/{GUEST_TOKEN}")

        response = anyio.run(get_page)

        # Trang phải render được thì sự im lặng của nó mới có nghĩa. Một trang
        # 500 cũng không chứa gì cả.
        assert response.status_code == 200, response.text
        assert "Techcombank" in response.text, "trang khách chưa render envelope"

        for needle in (
            "bí mật của nhóm này",
            "Chuyến Đà Lạt",
            str(outing.id),
            str(photo.id),
            photo.image_url,
            GRILL["name"],
        ):
            assert needle not in response.text, f"trang khách lộ {needle!r}"
        for word in ("preference", "affinity", "album", "Album", "sở thích", "gu "):
            assert word not in response.text, f"trang khách nhắc {word!r}"
