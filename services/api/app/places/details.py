"""The fields only F10 needs, kept out of the list payload on purpose.

`GET /places` draws a grid of cards; `GET /places/{id}` draws one screen. A
description and three reviews per row would multiply the list response by
several times to carry text no card renders, on the one screen most likely to
be opened on a phone connection.

Separate file rather than extra keys in `catalog.py` for a second reason: this
is *prose*, and `catalog.py` is the file `Memory` names as the one whose rows a
check-in snapshots. Keeping the two apart means editing a description can never
be the change that rewrites where a group was last March.

Synthetic, like the rest of the seed. Reviewer names are invented first names,
the sentences were written for this repo, and no real venue is being described
or reviewed. The charter keeps real ratings and real people out of Git; making
them up avoids the question rather than answering it.
"""

from __future__ import annotations

from typing import Any, TypedDict

__all__ = ["PLACE_DETAILS", "PlaceDetailSeed", "find_detail"]


class Review(TypedDict):
    author: str
    rating: float
    body: str


class PlaceDetailSeed(TypedDict):
    description: str
    reviews: list[Review]


PLACE_DETAILS: dict[str, PlaceDetailSeed] = {
    "p-tiem-nuong-xom-lao": {
        "description": (
            "Quán nướng sân vườn, bàn than hoa đặt ngoài trời và có mái che khi "
            "Đà Lạt trở lạnh. Không gian rộng, kê được bàn dài cho nhóm sáu tới "
            "mười người mà không phải tách bàn."
        ),
        "reviews": [
            {
                "author": "Trang",
                "rating": 5.0,
                "body": "Đi bảy đứa vẫn đủ chỗ, thịt ướp đậm vị. Trời lạnh ngồi cạnh than rất hợp.",
            },
            {
                "author": "Đức",
                "rating": 4.0,
                "body": "Đồ ăn ổn, tối cuối tuần hơi đông nên nên gọi bàn trước.",
            },
        ],
    },
    "p-lung-chung-cafe": {
        "description": (
            "Cafe nằm trên sườn đồi, ban công nhìn xuống thung lũng. Buổi sáng "
            "sớm hay có sương, đây là khung giờ nhiều người tới chụp ảnh nhất."
        ),
        "reviews": [
            {
                "author": "Mai",
                "rating": 5.0,
                "body": "View đúng như ảnh. Ngồi ban công buổi sáng thấy sương phủ cả thung lũng.",
            },
            {
                "author": "Hưng",
                "rating": 4.0,
                "body": "Đồ uống vừa miệng, chỗ để xe hơi chật vào cuối tuần.",
            },
        ],
    },
    "p-chill-dem-da-lat": {
        "description": (
            "Rooftop bar ở trung tâm, nhạc chill và cocktail. Mở tới một giờ "
            "sáng nên hợp làm điểm cuối của một buổi tối đã đi vài chỗ."
        ),
        "reviews": [
            {
                "author": "Quân",
                "rating": 5.0,
                "body": "Nhạc vừa đủ nghe, vẫn nói chuyện với nhau được. Cocktail pha khá.",
            },
            {
                "author": "Linh",
                "rating": 4.0,
                "body": "Chỗ ngồi ngoài trời lạnh về khuya, nhớ mang thêm áo.",
            },
        ],
    },
    "p-an-cafe-da-lat": {
        "description": (
            "Quán cafe nhỏ theo lối vintage, bàn gỗ và đèn vàng. Yên tĩnh, phù "
            "hợp nhóm ít người muốn ngồi lâu nói chuyện."
        ),
        "reviews": [
            {
                "author": "Thảo",
                "rating": 5.0,
                "body": "Yên tĩnh thật, ngồi cả buổi chiều không ai giục.",
            },
            {
                "author": "Nam",
                "rating": 4.0,
                "body": "Quán nhỏ nên nhóm đông sẽ chật, bốn người là vừa.",
            },
        ],
    },
    "p-dreampark": {
        "description": (
            "Khu vui chơi ngoài trời nhiều trò, có khu dành cho nhóm đông chơi "
            "cùng lúc. Vé vào cổng tính riêng với vé từng trò."
        ),
        "reviews": [
            {
                "author": "Khoa",
                "rating": 5.0,
                "body": "Đi cả nhóm mười người, chơi từ chiều tới tối vẫn chưa hết trò.",
            },
            {
                "author": "Vy",
                "rating": 4.0,
                "body": "Vui nhưng nên xem bảng giá từng trò trước, cộng lại cũng đáng kể.",
            },
        ],
    },
    "p-lau-ga-la-e": {
        "description": (
            "Lẩu gà lá é, món đặc sản hay được gọi khi trời lạnh. Bàn kê sát "
            "nhau, không gian ấm và hơi ồn vào giờ cao điểm."
        ),
        "reviews": [
            {
                "author": "Bình",
                "rating": 5.0,
                "body": "Nước lẩu đậm, gà chắc thịt. Nhóm sáu người gọi một nồi lớn là đủ.",
            },
            {
                "author": "Hà",
                "rating": 4.0,
                "body": "Ngon nhưng giờ cao điểm phải chờ bàn khoảng hai mươi phút.",
            },
        ],
    },
    "p-nuong-ngoi-troi-thong": {
        "description": (
            "Nướng ngói dưới tán thông, bàn ngoài trời hoàn toàn. Chỉ mở từ "
            "chiều muộn, nên đây là chỗ cho bữa tối chứ không phải bữa trưa."
        ),
        "reviews": [
            {
                "author": "Sơn",
                "rating": 4.0,
                "body": "Ngồi giữa rừng thông ăn nướng khá thích, đồ ăn ở mức ổn.",
            },
            {
                "author": "Ngọc",
                "rating": 4.0,
                "body": "Ngoài trời hết nên hôm mưa là không ngồi được, cần xem thời tiết.",
            },
        ],
    },
    "p-song-mau-workshop": {
        "description": (
            "Workshop gốm, mỗi buổi kéo dài khoảng hai tiếng và mang sản phẩm "
            "về được. Nhận nhóm nhỏ, nên đặt chỗ trước theo khung giờ."
        ),
        "reviews": [
            {
                "author": "Uyên",
                "rating": 5.0,
                "body": "Người hướng dẫn kiên nhẫn, chưa làm gốm bao giờ vẫn ra được cái cốc.",
            },
            {
                "author": "Tuấn",
                "rating": 5.0,
                "body": "Hai tiếng trôi nhanh. Đi bốn người là vừa đẹp với số bàn xoay.",
            },
        ],
    },
    "p-quan-oc-di-be": {
        "description": (
            "Quán ốc vỉa hè, thực đơn dài và giá bình dân. Bàn nhựa kê ra ngoài "
            "đường, đông nhất khoảng tám giờ tối."
        ),
        "reviews": [
            {
                "author": "Phát",
                "rating": 5.0,
                "body": "Ốc tươi, giá mềm. Nhóm đông gọi chục món vẫn không tốn bao nhiêu.",
            },
            {
                "author": "Như",
                "rating": 4.0,
                "body": "Ngon nhưng ồn và khói, ai cần yên tĩnh thì không hợp.",
            },
        ],
    },
    "p-the-hill-rooftop": {
        "description": (
            "Rooftop có nhạc sống vào cuối tuần, nhìn ra trung tâm quận 1. Mức "
            "giá cao hơn mặt bằng chung trong danh sách này."
        ),
        "reviews": [
            {
                "author": "Duy",
                "rating": 4.0,
                "body": "Ban nhạc chơi hay, view đẹp. Đồ uống giá khá cao.",
            },
            {
                "author": "Chi",
                "rating": 4.0,
                "body": "Tối có nhạc sống thì khá ồn, muốn nói chuyện nên đi sớm.",
            },
        ],
    },
    "p-ca-phe-vot-hem": {
        "description": (
            "Cà phê vợt trong hẻm, mở từ năm giờ sáng. Chỗ ngồi là ghế nhựa "
            "thấp, phần lớn khách là người quen trong khu."
        ),
        "reviews": [
            {
                "author": "Tú",
                "rating": 5.0,
                "body": "Cà phê đậm đúng kiểu cũ, giá rẻ bất ngờ. Sáng sớm rất yên.",
            },
            {
                "author": "Lan",
                "rating": 4.0,
                "body": "Quán nhỏ trong hẻm, đi nhóm quá bốn người là khó tìm chỗ.",
            },
        ],
    },
    "p-bowling-sky": {
        "description": (
            "Trung tâm bowling trong nhà, tính tiền theo lượt chơi và theo làn. "
            "Có máy lạnh, nên đây là phương án khi trời mưa."
        ),
        "reviews": [
            {
                "author": "Kiên",
                "rating": 4.0,
                "body": "Làn sạch, máy tính điểm chạy ổn. Đi tám người thuê hai làn là vừa.",
            },
            {
                "author": "Oanh",
                "rating": 4.0,
                "body": "Cuối tuần phải chờ làn, nên gọi trước cho chắc.",
            },
        ],
    },
}


def find_detail(place_id: str) -> PlaceDetailSeed | None:
    """The prose for this place, or None when it has none.

    None is a real answer, not an error: a catalogue row without a description
    is still a place, and the detail route serves it with `description: null`
    rather than refusing. A row that 404s because nobody wrote copy for it would
    be a screen that breaks for the newest place in the list.
    """

    return PLACE_DETAILS.get(place_id)


def detail_fields(place_id: str) -> dict[str, Any]:
    """Wire shape for the prose half of a detail response."""

    seed = find_detail(place_id)
    if seed is None:
        return {"description": None, "reviews": []}
    return {"description": seed["description"], "reviews": list(seed["reviews"])}
