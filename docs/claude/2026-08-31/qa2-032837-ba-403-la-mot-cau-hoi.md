# Ba con 403 của F43/F44/F45 là (a): phép đo chọn nhầm nhóm — không phải lỗi quyền

- task: `qa2-032837` (hậu tố `00558701`)
- commit đo: `fc39c96` (origin/main lúc bắt việc)
- protocol_version: v1
- verdict: **(a)** — máy chủ trả lời đúng. Backend **không có gì phải sửa** ở ba route này.
- skill: `api-testing`
- blocker còn mở: không có blocker mới. Blocker cũ (client ghim nhóm) vẫn nguyên,
  nhưng nó là **một** lỗi client, không phải ba tính năng hỏng.

## Câu hỏi

Báo cáo `qa2-022247` liệt kê ba hàng TẮC, cùng một `context_id`, cùng một mã:

```
F43  GET  403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/map
F44  GET  403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/heatmap
F45  POST 403 /contexts/1aa00000-aaaa-4aaa-8aaa-0000a0000001/meet
```

Một con 403 đứng một mình khớp với **hai** câu chuyện, và hai câu chuyện đó cần
hai cách sửa ngược nhau:

- **(a)** người gọi không phải thành viên nhóm đó → 403 **đúng**, sản phẩm không
  hỏng ở quyền, phép đo chỉ nhắm nhầm nhóm.
- **(b)** lỗi quyền thật → người **là** thành viên vẫn bị từ chối → giao backend.

Một chiều đo không phân biệt được. Nên tôi đo bốn chiều trên một stack sống.

## Cách đo

Stack dùng một lần do `scripts/e2e_slice.sh --keep` dựng — Postgres riêng, uvicorn
riêng, cổng ngẫu nhiên. **Không** đo trên 8099: cổng đó là stack dùng chung, và
một con số đọc từ đó không quy được về cây nào.

```bash
scripts/e2e_slice.sh --keep      # API http://127.0.0.1:46395 · db 127.0.0.1:44943
MOBILE_DATABASE_URL=<dsn> python3 scripts/reset_demo_group.py --yes
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL=<dsn> python3 scripts/seed_demo_data.py
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL=<dsn> \
  python3 tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py --ghi
```

Nhóm thật của lượt đo: `Team Đà Lạt` `69963939-752b-4d78-9809-76d515134290`,
7 thành viên ACTIVE. Actor: `46b55e67-…` (Minh, admin) — **một thành viên có thật
của nhóm có thật**, đọc ra từ bảng `memberships`.

## Kết quả — bốn chiều, số thật

```
[D] id có phải một nhóm không — GET /contexts/{id} bởi 46b55e67
  ID GHIM 1aa00000-...     GET  /contexts/{id} -> 403  permission_denied
    contexts     0 dòng
    memberships  0 dòng
  NHÓM THẬT 69963939       GET  /contexts/{id} -> 200
    contexts     1 dòng
    memberships  7 dòng

[A] TÁI LẬP — thành viên thật × id ghim trong app
  GET  F43 map     -> 403 permission_denied
  GET  F44 heatmap -> 403 permission_denied
  POST F45 meet    -> 403 permission_denied

[B] ĐỐI CHỨNG — CÙNG actor đó × nhóm họ THỰC SỰ thuộc về
  GET  F43 map     -> 200
  GET  F44 heatmap -> 200   khu=0 resolved=0 scanned=0
  POST F45 meet    -> 200

[C] ĐỐI CHỨNG DƯƠNG — người lạ × nhóm thật (cổng phải cắn)
  GET  F43 map     -> 403 permission_denied
  GET  F44 heatmap -> 403 permission_denied
  POST F45 meet    -> 403 permission_denied
```

**Chiều C không phải thủ tục.** Không có nó, "B trả 200" giải thích được y hệt
bằng *một cái cổng mở toang cho mọi người*, và kết luận sẽ tựa lên đúng cái giả
định mà lượt đo lẽ ra phải kiểm. C đỏ đúng chỗ nó phải đỏ: cùng nhóm đó, đổi
người, ba route đóng lại.

Ba route đi qua đúng một câu hỏi — `repository.is_member(context_id, actor.id)`,
một truy vấn thật vào `memberships` (`service.py`, ba lần, `permissions.py:354-370`).
Nên **ba con 403 là một câu trả lời được in ba lần**, không phải ba lỗi.

## Kết luận: (a), và mạnh hơn (a) một bậc

