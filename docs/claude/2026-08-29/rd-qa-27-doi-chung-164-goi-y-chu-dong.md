# rd-qa-27 · Đối chứng PR #164 (F32 · gợi ý chủ động)

`protocol_version: v1` · verdict: **PASS** · lane QA/QC

## Lý do, viết trước phần chi tiết

PASS. Cổng đầy đủ xanh trên chính bản hợp nhất `#164 ⊕ main@184820c`, không chỉ
trên nhánh PR. Bốn khẳng định trung tâm của PR đều **tự tái lập được**: route
không tồn tại trước PR và tồn tại sau, cơ chế grounding **đỏ được** khi làm hỏng
nó, quyền chặn đúng người ngoài lẫn người mới được mời, và Gemini **thật** giữ
trong danh mục 8/8 lượt. `basis` khớp từng đồng với `GET /recap` — hai đường đọc
độc lập cùng một sổ, ra cùng một số.

Không có blocker. **Hai điều Lead cần biết trước khi đọc F32 là "đã xong":**

1. **Chưa màn hình nào gọi route này.** F32 là hợp đồng backend, chưa phải tính
   năng người dùng thấy. PR nói thẳng điều đó ("để lane UI nối vào") nên đây là
   vỏ được khai báo, không phải vỏ bị giấu — nhưng đừng đếm F32 vào danh sách
   tính năng chạy được cho tới khi có màn gọi nó.
2. **#161 đã vào main sau khi PR này được viết**, và #161 sửa đúng
   `group_recap` — hàm F32 đọc số tiền từ đó. Tôi đã đo lại trên bản hợp nhất
   với main hiện tại: không vỡ. Nếu main còn dịch tiếp trước lúc merge thì số
   đo này hết hiệu lực ở đúng điểm đó.

## Đo trên cái gì

```
đo tại   5c40ad6  (nhánh backend/rd-be-14-goi-y-chu-dong, chưa merge)
và tại   184820c ⊕ 5c40ad6  (bản hợp nhất, merge sạch, không xung đột chữ)
sha main 184820c  — ĐÃ ở main
```

