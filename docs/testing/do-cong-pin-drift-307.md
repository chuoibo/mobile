# Đo cổng pin-drift của #307 — phán quyết QA: ĐẠT

- **protocol_version**: v1
- **verdict**: `APPROVE` (hậu kiểm — #307 đã merge vào `main` là `edcb734` lúc
  2026-08-30T10:32:35Z, giữa lượt đo này)
- **đo tại**: `f5c33cc` (head #307) và `2862154` (`main` sau khi #307 vào)
- **đối chứng**: `fd5198b` (`main` TRƯỚC khi #307 vào)
- **blocker còn mở**: không
- **skill QC đã dùng**: `ai-qa-review`, `bug-reproduction`

Bốn file của #307 trên `main` **giống hệt từng byte** bản tôi đo ở head, nên mọi
số dưới đây vẫn phát biểu được về `main`:

```
GIỐNG HỆT  scripts/check_pin_drift.py              8ba8b7e33c39
GIỐNG HỆT  scripts/gate.sh                         6c78fce208bf
GIỐNG HỆT  tests/test_pin_drift_gate.py            6f7c6c79203e
GIỐNG HỆT  tests/test_gate_stage_bodies_are_unique.py  ca6128e1fdc3
```

---

## Lệch pin là có thật trên máy này

`python3 scripts/check_pin_drift.py` → **KHỚP 5 · LỆCH 6 · THIẾU 1**, đúng con số
Lead đo. Năm pin *quan trọng lúc import* đang lệch:

```
alembic          ship 1.14.0    máy 1.16.5
fastapi          ship 0.115.6   máy 0.135.3
pytest           ship 8.3.4     máy 9.0.3
sqlalchemy       ship 2.0.36    máy 2.0.43
pytest-subtests  ship 0.14.1    máy KHÔNG CÀI
```

---

## Câu 4 (quan trọng nhất) — cổng có bắt được đúng sự cố 30/08 không: **CÓ**

Dựng lại nguyên lỗi #288 (route 204 khai `-> None` trong module có
`from __future__ import annotations`) trong hai cây worktree sạch, rồi chạy đối
chứng. Bằng chứng container là **docker thật**, fastapi 0.115.6 thật — không phải
đọc văn bản nguồn.

| cây | lệnh | kết quả |
|---|---|---|
| `main` **trước** #307 (`fd5198b`) + lỗi | `import app.api.main` tại máy | `IMPORT OK, số route = 86` — máy này không thấy gì sai |
| `main` **trước** #307 + lỗi | `scripts/gate.sh migration` | **rc=0** · *"Tất cả chặng đã chạy đều ĐẠT."* ← đúng cái lỗ 30/08 |
| `main` **trước** #307 + lỗi | `scripts/gate.sh pinned-import` | **rc=1** · `AssertionError: Status code 204 must not have a response body` · *"app KHÔNG import được với fastapi 0.115.6 — container sẽ thoát trước khi healthy"* |
| **#307** + lỗi | `scripts/gate.sh migration` | **rc=1** · *"MỌI CHẶNG ĐẠT — NHƯNG KHÔNG PHẢI TRÊN BẢN SẼ SHIP"* + gọi tên 5 pin + chỉ ra `scripts/gate.sh migration pinned-import` |
| **#307** + lỗi | `scripts/gate.sh migration pinned-import` *(làm theo đúng chỉ dẫn cổng vừa in)* | **rc=1** tại `pinned-import`, đúng `AssertionError` trên |
| `main` **sau** #307 (`2862154`), cây sạch | `scripts/gate.sh migration pinned-import` | **rc=0** · `IMPORT OK, 69 đường dẫn` — cổng biết cách XANH |
| `main` sau #307, cây sạch | `scripts/gate.sh api` | `2370 passed, 478 skipped, 4847 subtests passed` rồi **rc=1** vì lệch pin |

Hàng 2 và hàng 4 là cặp đỏ-trước/xanh-sau đúng nghĩa: **cùng một cây hỏng, cùng
một lệnh, chỉ khác có #307 hay không** — rc lật từ 0 sang 1.

### Phạm vi thật, nói cho đúng

Riêng **hình dạng** #288 này thì `test_route_declarations_under_pinned_fastapi.py`
(#290) đã bắt được sẵn ở chặng `api`, nên cây hỏng vẫn sẽ đỏ ở đó dù không có
#307. Cái #307 thêm vào là hai thứ #290 không làm được:

1. Chặng `migration` (và mọi chặng không chạy pytest) — #290 không chạy ở đó, và
   hàng 2 chứng minh chặng đó vẫn báo xanh trên cây không boot nổi.
2. **Loại** chứ không phải **hình dạng**: 5 pin lệch, bất kỳ khác biệt hành vi nào
   chưa ai mô hình hoá. #290 mô hình đúng một `assert`.

---

## Câu 1 — đường tha `MOBILE_GATE_ALLOW_DRIFT=1`

**Có cho qua, và không im lặng.** Đo trên **cây đã hỏng thật** (có lỗi #288), tức
trường hợp nguy hiểm nhất:

```
rc=0
Tất cả chặng đã chạy đều ĐẠT.

LƯU Ý: MOBILE_GATE_ALLOW_DRIFT=1 — pin quan trọng đang lệch và lượt này
KHÔNG chứng minh được ảnh sẽ ship chạy được. Đã bỏ qua theo yêu cầu:
    alembic
    fastapi
    pytest
    pytest-subtests
    sqlalchemy
```

`GATE_SUMMARY_FILE` ghi đúng như PR nói:

```
passed=1
failed=0
skipped=0
passed-stage=migration
pin-drift=drift-waived
pin-drift-name=alembic
pin-drift-name=fastapi
pin-drift-name=pytest
pin-drift-name=pytest-subtests
pin-drift-name=sqlalchemy
```

**Tiền đề của đường tha cũng đúng.** Giả lập máy không có docker (stub `docker`
exit 1, PATH đầy đủ): `pinned-import` **BỎ QUA — "docker daemon không chạy"**, nên
lượt chạy không có cách nào lấy được bằng chứng bản ship, và cổng chặn (rc=1).
Thêm `MOBILE_GATE_ALLOW_DRIFT=1` vào đúng máy đó → rc=0 kèm LƯU Ý. Không có đường
tha thì máy không docker sẽ đỏ vĩnh viễn và cổng bị gỡ trong một ngày.

---

## Câu 2 — có làm đỏ nhầm chặng không chạy code ứng dụng không: **KHÔNG**

Chạy từng chặng một trên head #307, đếm số dòng chặn-vì-drift trong stdout:

| chặng | rc | dòng chặn drift |
|---|---|---|
| `guard` | 0 | 0 |
| `ruff` | 0 | 0 |
| `contract` | 0 | 0 |
| `client-routes` | 0 | 0 |
| `cors` | 0 | 0 |
| `shared` | 0 | 0 |
| `mobile` | **2** | 0 |

`mobile` rc=2 **không phải** do cổng này: `apps/mobile/` không có trong worktree
(bẫy đã ghi trong CLAUDE.md), chặng BỎ QUA, và gate.sh trả 2 khi không chặng nào
chạy. Đối chứng trên `main` **trước** #307: `scripts/gate.sh mobile` → **rc=2**,
y hệt. Không có dòng drift nào trong cả hai.

---

## Câu 3 — 12 ca có răng không

Nền: `python3 -m pytest tests/test_pin_drift_gate.py -q` → **12 passed in 8.94s**
(head), **12 passed in 9.26s** (main sau merge).

Bảng đột biến có **cả hai chiều**: hàng ĐỔI tính chất phải ĐỎ, hàng GIỮ tính chất
phải XANH. Bảng toàn đỏ không phân biệt được cái gì đang thật sự được gác.

### Hàng ĐỔI tính chất — phải ĐỎ

| # | đột biến | kết quả | ca đỏ |
|---|---|---|---|
| M1 | bỏ `fastapi` khỏi `IMPORT_CRITICAL` | **ĐỎ** 2 | `test_a_drifted_critical_pin_is_red`, `test_names_only_...` |
| M2 | gói pin nhưng KHÔNG CÀI bị coi là khớp *(hình dạng `pytest-subtests`)* | **ĐỎ** 1 | `test_a_critical_pin_that_is_not_installed_at_all_is_red` |
| M3 | file không pin nào → báo SẠCH thay vì `exit 2` | **ĐỎ** 1 | `test_a_requirements_file_with_no_pins_cannot_report_clean` |
| M4 | file không đọc được → báo SẠCH | **ĐỎ** 1 | `test_a_missing_requirements_file_cannot_report_clean` |
| M5 | `critical_offenders` luôn rỗng | **ĐỎ** 3 | 3 ca |
| M6 | `--names-only` in cả pin không quan trọng | **ĐỎ** 2 | `test_drift_in_a_non_critical_pin_...`, `test_names_only_...` |
| M8 | luôn in "không pin nào lệch" ở đường người-đọc | **ĐỎ** 2 | 2 ca |
| M9 | đỏ mà không nói đường ra (`pinned-import`) | **ĐỎ** 1 | `test_a_drifted_critical_pin_is_red` |
| M10 | bỏ `migration` khỏi `DRIFT_CODE_TIERS` | **ĐỎ** 2 | `test_a_code_tier_alone_...`, `test_the_waiver_is_loud_...` |
| M12 | miễn trừ im lặng (không ghi `drift-waived`) | **ĐỎ** 1 | `test_the_waiver_is_loud_and_recorded` |
| M13 | lệch pin không bao giờ chặn | **ĐỎ** 2 | 2 ca |
| M14 | không ghi khoá `pin-drift=` ra summary | **ĐỎ** 1 | `test_the_waiver_is_loud_and_recorded` |
| M7 | siết `PIN_RE` chỉ nhận tên chữ thường | XANH — **TƯƠNG ĐƯƠNG** | — |
| M11 | bỏ `api` khỏi `DRIFT_CODE_TIERS` | **XANH — LỌT** | — |
| M15 | thêm `guard` vào `DRIFT_SHIPPING_PROOF` | **XANH — LỌT** | — |

M7 là đột biến **tương đương**, không phải lỗ hổng: cả 14 pin trong
`requirements-dev.txt` đều viết thường (`grep -cE "^[A-Z]" = 0`), nên siết regex
không đổi hành vi trên file thật.

### Hàng GIỮ tính chất — phải XANH

| # | đột biến | kết quả |
|---|---|---|
| C1 | đổi chữ nhãn `"python đang chạy:"` (không ai assert) | XANH 12/12 |
| C2 | `sorted(pins)` → `list(pins)` — vẫn khảo sát đủ mọi pin | XANH 12/12 |
| C3 | thêm `uvicorn` vào `IMPORT_CRITICAL` — `fastapi` vẫn critical | XANH 12/12 |
| C4 | thêm `contract` vào `DRIFT_CODE_TIERS` — `migration` vẫn nằm trong | XANH 12/12 |

Cây sạch sau khi khôi phục toàn bộ: **12 passed**. Bốn hàng GIỮ đều xanh, nên
12 hàng đỏ ở trên là đỏ vì đúng tính chất chứ không vì bất kỳ va chạm nào.

**Kết luận câu 3: có răng — 12/14 hàng cắn được bị bắt, 1 tương đương, 2 lọt.**

---

## Ba việc nên làm tiếp (không cái nào là blocker)

### B1 — hai danh sách chặng không được ca nào ghim (M11, M15)

`DRIFT_CODE_TIERS=(api migration postgres e2e)` và
`DRIFT_SHIPPING_PROOF=(pinned-import docker)` là hai danh sách viết tay, và
`test_a_code_tier_alone_matches_the_measured_drift_state` chỉ chạy `migration`.
Không ca nào phát biểu về thành viên của hai danh sách.

Khai thác đo thật, trên `main` sau merge:

```
thêm 'guard' vào DRIFT_SHIPPING_PROOF
  pytest tests/test_pin_drift_gate.py  -> 12 passed        (mù hoàn toàn)
  scripts/gate.sh guard migration      -> rc=0  "Tất cả chặng đã chạy đều ĐẠT."
cây sạch, cùng lệnh
  scripts/gate.sh guard migration      -> rc=1
```

`guard` chỉ quét file, không nói gì về thư viện — nhưng nó vừa được nhận làm bằng
chứng "đã chạy đúng bản ship". Cùng loại: bỏ `api` khỏi `DRIFT_CODE_TIERS` cũng
XANH 12/12, mà `api` chính là chặng chạy 2370 ca và là chặng trong tiêu đề của
chính PR.

Cổng **hiện tại đúng** — tôi đo `scripts/gate.sh api` trên `main` sạch ra rc=1 kèm
phán quyết. Đây là lỗ hổng phía *test*, hình dạng "cổng liệt kê theo tên mù với
cái thêm sau". Tiêu chí đóng: một ca sinh danh sách từ `STAGES` rồi khẳng định
từng chặng thuộc đúng nhóm nào, hoặc chạy `gate.sh <mỗi code tier>` và đòi rc=1.

### S2 — parser rơi im lặng pin có extras

`services/api/requirements-dev.txt` có **14** dòng pin, cổng khảo sát **12**:

```
BỊ RƠI IM LẶNG: ['psycopg[binary]==3.2.3', 'uvicorn[standard]==0.34.0']
```

`PIN_RE` không cho `[` vào tên gói, nên cả dòng bị bỏ chứ không phải chỉ bỏ phần
extras như docstring nói. Hôm nay vô hại: hai gói đó cố ý không nằm trong
`IMPORT_CRITICAL`.

Vấn đề là `test_the_survey_counts_every_pin_in_the_shipping_file` tính `expected`
bằng **chính hình dạng regex của parser**, nên nó đồng ý với parser theo cấu tạo
và không bao giờ thấy được chuyện này. Ngày ai đó ghim
`sqlalchemy[asyncio]==...` hoặc `pydantic[email]==...`, pin quan trọng đó biến
mất khỏi khảo sát và cổng báo SẠCH — đúng hình dạng "lọt im lặng" mà file này
sinh ra để chống. Tiêu chí đóng: `expected` đếm bằng cách độc lập với `PIN_RE`
(ví dụ đếm mọi dòng chứa `==`), hoặc parser xử lý extras.

### S3 — `gate_merge.sh` không đọc khoá `pin-drift`

```
grep -c 'pin-drift' scripts/gate_merge.sh  ->  0
```

Cổng gộp chỉ đọc `skipped=`, `skipped-stage=`, `passed=`. Nên một lượt
`drift-waived` và một lượt `clean` cho ra dòng kết luận giống hệt nhau ở chỗ
người bấm nút merge đọc. Chữ LƯU Ý vẫn hiện trên màn hình vì gate_merge không nuốt
stdout của gate.sh — nên đây là *chưa dùng*, không phải *im lặng*. Đối chiếu:
`skipped-stage=` được đối xử đúng như cần ở `scripts/gate_merge.sh:282`. Tiêu chí
đóng: gate_merge in ra waiver, hoặc từ chối lượt `drift-waived` khi có `--strict`.

---

## Cái bản đo này KHÔNG chứng minh

- Không nói lệch ở một pin cụ thể **có** đổi hành vi hay không. Tôi chỉ chứng minh
  được một trường hợp (fastapi 0.115.6 vs 0.135.3, bằng docker thật). Bốn pin còn
  lại — alembic, pytest, pytest-subtests, sqlalchemy — tôi **chưa** chạy hai bản
  để so.
- Không đo chặng `postgres` và `e2e` (hai code tier còn lại). Chúng nằm trong
  `DRIFT_CODE_TIERS` theo mặt chữ; tôi không chạy chúng.
- Không đo trên máy có pin khớp hoàn toàn, nên nhánh "không lệch → cổng im" của
  `test_a_code_tier_alone_...` chỉ được chứng minh gián tiếp qua các ca tổng hợp
  (`test_a_matching_critical_pin_is_green`), không qua một máy thật.
- Lượt giả lập "máy không có docker" dùng stub `docker` exit 1, không phải một máy
  thật thiếu docker.
