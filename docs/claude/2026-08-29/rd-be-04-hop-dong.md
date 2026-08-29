# Hợp đồng rd-be-04 — AI là một thành viên của nhóm

protocol_version: v1 · nhánh: `backend/rd-be-04-ai-thanh-vien-nhom` · nền: `origin/main` @ ebd4235

Spec §F08 · mockup `product/features/03-nhom-chat-va-ai-len-ke-hoach.png`.

## Vấn đề đang giải

AI đọc ngữ cảnh nhóm và trả lời khi hợp lý, **không cần bị @**. Nó trả về tin có
cấu trúc để client dựng THẺ, không phải chữ trơn.

Ba điều phải giữ, và cả ba đều là chỗ dễ nói dối nhất:

1. **AI không được bịa địa điểm.** Bịa một quán không tồn tại là mất niềm tin ngay.
2. **AI không tự tạo khoản chi hay đụng vào tiền.** Nó gợi ý, người xác nhận.
3. **Có trần số lần AI tự lên tiếng.** Một AI nói liên tục là phiền, không phải thông minh.

Thêm: nội dung chat là dữ liệu riêng tư — **không log nội dung tin nhắn**.

## Quyết định kiến trúc

### QĐ-1: Mô hình chọn ID, MÁY CHỦ cấp sự thật

Đây là điểm chống bịa mang tính **cấu trúc**, không phải lời dặn trong prompt.

Gemini chỉ được trả về `place_id`. Nó **không** được trả về tên quán, địa chỉ, giá,
rating. `ground_card` tra từng id trong danh mục máy chủ và **chép nguyên bản ghi của
máy chủ** vào thẻ. Tên quán mô hình viết ra bị vứt đi, kể cả khi id đúng.

Hệ quả: dù mô hình có bịa tên hay hay tới đâu, cái tới client vẫn là dữ liệu danh mục.
Cách duy nhất để bịa lọt là bịa ra một **id** — và id không có trong danh mục thì cả
thẻ bị từ chối.

### QĐ-2: Từ chối cả thẻ, không lọc bớt

Một id lạ → ném `CompanionError`, service trả `spoke=false`, **không ghi tin nào**.

Lọc bớt id lạ rồi vẫn đăng là tệ hơn: một lịch trình bị rút mất một chặng trông y hệt
một lịch trình đúng, và chuyện mô hình vừa bịa bị nuốt mất. Từ chối thì quan sát được.

### QĐ-3: Danh sách trắng khoá, không cấm theo từ khoá

`ground_card` **dựng payload đầu ra từ đầu**, chỉ lấy đúng các trường có tên trong hợp
đồng. Mọi khoá khác mô hình trả về đều rơi — kể cả `expense`, `amount_vnd`, `obligation`.

Cấm theo danh sách từ khoá là trò đuổi bắt: quên một từ là lọt. Danh sách trắng thì
trường mới phải được thêm bằng tay mới xuất hiện được.

Cộng thêm: đường đi của lượt AI **chỉ gọi `create_message`**. Nó không chạm bất kỳ
method nào của repository liên quan tới khoản chi/nghĩa vụ. Có ca kiểm điều đó bằng cách
đếm lời gọi, vì "thẻ không có trường tiền" không chứng minh "không ghi vào sổ".

### QĐ-4: Trần lên tiếng tính bằng METADATA, không đọc nội dung

`plan_turn` nhận đúng `{"id", "author_kind", "created_at"}` cho mỗi tin — **không có
`body`**. Quyền riêng tư được cưỡng chế bằng hình dạng dữ liệu, không bằng kỷ luật:
hàm quyết định trần không thể log nội dung vì nó chưa từng thấy nội dung.

### QĐ-5: Nguồn địa điểm là adapter, không phải bản sao

