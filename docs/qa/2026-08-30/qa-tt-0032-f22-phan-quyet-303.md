# PASS — #303 (F22 tầng phát hiện) tại `c7b55e2`

**Lý do:** bảng đột biến của PR tái lập được trên máy khác, DB khác (11/11 ĐỎ,
4/4 XANH), và năm đột biến **bổ sung** do QA tự viết cho những mặt PR không chạm
đều trả lời đúng: cửa kiểm quyền của route ghi tiền ĐỎ khi bị gỡ, hình học ô
vuông ĐỎ khi trả pixel thay phân số, trục sắp xếp ĐỎ khi bị đảo. Không tìm thấy
lỗi tiền, lỗi quyền riêng tư, hay lỗi cổng. Một lỗ hổng phủ (không phải lỗi sản
phẩm) và một ghi chú tương đương, cả hai đều là *suggestion*, không phải blocker.

**Cảnh báo quy trình, đọc trước phần kỹ thuật:** PR này đã được **merge lúc
12:01:20Z, giữa lượt đo của tôi**, khi chưa có phán quyết QA nào trên PR. Phán
quyết này vì vậy là **hậu kiểm**, không phải cổng. Xem mục 5.

| | |
|---|---|
| đo tại | `c7b55e2` (head của #303) và `0385a30` = `c7b55e2 ⊕ main@c11a765` |
| sha này | **ĐÃ ở main** — squash thành `7aa6dc8` lúc 2026-08-30T12:01:20Z |
| hậu kiểm tại | `main@7aa6dc8` |
| protocol_version | v1 |
| verdict | `PASS` |
| blocker còn mở | không |

Bảy file F22 (`domain/faces.py`, `api/service.py`, `api/repository.py`,
`media/face_detection.py`, `api/routes/faces.py`, `api/search_rate_limit.py`,
`scripts/mutation_rd_do_f22.py`) **giống hệt từng byte** giữa `c7b55e2` và
`7aa6dc8`, nên mọi số đo dưới đây chuyển thẳng sang main mà không phải đo lại.

---

## 1. Tầng nào đã THẬT SỰ chạy

| Tầng | Lệnh | Kết quả |
|---|---|---|
| Toàn bộ, cây gộp `0385a30` | `pytest services/api/tests tests -q` | **2455 passed, 0 failed** (521 skipped: postgres + node_modules vắng) |
| Toàn bộ trên main, **có tầng postgres** | idem + `MOBILE_REQUIRE_POSTGRES_TESTS=1` | **2958 passed, 0 failed, 40 skipped** |
| Tầng postgres F22 | `tests/postgres/test_bill_self_claim_postgres.py` + `test_face_boxes_privacy_postgres.py` | **22 passed, 0 skipped** |
| Tầng live, cascade Haar THẬT | `tests/live/test_face_detection_local.py` | **11 passed** |
| Mobile trên main | `cd apps/mobile && npm test` | **749 pass, 0 fail, 0 skipped** |
| Ratchet ruff trên main sạch | `tests/test_qa_scripts_are_ruff_formatted.py` | **4 passed** |

40 ca skip còn lại là tầng live Gemini (`GEMINI_API_KEY` +
`MOBILE_REQUIRE_GEMINI_TESTS=1`) — không thuộc phạm vi F22.

PostgreSQL: container riêng của lượt đo này (`qa303-pg`, cổng 5903), **không**
dùng DB chung — `conftest.py` của tầng postgres tự tạo schema riêng rồi xoá.

## 2. Bảng đột biến của PR — tái lập độc lập

`scripts/mutation_rd_do_f22.py`, chạy trong cây sạch, DB riêng:

```
11 BREAKS rows, 4 KEEPS rows.   →   11/11 RED ok, 4/4 GREEN ok, PASS
```

Bảng này tự bảo vệ đúng bốn kiểu hỏng mà repo đã trả giá: `ANCHOR-MISSING` (bảng
cũ), `ANCHOR-AMBIGUOUS` (vá nhầm bản sao), `RED-BUT-BROKEN` (đỏ vì `NameError`
chứ không vì tính chất), và từ chối chạy khi cây bẩn. **Bốn hàng KEEPS xanh** là
phần đáng tin nhất: một bảng toàn đỏ không phân biệt được "gác được tính chất"
với "đỏ mỗi khi file bị chạm".

## 3. Năm đột biến QA tự viết — những mặt PR không chạm

`tests/qa/qa-tt-0032-f22/mutation_bo_sung_303.py`. Cột *dự đoán* ghi TRƯỚC khi chạy.

| Đột biến | Dự đoán | Đo được | Đọc thế nào |
|---|---|---|---|
| `qa-claim-door-removed-entirely` — gỡ hẳn `_bill_for_actor` khỏi route ghi tiền | RED | **RED** | Cửa CÓ được gác. `record` bị ghi đè hai dòng sau nên xoá lời gọi là sửa đổi vô hình về cú pháp — vẫn bị bắt. |
| `qa-coords-emitted-as-pixels` — trả pixel thay phân số ảnh | RED | **RED** | Hình học response được khẳng định. |
| `qa-box-order-axes-transposed` — giữ tất định, đảo trục sắp xếp | GREEN | **RED** | **Tốt hơn dự đoán.** Trục "trên→dưới rồi trái→phải" mà docstring cam kết được gác thật, không chỉ tính tất định. |
| `qa-claim-list-dedupe-removed` — bỏ `dict.fromkeys` | GREEN | **GREEN** | **Lỗ hổng phủ** — xem mục 4. |
| `qa-claim-share-lock-dropped` — bỏ `with_for_update()` ở tầng share | GREEN | **GREEN** | **Tương đương**, không phải lỗ hổng — xem mục 4. |

## 4. Hai hàng XANH, hai kết luận khác nhau

### 4a. `dedupe` đúng nhưng KHÔNG được gác — *suggestion*

`item_keys` là một list. Không ca nào trong PR gửi khoá trùng, nên `dict.fromkeys`
trong `claim_bill_items` có mặt mà không có ai giữ. Bỏ nó đi, bộ test vẫn xanh.

"Có mặt nhưng không được gác" có hai cách đọc, và tôi đã **đo** để phân biệt
(`tests/qa/qa-tt-0032-f22/probe_bam_hai_lan.py`, PostgreSQL thật):

```
[probe] item_keys=['pho','pho']              -> HTTP 200, bill_item_shares = 1 hàng
[probe] item_keys=['pho','bia','pho','pho']  -> HTTP 200, bill_item_shares = 2 hàng
```

**Sản phẩm ĐÚNG.** Bấm hai lần không sập, không tạo hàng thừa. Đây thuần tuý là
lỗ hổng phủ: lần sửa sau gỡ mất `dict.fromkeys` sẽ đâm vào
`uq_bill_item_shares_item_participant` và không cổng nào kêu. Không phải blocker —
không sai tiền, không vi phạm spec — nhưng đáng một ca ba dòng.

### 4b. Khoá tầng share là THỪA — không phải lỗ hổng

Trước khi đọc XANH này thành thiếu ca đồng thời, tôi kiểm tương đương. Ba nơi ghi
`BillItemShare`:

- `create_bill` — tạo hoá đơn, chưa ai khác thấy nó, không có tranh chấp;
- `confirm_bill_assignments` — mở đầu bằng `select(Bill)…with_for_update()`;
- `claim_bill_items` — cũng mở đầu bằng `select(Bill)…with_for_update()`.

Hai writer có thể tranh chấp đều khoá **cùng một dòng `Bill`** trước khi chạm tới
bảng share, nên chúng đã xếp hàng từ đó. Khoá thứ hai ở tầng share không thêm
loại trừ nào. **XANH là câu trả lời đúng** — báo hàng này thành lỗ hổng sẽ là một
phát hiện giả.

## 5. Blocker quy trình: PR merge khi chưa có phán quyết QA

Charter: *"Bạn là cổng cuối trước `main`. Mọi PR phải qua bạn… Không PR nào được
merge khi chưa qua bạn."*

Mốc thời gian đo được:

```
#303 mở, 2 comment, không comment nào là phán quyết QA
12:01:20Z  #303 squash-merge vào main thành 7aa6dc8
           (lượt QA này đang chạy dở tầng postgres)
```

Comment duy nhất của Lead trên PR tự ghi *"Đã đo trước, **chưa phán quyết cuối**"*.
Nên đây không phải "QA chậm nên Lead merge thay" — không có phán quyết nào tồn tại
lúc merge.

Tôi **không** mở blocker code cho việc này: kết quả đo là PASS, và chặn một PR đã
đúng thì vô nghĩa. Nhưng nó thuộc loại blocker 1 (vi phạm spec/cổng) về mặt quy
trình, và tôi ghi ra vì nếu lần sau PR merge trước QA mà kết quả là FAIL thì hỏng
đã ở trên main rồi. Tiêu chí gỡ: hoặc phán quyết QA có mặt trước khi bấm merge,
hoặc charter được sửa để nói thật về thứ tự đang chạy.

Ghi chú đo lường: một lượt `npm test` của tôi trên cây gộp ĐỎ ở
`stacked-branch.test.mjs::"nhánh này không mang lại file nào đã có nguyên vẹn trên
origin/main"`. Đó là **hiện vật của phép đo**, không phải lỗi sản phẩm: #303 vừa
merge nên mọi file của nhánh đã nằm nguyên trên `origin/main`. Trên main sạch cùng
bộ đó ra **749 pass / 0 fail**.

## 6. Ô CHƯA quét

- **Chất lượng phát hiện khuôn mặt.** Tầng live xanh trên 4 ảnh mockup sản phẩm.
  Bốn ảnh không phải một phân phối. Haar bỏ sót mặt nghiêng và mặt ngược sáng.
- **Lệch phiên bản OpenCV.** Máy đo có `cv2 4.13.0`; ảnh Docker ghim `4.14.0.94`.
  Không ca nào phụ thuộc số khuôn mặt đếm được, nhưng tôi **không** chạy lại tầng
  live trong ảnh ghim ở lượt này — con số `4.14.0` trong mô tả PR là của tác giả,
  không phải của tôi.
- **Chưa có UI.** Không có màn nào để người dùng bấm vào ô của mình. PR nói rõ
  điều này và tôi xác nhận: đây là tầng máy chủ, chưa đi bộ được như người dùng.
- **Mối nối scan → gán món → chia tiền chưa đi hết bằng tay.** Tầng postgres
  chứng minh `split` của hoá đơn đã tự nhận món vẫn `Σ = tổng` và mọi số là số
  nguyên đồng; nhưng không có lượt đi bộ đầu-cuối qua HTTP thật cho đường
  *ảnh → ô vuông → nhận món → chia*.
- **Mã QR quét bằng app ngân hàng thật** — vẫn chưa ai làm, cần leader và một
  điện thoại thật (ADR-0010 mục 8). Không liên quan F22, nhưng còn mở.
- **Trần nhịp cửa thứ chín dưới tải thật.** Ca 20 luồng qua barrier là ca của PR,
  tôi tái lập qua bảng đột biến (`ninth-door-shares-the-eighth-door-window` ĐỎ),
  chứ không tự dựng phép đo tải riêng.

## 7. Tái lập

```bash
docker run -d --name qa303-pg -e POSTGRES_USER=mobile \
  -e POSTGRES_PASSWORD=mobile-dev-only -e POSTGRES_DB=mobile -p 5903:5432 postgres:16

export PG='postgresql+psycopg://mobile:mobile-dev-only@localhost:5903/mobile'

# cổng đầy đủ, tầng postgres KHÔNG được skip
MOBILE_TEST_DATABASE_URL="$PG" MOBILE_REQUIRE_POSTGRES_TESTS=1 \
  python3 -m pytest services/api/tests tests -q

# bảng đột biến của PR, rồi bảng bổ sung của QA
MOBILE_TEST_DATABASE_URL="$PG" python3 scripts/mutation_rd_do_f22.py
MOBILE_TEST_DATABASE_URL="$PG" python3 tests/qa/qa-tt-0032-f22/mutation_bo_sung_303.py

# probe bấm hai lần (tự chép vào tầng postgres, chạy, rồi dọn)
MOBILE_TEST_DATABASE_URL="$PG" python3 tests/qa/qa-tt-0032-f22/chay_probe.py
```

Cả hai script đều **từ chối chạy khi `services/api` bẩn** — đã kiểm chứng: một
file nháp bỏ quên làm script thoát mã 2 kèm tên file, thay vì đè lên nó.

## 8. Cái báo cáo này KHÔNG chứng minh

Bộ test xanh nói code làm đúng điều tác giả nghĩ; nó không nói người thật hiểu sản
phẩm. Repo vẫn **chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 do leader
gác lại). F22 hiện là một tầng máy chủ không có màn hình — nó chưa chứng minh được
gì về việc người dùng có bấm đúng ô của mình hay không.
