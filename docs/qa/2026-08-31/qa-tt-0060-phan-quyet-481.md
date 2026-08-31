# PASS — #481 (devops-tt-0032), xác minh SAU merge

**Lý do, viết trước phần chi tiết:** ba tuyên bố đo được của PR đều tái lập độc lập
được bằng tay, trên chính file thật, không dùng con số nào của tác giả. Cổng cũ ra
**0** finding trên `lane.py` trước vá, cổng mới ra **9**, và **0** sau vá — đúng như
PR nói. Bộ test mới **không phải test giả**: 8/9 đột biến có hệ thống làm nó đỏ, kèm
một đối chứng âm. Cổng đầy đủ xanh trên cả SHA của PR lẫn `main` sau merge.

Kèm hai thứ PR không nói, và một thứ tôi nói sai rồi tự sửa:

- **Một nhánh mã không có ca test nào phủ** (gợi ý, không phải blocker): xoá phân giải
  bí danh ở call site `AnnAssign` thì cả 21 ca vẫn xanh. Mã **đúng** ở nhánh đó — chỉ
  là không ca nào chứng minh nó.
- **Lỗi này vẫn còn sống ở bản đang CHẠY** (phiếu riêng cho devops, không chặn PR
  này): `~/agent-harness/agent_supervisor.py:209`. PR tự ghi "không cổng nào trong
  repo này chạy trên harness — khoảng trống đó là thật"; tôi đo được khoảng trống đó
  đang có người ở trong.
- **Bảng đột biến đầu tiên của tôi SAI** và tôi giữ lại câu chuyện đó ở dưới, vì cách
  nó sai là một cái bẫy chung.

## Đo trên cái gì

```
đo tại   b20cc4ac6f42d4a659030f7a85643c0e774e24a7   (head PR lúc nhận việc)
sha này  ĐÃ bị squash vào main thành 7da3907, lúc 2026-08-31T05:27:10Z —
         tức là giữa lúc tôi đang chạy cổng đầy đủ.
```

Nên phán quyết này **không phải cổng chặn merge**; nó là xác minh sau merge. Neo
không đặt vào SHA (squash làm SHA mồ côi) mà đặt vào **blob của đúng file PR sửa**:

```
blob bản tôi đo          ed1f92fd03355d04e3ce395940cae813c69bc519
blob bản đang trên main  ed1f92fd03355d04e3ce395940cae813c69bc519   ← giống hệt
```

Tree của hai commit khác nhau, vì #480 merge xen vào giữa. File thì không đổi một
byte, nên mọi số dưới đây chuyển nguyên vẹn sang `main`.

## Đối chứng: cổng cũ có thật sự mù không

Không đọc lời PR. Lấy máy dò bản `origin/main` **trước** PR và bản của PR, chạy cả
hai lên chính hai phiên bản `lane.py` của repo harness:

