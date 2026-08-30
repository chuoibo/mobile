<!-- QA verdict record; the authoritative copy is the PR comment. -->
# Phán quyết QA — PR #264 (rd-be-26)

| | |
|---|---|
| PR | #264 `backend/rd-be-26-paid-by-va-recorded-by-tu-than-request` |
| commit đã test | `5c4f71bb8f4a69e91d5bce4f3f0db023a183af05` |
| nền của commit đó | `9590e51` (nhánh CHƯA merge) |
| cây gộp đã kiểm | main `cac18a3` và main `5a1594f` |
| protocol_version | v1 |
| verdict | **PASS** |
| blocker còn mở | không |
| đăng tại | comment trên PR #264 (bản chính thức của phán quyết) |

---

# PASS

**Lý do:** đối chứng đỏ-trước/xanh-sau tái lập được đúng như PR mô tả (4 đỏ trên nền chưa sửa, 18 xanh sau), bảng đột biến 13 hàng đúng màu **kể cả ba hàng giữ-tính-chất phải xanh**, và tôi đã tự đếm lại đường ghi thay vì tin câu "chỉ có một cửa" — nó đúng.

Đo tại `5c4f71b` (head đã đẩy của PR).
`5c4f71b` là **nhánh chưa merge**; nền của nó là `9590e51`, không phải main hiện tại.

> Ghi chú: worktree local của backend đang ở `1ce1eae` (đã rebase lên `bef0524`) **chưa đẩy**. Tôi test bản đã đẩy — nếu bạn đẩy tiếp thì phán quyết này hết hiệu lực.

## Câu tôi cố đánh đổ: "chỉ có một cửa"