Không phải "persona đi bộ không phải thành viên nhóm `1aa00000-…`". Là:

> **`1aa00000-aaaa-4aaa-8aaa-0000a0000001` có 0 dòng trong `contexts`.**
> Nó không phải nhóm của ai cả. Không ai có thể là thành viên của nó.

403 là câu trả lời **đúng** cho id đó — cho tôi, cho persona, cho bất kỳ ai.
Hai comment trong repo đã nói thẳng điều này từ trước (`apps/mobile/src/api.ts:76`,
`src/screens/chat/nhom.ts:3`) và `test_expense_context_fk_postgres.py:59` đặt tên nó
là `DEMO_ORPHAN_CONTEXT_ID`. Lượt này là lần đầu con số đó được đo trên máy chủ
sống thay vì suy từ chữ.

### Cái gì đổi so với báo cáo cũ, cái gì không

**Không đổi** — `qa2-022247` đã nói ba hàng này là **một** lỗi client (một prop
thiếu), không nói lỗi quyền. Chuỗi nhân quả vẫn đúng nguyên văn trên `fc39c96`:

```
apps/mobile/src/screens/kham-pha/places.ts:53      export const CONTEXT_ID = "1aa00000-…"
apps/mobile/src/screens/kham-pha/ban-do-nhom.ts:320,324,328   contextId: string = CONTEXT_ID
apps/mobile/src/screens/kham-pha/KhamPha.tsx:197   <BanDoNhom nguoi=… moDiemHenNgay=… onQuayLai=… />
                                                              ↑ vẫn không truyền contextId
```

`KhamPha` **đang cầm** nhóm thật — nó truyền `nhom` xuống `ChiTietDiaDiem` ở
dòng 206, ngay dưới. Vì `banDoUrl` có tham số mặc định, chỗ thiếu đó không phải
lỗi biên dịch; nó im lặng rơi về id mồ côi.

**Đổi** — bốn điều, và ba trong số đó ảnh hưởng tới ai làm gì tiếp:

1. Chữ **"TẮC"** ở ba hàng đọc thành *ba tính năng hỏng*. Đúng phải là: **một**
   lỗi client, lộ ra ở ba chỗ. Số tính năng thiếu không đổi, cách sửa đổi.
2. **Đừng giao backend.** Ba route trả 200 cho thành viên thật, 403 cho người lạ.
   Không có gì để sửa ở `service.py` / `permissions.py`.
3. Trước đây là **suy từ đọc code**; giờ là **đo có đối chứng dương**.
4. Tiêu chí gỡ chặn cũ — *"`contextId={nhom?.id}` ở dòng 197, ba route hết 403"* —
   **đủ cho F43 và F45, KHÔNG đủ cho F44**. Xem mục dưới.

**Hệ quả im lặng vẫn nguyên và vẫn nghiêm trọng hơn ba con 403**: cùng hằng số đó
lái `GET /places?context_id=1aa00000-…` ở `places.ts:310`, và đường đó trả **200**.
"AI MATCH 96%" đang chấm theo ngân sách và sở thích của một nhóm **không tồn tại**.
Không có 403 nào lộ ra ở đó.

## Câu Lead hỏi riêng: /heatmap trả 403 hay 200-với-0-khu?

**200 với 0 khu.** Trên nhóm mà persona thực sự thuộc về:

```
GET /contexts/69963939-…/heatmap -> 200
{"areas": [], "resolved_checkins": 0, "unknown_area_count": 0, "scanned_checkins": 0}
```

Quyền đúng. Nhóm chưa có dữ liệu bản đồ. Chặng `--ghi` chứng minh đó là **dữ
liệu**, không phải code, bằng cách ghi rồi đọc lại qua đúng route của sản phẩm:

```
trước   GET  /heatmap -> 200  khu=0 scanned=0
ghi     POST /contexts/{id}/checkins p-tiem-nuong-xom-lao -> 201
ghi     POST /contexts/{id}/checkins p-lung-chung-cafe    -> 201
sau     GET  /heatmap -> 200  khu=1 scanned=2  [('da-lat', 2)]
```

Cách sửa cho màn hình là **seed dữ liệu**, không phải sửa quyền:
`scripts/seed_demo_data.py` dựng 3 buổi đi chơi và 8 chặng nhưng **không tạo một
memory `kind="checkin"` nào**, nên mọi lượt đi bộ live đều gặp heatmap rỗng.

### Nhưng giả thuyết "cùng gốc với ca test chập chờn" thì KHÔNG đúng