rd-be-05 (PR #81, **CHƯA MERGE**) dựng danh mục ở `app/places/catalog.py` — seed data,
không phải bảng DB. Việc này **không** dựng danh mục thứ hai: hai nguồn địa điểm song
song là đúng kiểu hỏng mà "hai phép chia tiền" đã dạy.

`app/api/companion_places.py` import mềm `app.places.catalog`. Khi chưa có (main hôm nay):
danh mục rỗng → prompt nói rõ "không có địa điểm nào" → mọi thẻ `places`/`itinerary` bị
`ground_card` từ chối → AI vẫn trả lời được thẻ `text` có ngữ cảnh nhóm thật.

**Đây là chỗ tôi nói rõ giới hạn:** trên main hôm nay thẻ địa điểm KHÔNG bật. Nó bật khi
#81 vào main, không cần sửa gì thêm ở lane backend.

## Hợp đồng tầng domain — `app/domain/companion.py`

Thuần. `dict` vào, `dict` ra. Không import `app.db`, `app.api`, `app.payments`,
`sqlalchemy`, `fastapi`, `alembic`, `pydantic`. `tests/test_import_boundary.py` gác.

```python
class CompanionError(Exception):
    def __init__(self, code: str) -> None: ...
    code: str

DEFAULT_LIMITS = {
    "window_messages": 20,
    "max_ai_messages_per_window": 3,
    "cooldown_seconds": 90,
}
```

### `plan_turn(conversation: dict, limits: dict | None = None) -> dict`

```
conversation = {
  "messages": [ {"id": str, "author_kind": "human"|"ai", "created_at": iso8601}, ... ],  # CŨ -> MỚI
  "now": iso8601,
}
->  {"may_speak": bool, "reason": str}
```

`reason` theo thứ tự ưu tiên, dừng ở cái đầu tiên đúng:

| reason | khi nào |
|---|---|
| `no_conversation` | không có tin nào của người |
| `already_spoke_last` | tin mới nhất là của AI |
| `rate_limited` | số tin AI trong `window_messages` tin gần nhất ≥ `max_ai_messages_per_window` |
| `cooldown` | tin AI mới nhất cách `now` dưới `cooldown_seconds` giây |
| `ok` | còn lại → `may_speak=True` |

`created_at` phải có timezone; thiếu → `CompanionError("companion_timestamp_naive")`.

### `ground_card(raw: dict, allowed_places: list[dict]) -> dict`

`allowed_places`: bản ghi danh mục máy chủ, mỗi cái có ít nhất `id` (str) và `name`.

Đầu ra, dựng lại từ đầu:

```
{"kind": "text",      "payload": {"text": str}}
{"kind": "places",    "payload": {"intro": str, "places": [PLACE, ...]}}
{"kind": "itinerary", "payload": {"title": str,
                                  "stops": [{"time_text": str, "note": str, "place": PLACE}, ...]}}
```

`PLACE` là **bản chép của bản ghi danh mục**, không phải thứ mô hình gửi lên.

Đầu vào mô hình được phép gửi: `kind`, `payload.text`, `payload.intro`, `payload.title`,
`payload.place_ids: [str]`, `payload.stops: [{"place_id", "time_text", "note"}]`.

| code | khi nào |
|---|---|
| `companion_card_malformed` | `raw` không phải dict, thiếu `kind`, `payload` không phải dict |
| `companion_card_kind_unknown` | `kind` ngoài `text`/`places`/`itinerary` |
| `companion_place_not_in_catalogue` | bất kỳ id nào được nhắc không có trong `allowed_places` |
| `companion_card_empty` | `places`/`itinerary` không còn mục nào; `text` rỗng hoặc toàn khoảng trắng |

Còn lại: `place_ids` trùng → khử trùng lặp, giữ thứ tự. Quá `MAX_PLACES=5` /
`MAX_STOPS=6` → cắt bớt. Chữ quá `MAX_TEXT=600` → cắt (một câu dài không phải lời nói dối).

## Hợp đồng tầng API

### `app/api/companion_gemini.py` — `GeminiCompanion`

Cùng biên an toàn credential như `vision_gemini.py`: thiếu key →
`CompanionError("COMPANION_NOT_CONFIGURED")`; mọi lỗi khác → `RuntimeError(type(exc).__name__)`,
**không bao giờ** để nguyên văn exception đi tiếp (nó có thể chứa cả key lẫn nội dung chat).

`reply(conversation, members, places, budget_per_person_vnd) -> dict` (thẻ thô).
`temperature=0.0`, `response_schema` ép mô hình chỉ trả `place_id`, không trả tên quán.

### `app/api/companion_places.py`

`load_place_catalogue() -> list[dict]` — import mềm `app.places.catalog.PLACES`,
chuẩn hoá còn các trường client cần. Không có module → `[]`.

### `ApiService.take_companion_turn(context_id, actor) -> CompanionTurnResponse`

1. `_require_permission("invoke_group_companion", actor, {"is_group_member": ...})`
2. `repository.list_messages(context_id, limit=CONTEXT_WINDOW)` — 40 tin gần nhất
3. metadata → `plan_turn` → `may_speak=False` ⇒ trả `spoke=false` + reason, **không ghi gì**
4. dựng đầu vào mô hình: nội dung tin + tên hiển thị thành viên + ngân sách (nếu biết)
5. gọi companion client; `CompanionError`/`RuntimeError` ⇒ `spoke=false`, `reason="unavailable"`
6. `ground_card(...)`; `CompanionError` ⇒ `spoke=false`, `reason="ungrounded"`, **không ghi gì**
7. `repository.create_message(kind="ai_card", author_id=None, card=grounded, ...)`
8. trả `spoke=true` + `message`

`author_id=None` là có chủ ý: AI không phải một `Person`. Model `Message` đã cho phép
(`kind = 'ai_card' OR author_id IS NOT NULL`).

### Route

`POST /contexts/{context_id}/ai-turn` → 200 `CompanionTurnResponse`.

```python
class CompanionTurnResponse(ApiModel):
    context_id: UUID
    spoke: bool
    reason: str
    message: MessageResponse | None
```

Không phải 201 kể cả khi có ghi tin: kết quả bình thường của lời gọi này là **im lặng**,
và một route lúc 201 lúc 200 buộc client phải đoán.

### Quyền

Thêm `"invoke_group_companion": {"roles": {"group_admin", "member"}, "requires": ("is_group_member",)}`.

## Cổng phải xanh

- `python3 -m pytest services/api/tests tests -q` (gốc repo)
- `MOBILE_REQUIRE_POSTGRES_TESTS=1 python -m pytest tests/postgres -q`
- `ruff check` trên file đã sửa
- `alembic upgrade head --sql` offline — việc này **không** thêm migration
