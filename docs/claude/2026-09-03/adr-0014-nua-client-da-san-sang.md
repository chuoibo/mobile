# ADR-0014 — nửa client đã dựng xong, đang chờ route

- **Nhánh:** `claude/p0-w-rudi-du-lieu-that`
- **Trạng thái ADR-0014:** 🟡 ĐỀ XUẤT. **Chưa** được Lead nhận. Doc này **không** đề nghị bỏ qua cổng đó.
- **Lane:** client là Claude (`apps/mobile/`), server là Codex (`services/api/`, `db/`).
- **Thứ tự merge:** **máy chủ trước, client sau.** `scripts/check_api_contract.py` chặn merge một client gọi path máy chủ chưa khai, và đó là hành vi đúng — `docs/architecture/01` mục 7 nêu chính ràng buộc này.

---

## 1. Cái đã có trên nhánh này, và vì sao nó merge được ngay

Không dòng nào dưới đây thêm một **path literal** mới, nên cổng hợp đồng vẫn exit 0. Đo lại được: `python3 scripts/check_api_contract.py`.

| Việc | Chỗ | Gác bởi |
|---|---|---|
| Có bearer thì gửi `Authorization`, và **bỏ** `X-Actor-ID` / `X-Actor-Roles` / `X-Actor-Contexts` | `src/api.ts` `actorHeaders` | `tests/rudi-phien.test.mjs` bắt header trên dây |
| 401 **khi đang giữ bearer** thì bỏ token và báo ra ngoài | `src/api.ts` `send` | như trên |
| 401 khi **không** có bearer thì **không** gọi đường mất phiên | `src/api.ts` | như trên |
| Token ở SecureStore, không ở AsyncStorage | `src/rudi/kho.ts` | — |
| `cheDo: "live" \| "trai-nghiem"` suy từ token, thay `enteredAsDemo` (state chết) | `src/rudi/session.tsx` | `DemoBadge` biến mất ở `live` |
| Seam cấp phiên **ném** `ChuaCoRouteError` | `src/rudi/phien.ts` | `tests/rudi-phien.test.mjs` |

Đã đột biến để chắc cổng có răng: cho `actorHeaders` gửi kèm `X-Actor-ID` khi có bearer → **1 ca đỏ**, trả lại → xanh.

**Vì sao `X-Actor-ID` bị BỎ chứ không phải để máy chủ lờ đi.** Mục 7 của ADR định nghĩa prod là *máy chủ thôi tin lời khai của client về danh tính*. Gửi kèm bộ ba header là đưa cho nó câu trả lời thứ hai, do client tự khai, cho đúng câu hỏi đó. Một cổng ở phía server mà quên lọc một header sẽ biến câu trả lời thứ hai thành câu trả lời được dùng.

---

## 2. Cái Codex cần ship, và client sẽ gọi thế nào

`src/rudi/phien.ts` giữ **hình dạng** của lời gọi mà không giữ đường dẫn. Khi route sống, đổi thân hàm và xoá ca test đang ghim cái ném.

### 2.1. Bootstrap: đổi bí mật lời mời đích danh lấy phiên

```
POST <đường dẫn do Codex đặt>
body: { "bi_mat": "<raw secret trao tay một lần>" }
→ 200 { "token": "<bearer thô>", "person_id": "<uuid>", "het_han": "<ISO 8601>" }
```

Ràng buộc, chép từ ADR-0014 mục 3 và 4:

- Chỉ nhận lời mời **đích danh**: `source ∈ {group, friend}` và `invited_person_id IS NOT NULL`.
- `source=link` **không** cấp phiên. Nó đi cửa cũ `POST /outing-invites/{token}/accept`, cap ở `INVITED`, và một thành viên ACTIVE khác duyệt trước khi dữ liệu nhóm hiện ra.
- Phiên gắn **đúng** `invited_person_id`. Body **không có** trường `person_id` nào được đọc. Client không khai người, và nó cũng không có gì để khai.
- Chỉ persist **digest SHA-256**. Khuôn đã có sẵn ở `GuestLink` và `OutingInvite`.
- **Cấm** dùng `invite.id` làm bí mật: nó đã trả ra trong `OutingInviteAcceptResponse`, tức là dữ liệu công khai.

Client giữ `token` trong SecureStore và **không bao giờ** ghi `person_id` vào header (mục 9). `person_id` trong body trả về chỉ để màn hình biết nó đang là ai; nó không đi kèm request nào.

### 2.2. Mất phiên: xoay bí mật trên hàng đã có

Cài lại app, đổi máy. `uq_outing_invites_person` là partial unique trên `(outing_id, invited_person_id)` và **không** lọc `accepted_at` / `revoked_at`, nên INSERT hàng đích danh thứ hai là **409**. Mời lại **không phải** đường re-login.