Lead đoán ca test chập chờn (#407) và ba con 403 có thể cùng một gốc. Tôi đã
kiểm và **không phải**, nên xin đừng đi tiếp theo hướng đó:

`apps/mobile/tests/duong-vao-ban-do-nhom.test.mjs` chạy trên **stub**, không phải
máy chủ thật — `installTabStubs` / `taoFixtures` từ `tools/tab-snapshots.mjs`, và
`/heatmap` ở đó trả `fixtures.nhietDo` (`tab-snapshots.mjs:863`). Ca test đó
**chưa bao giờ chạm** vào `is_member`, vào `memories`, hay vào dữ liệu seed. Cái
`>=1 khu` của nó do fixture quyết định.

Nên hai chuyện này rời nhau:

| | Chạm cổng quyền thật? | Chạm dữ liệu seed thật? |
|---|---|---|
| Ba con 403 (F43/F44/F45) | **Có** — `is_member` trên máy chủ sống | Có |
| Ca test #407 | Không — stub | Không — fixture |

Điều đó cũng có nghĩa: bản sửa #407 của qa3 đứng vững độc lập với phát hiện này,
và heatmap rỗng trên dữ liệu seed là một lỗ hổng **riêng**, chưa ca test nào gác.

`GET /map` cũng vậy: `visited: 0`. `trending: 2` và `recommended: 8` có số vì
chúng đọc catalogue tĩnh `app/places/catalog.py`, không đọc lịch sử nhóm.

### Bẫy tôi đã sập trong lượt này, ghi ra để người sau khỏi mất một vòng

Sản phẩm có **hai** thứ tên là "check-in", và tôi thử nhầm cái trước:

| Route | Ghi vào | Có nuôi heatmap? |
|---|---|---|
| `POST /outing-stops/{id}/checkins` (F46 — tới một chặng) | `outing_stop_checkins` | **Không** — bảng đó cố ý không có toạ độ |
| `POST /contexts/{id}/checkins` (lên tường kỷ niệm) | `memories` kind=`checkin` | **Có** — `_scan_checkins` đọc đúng bảng này |

Tôi POST cái thứ nhất, nhận `201` hai lần, rồi đọc lại heatmap thấy vẫn
`scanned_checkins: 0`. Nhìn y hệt một phép gộp hỏng. Nó không hỏng — hai bảng
khác nhau, và `OutingStopCheckin` trong `models.py:1250` giải thích tại sao bảng
đó không có `lat`/`lng`. Chặng `--ghi` của probe ghi lại cả cái bẫy này.

## Cái phép đo này KHÔNG chứng minh

- Không chứng minh màn hình sau khi sửa `contextId` sẽ **vẽ** đúng. Nó đo máy chủ
  bằng HTTP, không mở trình duyệt lượt này.
- Không chứng minh cổng quyền chặn được **mọi** kiểu người gọi — chỉ đo một người
  lạ (`0b0b…`, không có dòng trong `people`) và một thành viên ACTIVE. Thành viên
  đã rời nhóm (`state != active`) chưa đo lượt này.
- Không chứng minh nhóm nào khác ngoài `Team Đà Lạt` của bộ seed.
- Không đo lại ca test #407. Tôi chỉ đọc nguồn nó đủ để biết nó chạy trên stub —
  đủ để bác bỏ giả thuyết "cùng gốc", không đủ để nói gì về độ ổn định của nó.
- `--ghi` **sửa dữ liệu**. Chỉ chạy trên stack dùng một lần, đừng bắn vào 8099.

## Chạy lại

```bash
scripts/e2e_slice.sh --keep
MOBILE_DATABASE_URL=<dsn> python3 scripts/reset_demo_group.py --yes
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL=<dsn> python3 scripts/seed_demo_data.py
MOBILE_SEED_API_BASE_URL=<api> MOBILE_DATABASE_URL=<dsn> \
  python3 tests/qa/qa2-403-mot-cau-hoi/probe_doi_chung_hai_chieu.py --ghi
```

Probe tự đọc nhóm thật và khu xuất phát từ `GET /areas`; không có hằng số nào
chép tay ngoài chính id mồ côi đang bị điều tra. (Bản đầu tiên chép tay
`"quan-1"`, ăn `422 unknown_area`, và suýt nữa tôi đọc con 422 đó thành bằng
chứng về F45. Route `/areas` tồn tại đúng để chặn kiểu sai đó.)