| file thật | cổng CŨ (trước #481) | cổng MỚI (#481) |
|---|---|---|
| `lane.py` TRƯỚC vá (`58b3ec4`) | **0** | **9** |
| `lane.py` SAU vá (`f874225`) | 0 | 0 |

9 dòng đó nằm ở `run_task()` ×5, `Lane()`, `watch()`, `serve()` ×2 — trong đó
`watch()` là dòng gọi `kill()`. Con số 0 ở cột trái là bằng chứng lỗi có thật trước
khi có bản vá: một cổng đang chạy đọc file đó là sạch.

## Bộ test mới có phải test giả không — 9 đột biến

Quét **toàn bộ** bề mặt bí danh mà PR thêm vào, bỏ từng mảnh một, không chọn một ca
để thử:

| đột biến | kết quả | ca đỏ |
|---|---|---|
| M0 đối chứng âm — không đổi gì | XANH | 21 passed |
| M1 gỡ hẳn phân giải bí danh | **ĐỎ** | 3 ca |
| M2 bỏ bước lọc docstring | **ĐỎ** | `bí danh có docstring` |
| M3 bỏ nhánh `now = time.time` | **ĐỎ** | `bí danh gán thẳng` |
| M4 phân giải theo TÊN thay vì theo THÂN | **ĐỎ** | `hàm tên giống nhưng trả monotonic` |
| M5a bỏ `bi_danh` ở call site `Assign` | **ĐỎ** | 3 ca |
| M5b bỏ `bi_danh` ở call site `AnnAssign` | **XANH** | — không ca nào phủ |
| M5c bỏ `bi_danh` ở call site `BinOp` (phép trừ) | **ĐỎ** | 3 ca |
| M6 nới thành hai hop | **ĐỎ** | `bí danh của bí danh` |

M4 là ca đáng giá nhất: nó chứng minh tuyên bố *"phân giải theo cái tên TRẢ VỀ, không
theo cái tên được gọi"* được **cưỡng chế**, chứ không chỉ được viết trong docstring.
Cho một hàm tên `now()` trả `time.monotonic()` bị gắn nhãn đồng hồ treo tường thì
`PHAI_THA` đỏ ngay — nghĩa là bản ĐÚNG bị báo oan sẽ bị bắt.

M6 chứng minh `MU_CO_CHU_DICH` làm đúng việc nó hứa: nới máy dò mạnh lên thì ca "lỗ
hổng đã biết" đỏ và đòi người ta chuyển sang `PHAI_BAT` một cách có ý thức. Đây là
kiểu ghi tài liệu duy nhất không tự mục đi.

### Nhánh không ai phủ: M5b

Ba call site đều được truyền `bi_danh`. Hai trong ba có ca test bắt được khi gỡ; cái
thứ ba — mốc gán **có chú kiểu** — thì không:

```python
def run():
    started: float = now()      # AnnAssign, không phải Assign
    return now() - started
```

Mã của PR xử lý đúng hình dạng này (chạy tay: **1 finding**). Chỉ là `PHAI_BAT` không
có ca nào dùng `AnnAssign`, nên nếu ai đó sau này sửa hỏng đúng dòng 242 thì cổng im
lặng. Một dòng thêm vào `PHAI_BAT` là đủ. **Suggestion, không phải blocker** — không
thuộc 5 loại blocker của charter, và không có lỗi nào đang sống nhờ nó.

### Bảng đột biến đầu tiên của tôi sai, và vì sao

Lượt chạy đầu tôi báo **hai** ô xanh: M5b và M5c. M5c xanh là vô lý — nó gỡ phân giải
ở chính phép trừ. Chạy riêng lại thì nó đỏ 3 ca.

Nguyên nhân: 9 đột biến chạy cách nhau ~0.15 giây, và mọi bản thay thế của tôi đều
làm file dài thêm **đúng 1 byte**. Cache viết-lại-assert của pytest trong
`tests/__pycache__` xác thực bằng `(mtime giây, cỡ file)` — hai đột biến liên tiếp
cùng giây, cùng cỡ, nên nó chạy lại **bytecode của đột biến trước**. Thước của tôi
hỏng chứ không phải sản phẩm hỏng.

Bảng ở trên là bản chạy lại, xoá `tests/__pycache__` trước mỗi lượt, và có thêm M0
làm đối chứng âm. Ghi lại đây vì một bảng đột biến toàn xanh trông y hệt "mã được
gác kém", và người đọc không có cách nào phân biệt nếu người đo không nói.

## Lỗi vẫn đang sống ở bản ĐANG CHẠY — phiếu riêng, không chặn PR này

Chạy máy dò của #481 (bản đã merge) lên mọi file `.py` được git theo dõi:

| cây | file quét | finding |
|---|---|---|
| `~/agent-harness` (bản harness đang chạy) | 17 | **3**, ở 2 file |
| repo này, `scripts/` (phạm vi cổng) | 38 | 0 |
| repo này, `services/api/app/` (ngoài phạm vi cổng) | 130 | 0 |

Chỗ nặng:

```
~/agent-harness/agent_supervisor.py:209
    emit("INFO", f"{agent} ket thuc sau {int(time.time() - started)}s, exit={code}")
```

Đây là **cái bẫy hai bản sao**, không phải một chỗ bị bỏ quên:

- `scripts/agent_supervisor.py` trong repo này: đã vá đủ (`time.monotonic` ở 6 chỗ,
  từ #470 và #477). Máy dò ra 0.
- `~/agent-harness/agent_supervisor.py`: commit cuối chạm nó là `487f0c6`
  (2026-08-28), **chưa từng nhận #470 hay #477**. Không có một chữ `monotonic` nào.
  Hai bản lệch **212 dòng**.
- Bản đang chạy là bản chưa vá: `agy_test_pr.sh:31` giải ra
  `${AGENT_HARNESS:-$HOME/agent-harness}/agent_supervisor.py`.

PR #481 tự ghi rất thẳng rằng "không cổng nào trong repo này chạy trên mỗi thay đổi
của harness, và khoảng trống đó là thật". Đóng góp của tôi chỉ là đo xem khoảng trống
đó đang trống hay đang có người: **đang có người**. Đã gửi `bug-to devops`.

Hai finding còn lại ở `~/agent-harness/tests/test_phat_hien_hong.py:104,368` là ca
test tự đo thời gian phát hiện (`assertLess(time.time() - started, 30)`). Đồng hồ lùi
làm chúng xanh vô điều kiện. Nhẹ, ghi cho đủ, không phải phiếu.

## Cổng đã chạy

```
b20cc4a (head PR)
  python3 -m pytest services/api/tests tests -q
      2877 passed, 583 skipped, 5272 subtests passed, 0 failed   (316.39s)
  python3 -m pytest tests/test_khong_do_khoang_bang_dong_ho_treo_tuong.py -q
      21 passed
  ruff check <file PR sửa>      All checks passed!      (ruff 0.9.2, bản ghim)
  ruff format --check <file>    1 file already formatted
  python3 scripts/repo_guard.py tree HEAD    passed, 1340 file scan(s)

7da3907 (main sau khi #480 và #481 cùng merge)
  python3 -m pytest services/api/tests tests -q
      2877 passed, 583 skipped, 5272 subtests passed, 0 failed   (308.90s)
```

PR ghi "580 skipped"; tôi đo 583 ở cả hai chỗ. Chênh lệch là do main nhích giữa lúc
đo, không phải do PR. Số ca pass và số fail khớp tuyệt đối.

Sau khi đột biến xong, file được khôi phục từ bản chép ở `/tmp` (không dùng
`git checkout`, để không xoá mất thứ đang dở), và xác nhận bằng sha256 khớp bản gốc:
`43187253d48d2348a1976fb6a1407419dcc68de00462d76f126c4275b654ae02`. `git status` sạch.

## Ô CHƯA quét

- **Bản vá `lane.py` của harness** (`f874225`) không được kiểm ở đây. Tôi đọc file đó
  làm dữ liệu cho máy dò, và tôi có chạy máy dò lên nó — nhưng tôi **không** chạy bộ
  test hành vi `tests/test_dong_ho_nhay_khong_giet_lane.py` của harness, nên con số
  "TRƯỚC vá FAILED, SAU vá OK (3 ca)" trong mô tả PR **vẫn là lời của tác giả**, chưa
  được tôi tái lập. Nó nằm ngoài repo này và ngoài phạm vi diff của PR.
- **Không quét** `apps/mobile` (PR không chạm JS/TS; `npm test` không chạy lượt này).
- **Không quét** tầng `tests/postgres` (không dựng Postgres; PR không chạm persistence).
- **Không có bằng chứng hành vi nào** về việc lỗi đồng hồ này đã từng giết một lane
  thật trong sản xuất. Cả #470, #477, #481 đều dựng lại bằng đồng hồ giả. Giả thuyết
  đồng hồ cho vụ 5 lane chết lúc 07:44:50 đã bị bác bằng một lane sống sót — và như
  PR ghi đúng, một lane sống sót **không** bác bỏ được kiểu hỏng này nói chung, vì nó
  phụ thuộc tuổi từng lane.
- **Mã QR chưa được quét bằng app ngân hàng thật.** Vẫn mở, không liên quan PR này.

## Phân loại theo 5 loại blocker

Không có blocker. `AnnAssign` chưa có ca test là suggestion (không sai tiền, không
rò rỉ, không hỏng tính hợp lệ thí nghiệm, tái lập được). Bản sao harness chưa vá là
**không tái lập được → hết**: nó tái lập được, đã có phiếu, và không thuộc diff này.