Đây là lần thứ sáu của cùng khuôn (#235, #247, #253, #254, #260), nên tôi không đọc câu đó mà đếm lại:

```
ghi paid_by_id/recorded_by_id xuống DB   -> repository.py:2231-2232, trong save_expense_confirmation (:2200)
lời gọi save_expense_confirmation        -> ĐÚNG 1  (service.py:2068, trong confirm_expense)
guard nằm trên nó                        -> service.py:2037, cùng hàm
```

Claim đứng vững. Guard có 3 call site (1749, 1819, 2037); PR chỉ nới đúng cái ở `confirm_expense`, không đẻ bản sao thứ hai của luật — đúng hướng.

## Đỏ trước / xanh sau — tôi tự dựng lại, không đọc lại số của PR

Chép file test của PR (đã gỡ marker) sang cây nền `9590e51` (guard ở đó vẫn chỉ nhận `participants`):

```
nền 9590e51 (chưa sửa):  4 failed, 14 passed     <- DID NOT RAISE, cả tầng fake lẫn tầng live
head 5c4f71b (đã sửa):   18 passed
```

Bốn ca đỏ đúng là bốn ca của lỗ 1 + lỗ 2, ở cả hai tầng.

## Bảng đột biến — chạy tay, `MOBILE_TEST_DATABASE_URL` trỏ DB riêng của tôi

`ALL ROWS AS EXPECTED`, 13/13, và tôi đọc kỹ ba hàng cuối vì đó là thứ luật mới của Lead đòi:

```
GATED     whole guard removed            red   5 failed
GATED     paid_by_id dropped             red   2 failed, 16 passed   <- đúng 2 ca, không đỏ cả bảng
GATED     recorded_by_id dropped         red   2 failed, 16 passed   <- đúng 2 ca
... (7 hàng GATED/ELSEWHERE khác đều đỏ đúng)
UNCHANGED guard argument sorted+reordered green  18 passed
UNCHANGED refusal wording changed        green  18 passed
UNCHANGED roster loop thay set-comp      green  18 passed
```

Hai hàng "bỏ đúng một đối số" đỏ **đúng 2 ca** chứ không đỏ cả bảng — đó là thứ phân biệt "gác đúng id này" với "phản ứng vì có người đụng dòng này". Ba hàng xanh là thứ phân biệt cổng đo tính chất với cổng đo diff. Harness cũng tự phòng đúng hai bẫy đã cắn repo này: `assert s.count(old) == 1` (neo trùng) và chỉ đọc dòng tổng kết cuối (docstring chứa chữ "passed").

## Không làm mù cổng của PR trước

Chạy `tests/qa/qa-tt-0011/mutants.sh` (#263) trên cây gộp: `ALL ROWS AS EXPECTED`. PR này không làm câm cổng trước nó.

## Cây gộp — main đã đi hai lần trong lúc tôi đo

```
gộp với main cac18a3:  1941 passed, 35 skipped, 0 failed
gộp với main 5a1594f:  1945 passed, 35 skipped, 0 failed   (main mới nhất, gồm #267)
```

Merge sạch cả hai lần. Và vì #267 vừa làm tầng postgres **thật sự chạy** ca live dưới `tests/qa`, tôi chạy luôn `scripts/postgres_tier.sh` trên cây gộp: `ĐẠT tests/postgres` + `ĐẠT ../../tests/qa`, 89 passed — 18 ca của rd-qa-40 nằm trong đó, tức cổng này có người gác thật chứ không mồ côi.

## Lát cắt dọc chạy thật

Dựng uvicorn từ **chính build của PR** ở cổng 8264 (`openapi.json` đếm 52 route, không phải container 8099 cũ), rồi ghim `EXPO_PUBLIC_API_URL`:

```
npm run test:e2e   ->  7 pass, 0 fail, 0 skipped   (KHÔNG in "khong co server")
```

Gồm cả "một khoản chi đi hết đường tới link của khách". Đây là điều tôi lo nhất ở PR này: guard **chặt hơn** có thể làm hỏng lát cắt dọc nếu fixture dùng `paid_by_id` không phải thành viên active. Không hỏng.

```
apps/mobile npm test  ->  667/667 trên cả cây gộp lẫn main
```

## Hai ghi chú, không phải blocker

**1. `split_bill` còn một `paid_by_id` chưa kiểm — nhưng nó không ghi gì.**
`BillSplitRequest.paid_by_id` (schemas.py:181) đi vào `allocator_input_from_bill` làm `advancer_id` (service.py:1916) mà không qua roster. Tôi đã kiểm: `split_bill` **không** persist — cột `paid_by_id` chỉ có đúng một người ghi là `save_expense_confirmation`, và nó không gọi được từ đó. Nên đây là đường xem trước, không phải đường tiền. Không chặn PR này (PR không nhận phạm vi đó), nhưng đáng vào hàng đợi: nó đúng hình dạng "lỗ hổng ngủ chờ tính năng bật lên" — vô hại tới đúng ngày ai đó cho kết quả preview chảy vào sổ.

**2. Người đã rời nhóm giờ không thể là `paid_by_id` nữa.** Guard chỉ nhận `state == "active"`. Đây là hệ quả nằm ngoài câu "chặn người ngoài", nhưng nó **nhất quán** với cách `participants` đã hành xử từ #235 — nếu người rời nhóm không bị tính tiền được thì họ cũng không nên đứng tên người ứng tiền. Tôi coi là đúng, chỉ nêu để không ai bất ngờ.

## Ô CHƯA quét

- **Mã QR chưa được quét bằng app ngân hàng thật.** Vẫn mở, vẫn chỉ leader đóng được.
- Tầng Gemini live (35 skipped — thiếu `GEMINI_API_KEY` + `MOBILE_REQUIRE_GEMINI_TESTS=1`).
- Không quét giao diện/ảnh: PR này không chạm `app/web/` hay `apps/mobile/`.
- Chưa đâm concurrency (hai `confirm` đồng thời cùng expense) cho đường `paid_by_id` mới.

## Một lỗi của chính tôi, ghi ra để không ai đọc nhầm log

Lượt đầu tôi chạy `npm test` **có** ghim `EXPO_PUBLIC_API_URL=8264` và thấy 2 ca đỏ (`tai-anh-len.test.mjs`). Tôi suýt báo "main đỏ". Không phải: hai ca đó so chuỗi URL cứng `localhost:8099`, nên chính biến tôi đặt làm chúng đỏ. Bỏ biến ra: 667/667 trên cả hai cây. **Phép thử của tôi hỏng, không phải sản phẩm** — và cùng con số đó trên main chứng minh nó không đến từ PR này.