Xoay **tại chỗ**, cấp digest mới, digest cũ **chết vĩnh viễn**. **Cấm** hiện thực xoay bằng cách xoá `accepted_at`: làm vậy thì `accept_outing_invite` chạy được hai lần trên cùng một bí mật.

### 2.3. Thu hồi phiên

`traLaiPhien` trong `phien.ts` cũng đang ném. Xoá token trên máy là việc client làm được ngay; giết nó ở máy chủ thì chưa. Một token chỉ xoá ở máy là một token máy chủ vẫn còn nhận, nếu nó từng rời khỏi máy.

### 2.4. Roles và context

Client **không** gửi gì. Mục 7 liệt kê năm role chưa có nguồn trên phiên — `advancer`, `recipient`, `sender`, `creditor`, `platform_moderator` — và với mỗi cái, hoặc cấp đúng từ nguồn **tại action**, hoặc **403**. Không 200 kèm role đọc từ header.

Ca âm bắt buộc phía server: phiên `member` gửi header hoặc body tự xưng `creditor` → Actor **không** mang role đó.

---

## 3. Tiêu chí ra của nửa client, khi route đã sống

1. `doiLoiMoiLayPhien` gọi được thật; ca ghim `ChuaCoRouteError` đổi thành ca đường thành công. **Ca ném không được xoá lặng lẽ** — nó là thứ báo cho người sau biết route đã có.
2. `python3 scripts/check_api_contract.py` vẫn exit 0 sau khi thêm path (nghĩa là máy chủ đã vào `main` trước).
3. Một ca chứng minh phiên hết hạn đưa người về màn vào cửa chứ không phải câu «sự cố máy chủ».
4. `cheDo` chuyển sang `live` và `DemoBadge` biến mất trên cả 21 màn — nhưng **chỉ** khi màn đó thật sự đọc dữ liệu máy chủ. Xem mục 4.

---

## 4. Cảnh báo: có token chưa làm cho MỌI màn thành thật

**Đã nối (M2):** Quyết toán và Tài chính. Hai màn này ở chế độ live đọc
`GET /contexts/{id}/balances`, `GET /contexts/{id}/recap`,
`GET /contexts/{id}/members` và `GET /people/{id}/finance`, và không chạm
`fixtures.ts` một dòng nào. Đo trên máy: `make mobile-native-live` với một
database seed riêng — màn hiện `6.785.000đ` (chính `split_total_vnd` của máy chủ,
không phải tổng do app cộng), `Ngọc → Minh 453.666đ`, `7 người`, và **không** có
`3.840.000đ`, `Xóm Lèo`, `Minh Anh` hay nhãn «Dữ liệu demo».

**Chưa nối:** 19 màn còn lại. Khám phá, Lên plan, Tin nhắn, Bình chọn, Kỷ niệm,
Album, Check-in, Thành tích vẫn đọc fixture ở cả hai chế độ.

Đây chính là cái bẫy phải nhớ. Ngay trong lượt đo M2 nó đã xảy ra một lần: khi
mới nối Quyết toán mà chưa nối Tài chính, cùng một lần mở app có màn hiện
`6.785.000đ` của nhóm seed và màn kia hiện `3.840.000đ` của fixture — **đúng cái
defect PR #512 được mở ra để sửa, chỉ quay ngược hướng.** Flow
`20-du-lieu-that.yaml` giờ đi qua **cả hai** màn tiền trong một lượt vì lý do đó.

**Luật cho người nối tiếp:** nối màn nào thì thêm assertion cho màn đó vào flow
20 trong cùng một commit. Một màn tiền ở chế độ live mà vẫn đọc fixture là một
lời nói dối, và nhãn «Dữ liệu demo» đã bị tắt nên không còn gì cảnh báo người
đọc nữa.

---

## 5. Còn nợ, ngoài ADR này

- **`scripts/check_api_contract.py` mù với route khai ngoài `app/api/routes/`.** `/healthz` khai ở `main.py:220` với `include_in_schema=False`, nên bất kỳ client nào gọi nó đều làm cổng đỏ nhầm địa chỉ. Cổng dùng chung, cần Codex.
- **`scripts/seed_demo_data.py` và fixture RuDi kể hai câu chuyện khác nhau**: seed có «Team Đà Lạt» **7 người** (Minh, Trang, Hải, Ngọc, Đức, Linh, Quân) với số tiền khác; fixture có **8 người** và bill Xóm Lèo 1.280.000đ. Ở chế độ live màn sẽ hiện số của seed. Muốn hai bên khớp thì sửa seed — lane Codex.