PR được viết trên `origin/main@6c7d2ab`; tới lúc tôi đo, main đã đi thêm 6 commit
(#159, #160, #163, #168, #161, #170). Vì thế mọi con số dưới đây đo **hai lần**:
một lần trên nhánh PR, một lần trên bản hợp nhất với main hiện tại.

## Cổng đã chạy thật

| Cổng | Trên nhánh PR `5c40ad6` | Trên `184820c ⊕ 5c40ad6` |
|---|---|---|
| `pytest services/api/tests tests -q` | 1193 passed, 272 skipped, 4591 subtests | **1214 passed**, 277 skipped, 4592 subtests |
| `tests/postgres` (DB riêng, `MOBILE_REQUIRE_POSTGRES_TESTS=1`) | **236 passed, 0 skipped** | **242 passed, 0 skipped** |
| `cd apps/mobile && npm test` | — | **498 pass, 0 fail, 0 skipped** |
| `tests/live/test_suggestion_gemini_live.py` (`MOBILE_REQUIRE_GEMINI_TESTS=1`) | **4 passed in 18.64s** — Gemini THẬT | — |
| `scripts/repo_guard.py tree HEAD` | — | **passed, 612 file scan(s)** |
| `scripts/check_actor_headers.py` (cổng #163) | — | **ĐẠT — 61 lời gọi đều gửi X-Actor-ID** |

DB riêng `qa164` / `qa164n` tạo mới rồi `alembic upgrade head` từ đầu — không
đụng DB dùng chung `mobile`, không stamp lại revision của ai.

## Đối chứng: route chết trước PR, sống sau PR

Hai máy chủ uvicorn thật, cùng một DB, khác đúng một commit:

```
before  0fbf500          /openapi.json | grep -c 'contexts/{context_id}/suggestion'  ->  0
after   0fbf500⊕5c40ad6  /openapi.json | grep -c 'contexts/{context_id}/suggestion'  ->  1
```

## Grounding có đỏ được không — ba đột biến, ba kết quả khác nhau

Chạy trên `tests/domain/test_suggestion_grounding.py` (30 ca, xanh khi sạch).
Mã sản phẩm được khôi phục sau mỗi lượt; `git status` sạch (0 file sửa) trước
khi đo tiếp, và 30/30 xanh trở lại.

| Đột biến | Ca đỏ | Số ca đỏ |
|---|---|---|
| **A** · lọc id lạ thay vì từ chối cả thẻ | `..._rejects_the_whole_card`, `..._caught_before_the_display_limit_truncates_it` | 2 |
| **B** · kiểm danh mục **sau** khi cắt `MAX_STOPS` | `..._caught_before_the_display_limit_truncates_it` | **1** |
| **D** · copy nguyên payload của model rồi ghi đè | `..._a_key_the_contract_never_named_cannot_reach_the_payload` | 1 |

Điểm đáng giá nằm ở B: nó đỏ ở **đúng một ca, khác với A**. Nghĩa là "kiểm trước
khi cắt" là một khẳng định riêng chứ không phải hệ quả ăn theo của "từ chối thay
vì lọc" — đúng như PR nói. Một bộ test mà A và B đỏ cùng chỗ thì không phân biệt
được hai lỗi đó, và bảng này chứng minh bộ test hiện tại phân biệt được.

PR khai A làm đỏ 3 ca; tôi đo được 2. Khác biệt nhỏ, không đổi kết luận, và
hướng thì đúng: cổng đỏ được.

## Đi bộ như người thật — `tests/qa/rd-qa-27/f32-di-bo.py`

Dựng lịch sử nhóm qua chính route mà điện thoại gọi (tạo nhóm → mời → nhận lời
mời → hai buổi đi đã kết thúc → khoản chi → `confirm` với allocation **do máy chủ
trả về**, không tự chia lại), rồi đọc thẻ.

```
GET /contexts/{id}/suggestion  (An, ACTIVE)  -> 200  suggested=true  source=ai

PASS  stops present                          2 stops
PASS  no lat/lng anywhere in payload
PASS  every place_id is in the catalogue     ids=['p-tiem-nuong-xom-lao', 'p-lung-chung-cafe']
PASS  reason/verdict paired @ 18:30          reason=set verdict=hop
PASS  reason/verdict paired @ 20:30          reason=set verdict=hop
PASS  basis.outing_count matches recap       basis=2 recap=2
PASS  basis.split_total_vnd matches recap    basis=1,160,000 recap=1,160,000
PASS  basis money are integers               avg=290000
PASS  basis.top_categories non-empty         ['cafe', 'quan-an-local']
```

`basis` là đường đọc thứ hai vào cùng một sổ; `GET /recap` là đường thứ nhất. Hai
đường ra **1.160.000** như nhau, và `avg = 1.160.000 / 4 = 290.000` là chia lấy
nguyên, số nguyên đồng. Không có `Decimal`, không có `float` nào lọt ra wire.

Quyền:

```
Cuong  (chưa bao giờ là thành viên)  -> 403 permission_denied / is_group_member
Dung   (INVITED, chưa nhận lời mời)  -> 403 permission_denied / is_group_member
không gửi X-Actor-ID                 -> 401
An đọc thẻ của nhóm khác             -> 403
```

Người mới bấm link mời mà chưa nhận **không** kéo được năm con số tóm tắt cả
nhóm ra. Đó là khẳng định đáng giá nhất của bề mặt này và nó đứng vững.

## Gemini thật, lặp 8 lượt — `tests/qa/rd-qa-27/f32-gemini-that.py`

Một lượt xanh chỉ chứng minh một lượt xanh. Đầu ra bất định thì phải đo bất định:

```
LIVE GROUNDING, 8 real Gemini calls
   1  reason=ok  stops=2  verdicts=[hop,hop]      ok
   2  reason=ok  stops=1  verdicts=[hop]          ok
   3  reason=ok  stops=3  verdicts=[hop,hop,tam]  ok
   4  reason=ok  stops=1  verdicts=[hop]          ok
   5  reason=ok  stops=2  verdicts=[hop,hop]      ok
   6  reason=ok  stops=2  verdicts=[hop,hop]      ok
   7  reason=ok  stops=2  verdicts=[hop,hop]      ok
   8  reason=ok  stops=2  verdicts=[hop,hop]      ok

  reason distribution: {'ok': 8}
  rounds with a problem: 0/8
```

Số chặng dao động 1–3 và verdict dao động `hop`/`tam` — model thật sự thay đổi
đáp án giữa các lượt, nên 8 lượt sạch là 8 lượt sạch chứ không phải một đáp án
cache lại. Không lượt nào ra id ngoài danh mục, không lượt nào có nửa cặp
`reason`/`verdict`, không lượt nào có toạ độ.

Cách ly giữa hai nhóm, với một tiêu đề mồi không ai gõ trúng ngẫu nhiên:

```
A basis: outings=2 total=1,160,000  titles=['SENTINEL-...', 'SENTINEL-...']
B basis: outings=1 total=  300,000  titles=['Vung Tau']
PASS  group B never sees A's sentinel title
PASS  group B outing_count/total are its own
PASS  An (nhóm A) đọc thẻ nhóm B -> 403
```

**Một cảnh báo giả do chính phép đo đẻ ra, tôi ghi lại vì nó dễ lặp:** bản đầu
của probe tìm chuỗi mồi trong **toàn bộ** response và báo đỏ 8/8 lượt. Chuỗi đó
nằm ở `basis.recent_titles` — dữ liệu của chính nhóm trả về cho chính thành viên
nhóm đó, tức là đúng hợp đồng. Probe đã sửa để chỉ soi phần **model tự viết**
(`title`, `when_text`, `note`, `reason`). Đây là kiểu "tìm thấy dữ liệu của mình
rồi gọi là rò rỉ" — đo lại phạm vi trước khi mở phiếu.

## Ô CHƯA quét

- **Không màn hình nào gọi route này** (`grep -rn suggestion apps/mobile/src` ra
  2 dòng comment, 0 lời gọi). Nên chưa quét được: thẻ hiện lên trông thế nào,
  `suggested:false` hiển thị ra sao, `reason`/`verdict` có bị in lệch không.
- **Không quét giao diện** — không có UI để quét. Không chạy `imp detect`, không
  chạy canary; không có số nào về UI trong báo cáo này.
- **`reason: "unavailable"` và `"ungrounded"` chưa thấy trên máy chủ thật.** Tôi
  chỉ chứng minh chúng qua đột biến ở tầng domain; đường đi từ model hỏng → 200
  `suggested:false` chưa được đi bằng một model thật đang hỏng.
- **Chưa đo tải/độ trễ.** Mỗi lượt gọi là một lần gọi Gemini đồng bộ trên đường
  mở màn hình; 8 lượt của tôi không nói gì về 50 người mở cùng lúc.
- **Chưa đâm prompt injection** qua tiêu đề buổi đi hay caption check-in — dữ
  liệu nhóm đi thẳng vào prompt. Grounding chặn được *id bịa*, nhưng `title` và
  `note` là chữ tự do do model viết. Đề xuất mở một lượt `ai-system-testing`
  riêng cho đường đó; không chặn PR này.
- **Mã QR chưa được quét bằng app ngân hàng thật** — vẫn còn nguyên trong danh
  sách chưa quét, không liên quan PR này nhưng chưa ai đóng.

## Không tự sửa gì

Không sửa mã sản phẩm, không sửa test, không vá package, không mock-stub
dependency. Ba đột biến đều được khôi phục bằng bản sao nguyên gốc và xác nhận
`git status` sạch + 30/30 xanh trở lại trước khi đo tiếp. `GEMINI_API_KEY` đọc
từ `/home/lakiet/mobile/.env`, không in ra, không commit.
