# QA — PR #311: cổng canh máy demo tụt lại sau main

- **protocol_version**: v1
- **PR**: #311 `devops/may-demo-theo-main` — head `e6a3c1d`, **đã MERGE** vào main ở `2862154`
- **Nhánh đo**: `qa3/tt-0033-do-cong-may-demo-311`, nền `15429c8` (= `origin/main` lúc đo)
- **Kỹ năng**: `bug-reproduction` (chặng 1), `ai-qa-review` (chặng 2)
- **Verdict**: **ĐẠT CÓ ĐIỀU KIỆN** — cổng bắt đúng sự cố thật; bộ test canh nó có
  bốn lỗ hổng, một trong số đó cho phép dựng lại **đúng** điểm mù mà PR sinh ra để bịt.

PR đã merge trước khi tôi đo, nên đây không phải phiếu chặn merge. Nó là câu trả
lời cho bốn câu Lead hỏi, cộng bốn thứ cần một PR tiếp theo.

---

## Tóm tắt bốn câu Lead hỏi

| # | Câu hỏi | Trả lời |
|---|---|---|
| 1 | Cổng có bắt được đúng sự cố thật không? | **CÓ** — rc=1, gọi đúng tên 4 route thiếu, trên container docker thật dựng từ commit tụt đúng 16 bước |
| 2 | `tests/test_demo_matches_main_gate.py` có răng không? | **CÓ NHƯNG THỦNG** — 7/11 đột biến không-tương-đương bị giết (64%); 4 lọt, xem chặng 2 |
| 3 | openapi.json hỏng → rc=2, không traceback? | **9/10 ca đúng.** 1 ca ra **rc=1 + traceback** — mã 1 nghĩa là "lệch", tức là chẩn đoán sai |
| 4 | `--no-fetch` có thật sự không fetch? | **CÓ**, và thiếu nó thì cổng neo vào `origin/main` **mới fetch**, không phải bản trên đĩa |

---

## Chặng 1 — dựng lại sự cố thật (`bug-reproduction`)

Không dùng stub. Dựng lại bằng hình học **đúng** của sự cố 30/08.

Trước hết xác nhận khoảng cách là thật, không phải con số trong mô tả PR:

```
$ git rev-list --count 65319b5..3e64ccf
16
```

`65319b5` đứng **đúng 16 commit** sau `3e64ccf` (main lúc xảy ra sự cố). Đó là
cây mà bộ container demo được dựng ra.

Dựng ảnh từ **cây sạch** tại commit đó — worktree riêng, không phải cây đang
đứng, vì `docker build` copy cả file WIP chưa commit và sẽ làm số route sai:

```
$ git worktree add --detach /tmp/qa3-demo-old 65319b5     # dirty? []  (sạch)
$ docker build -t qa3tt0033/api:65319b5 services/api      # tag RIÊNG của lane
$ docker run -d --name qa3tt0033-old -p 127.0.0.1:8393:8000 qa3tt0033/api:65319b5
$ curl -s :8393/openapi.json | jq '.paths|length'
58
```

Tag ảnh cố ý **không** phải `mobile-local/api:dev`: đó là tag của chính máy demo
8099, và `make up` từ worktree này sẽ ghi đè lên nó. Máy demo không bị chạm.

### Cổng MỚI trên máy chủ cũ đó

```
$ python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:8393 --ref 3e64ccf --json
!! Máy demo KHÔNG khớp 3e64ccf.
   3e64ccf khai 62 route, máy chủ phục vụ 58.
   THIẾU 4 route — leader bấm vào sẽ nhận 404:
      /areas
      /contexts/{context_id}/budget
      /contexts/{context_id}/messages/{message_id}/expense-draft
      /screenshots/scan
exit 1
```

**Đúng 4 route, đúng tên, đúng mã thoát.** Đây là điều kiện nghiệm thu của câu 1.

### Đối chứng bắt buộc — cổng CŨ trên CÙNG máy chủ đó

Một cổng đỏ chỉ có nghĩa nếu cổng cũ xanh trên cùng đầu vào. Chạy
`check_server_routes.py` **từ chính cây đã dựng ra ảnh**, đúng như `make smoke` làm:

```
$ cd /tmp/qa3-demo-old && python3 scripts/check_server_routes.py --url http://127.0.0.1:8393 --json
  "declared": 58, "served": 58, "missing": [], "extra": []
Route máy chủ: 58 phục vụ / 58 cây này khai — đủ, không thiếu route nào.
exit 0
```

Xanh-by-construction, dựng lại sống. Hai vế cùng đọc từ một cây cũ nên phép so
**không thể** đỏ — và nó đọc y hệt một cổng đang đạt.

### Vẫn cắn với main hôm nay

```
$ ... --ref origin/main --json
ref_routes 69 | served 58 | missing 11 | extra 0        exit 1
4 route gốc còn nằm trong danh sách thiếu? True
```

Cổng không bị ghim vào thời điểm đó: main nay khai 69 route, cổng vẫn đỏ đúng.

---

## Chặng 2 — bộ test có răng không (`ai-qa-review`)

Baseline: `9 passed in 4.06s`, chạy 3 lượt không rung, ca chậm nhất 1.01s.

Đột biến chạy trên **bản sao** `/tmp/qa3-mut` (worktree thật không bị sửa —
máy này có lane khác). Bản sao được kiểm baseline XANH trước, vì một bản sao
không trung thực thì mọi con số dưới đây vô nghĩa. Mỗi đột biến tự khẳng định
needle khớp **đúng 1 lần**, và bảng đòi **đúng ca** đỏ chứ không phải "có gì đó
đỏ".

| đột biến | kỳ vọng | thực tế | đúng ca | ghi chú |
|---|---|---|---|---|
| `BO-HUONG-THUA` | ĐỎ | ĐỎ | v | |
| `BO-HUONG-THIEU` | ĐỎ | ĐỎ | v | |
| `ZERO-ROUTE-LA-DAT` | ĐỎ | ĐỎ | v | |
| `GOP-MA-2-VAO-MA-1` | ĐỎ | ĐỎ | v | |
| `KHONG-IN-TEN-ROUTE-THIEU` | ĐỎ | ĐỎ | v | |
| `VE-THAM-CHIEU` — *hình dạng dễ đọc* | ĐỎ | ĐỎ | v | |
| `GIU-TINH-CHAT-DOI-HANG-SO` (đối chứng) | XANH | XANH | v | nới `RENDER_TIMEOUT` 180→300 |
| **`VE-THAM-CHIEU` — *viết cách khác*** | ĐỎ | **XANH** | **X** | lỗ hổng 1 |
| **`BO-KIEM-CONTENT-TYPE`** | ĐỎ | **XANH** | **X** | lỗ hổng 2 |
| **`BO-HAN-FETCH`** | ĐỎ | **XANH** | **X** | lỗ hổng 3 |
| **`FETCH-HONG-VAN-DI-TIEP`** | ĐỎ | **XANH** | **X** | lỗ hổng 4 |
| ~~`BO-XU-LY-HTTP-404`~~ | ĐỎ | XANH | — | **RÚT LẠI — tương đương**, xem dưới |

Hàng đối chứng cuối phải XANH và đã XANH: một bảng toàn đỏ không phân biệt được
"gác tính chất" với "ghim hằng số".

**Điểm đột biến: 7/11 = 64%** (mẫu số đã trừ ca tương đương).

### Rút lại một hàng — `BO-XU-LY-HTTP-404` là đột biến tương đương

Lượt đầu tôi tính nó là lỗ hổng. Sai, và lỗi ở phép thử của tôi:

```
$ python3 -c "import urllib.error; print(issubclass(urllib.error.HTTPError, urllib.error.URLError))"
True
```

`HTTPError` là con của `URLError`, nên gỡ mệnh đề `except HTTPError` thì mệnh đề
`except (URLError, OSError)` phía dưới vẫn bắt. Đo hai bản trên cùng đầu vào 404:

```
bản THẬT     (2, không traceback, '...trả về HTTP 404. Máy chủ có đang chạy đúng ảnh không?')
bản ĐỘT BIẾN (2, không traceback, '...Máy chủ chưa chạy. Gỡ:  make up')
```

Mã thoát y hệt. Chỉ **nhãn lỗi** kém đi (báo "chưa chạy" cho một máy chủ đang
chạy và trả 404). Đó là nợ chất lượng thông điệp, không phải lỗ hổng cổng — nên
nó ra khỏi mẫu số.

*Ghi lại vì suýt báo sai:* lượt đo tương đương đầu tiên của tôi chạy bản sao cổng
đặt ở `/tmp`, nên `REPO_ROOT` không phải repo git và **cả hai** bản đều chết ở
`ref_paths` với mã 2 vì lý do chẳng liên quan gì tới đột biến. Hai con số giống
nhau vì phép đo hỏng, không vì sản phẩm giống nhau. Đo lại trong cây git thật
mới tách được.

### Lỗ hổng 1 — canary neo vào **hình dạng chữ**, không vào hành vi (NẶNG)

Ca `test_ve_tham_chieu_doc_tu_ref_chu_khong_phai_cay_dang_dung` là ca **duy nhất**
gác nguyên nhân gốc của sự cố 30/08. Nó không chạy cổng; nó grep mã nguồn:

```python
src = inspect.getsource(gate.ref_paths)
assert "worktree" in src
assert 'REPO_ROOT / "services"' not in src
```

Cùng một vi phạm, viết bằng `.joinpath` thay vì toán tử `/`, đi lọt. Và không
phải lọt trên lý thuyết — tôi chạy bản đột biến đó **từ cây cũ 65319b5, soi đúng
container 58 route**:

```
$ python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:8393 --ref origin/main --json
  "ref": "origin/main", "ref_routes": 58, "served": 58, "missing": [], "extra": []
Máy demo khớp origin/main: 58 route, không thiếu, không thừa.
exit 0
```

Cổng khai `"ref": "origin/main"` và `ref_routes: 58` trong khi `origin/main` thật
có **69**. Đây là **đúng** sự cố 30/08, dựng lại nguyên vẹn, trong khi
`tests/test_demo_matches_main_gate.py` vẫn **9/9 XANH**.

Chữ `"worktree"` vẫn còn trong hàm (worktree vẫn được dựng, chỉ là không dùng
tới), nên vế `assert` thứ nhất cũng không cứu được.

Cách sửa là một ca **hành vi**, không phải một ca đọc chữ: cho `ref_paths` một
ref mà `services/api` khác cây đang đứng, rồi khẳng định nó trả về route của
**ref**. Ca đó bắt được mọi cách viết, vì nó đo cái hàm làm chứ không đo cách
hàm được gõ.

### Lỗ hổng 2 — `BO-KIEM-CONTENT-TYPE` lọt, và lọt về phía XANH GIẢ

`test_do_khac_ma_khi_may_chu_tra_html` gửi `<html>502</html>` + `text/html`. Gỡ
mệnh đề content-type thì `json.loads` vẫn ném, vẫn ra mã 2 — nên ca đó không
phân biệt được guard nào đã cắn.

Đầu vào phân biệt: **JSON OpenAPI hợp lệ, content-type nói dối**:

```
bản THẬT     -> 2   '   Cổng này đang nói chuyện với thứ không phải API.'
bản ĐỘT BIẾN -> 0   (khớp)
```

Không tương đương, và sai về phía nguy hiểm: mã **0** cho một thứ không phải API.

### Lỗ hổng 3 & 4 — **toàn bộ nửa `fetch` không có một ca nào**

```python
@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(gate, "fetch_ref", lambda ref: None)
```

`autouse=True` nên **mọi** ca trong file chạy với `fetch_ref` bị vô hiệu. Hệ quả:
gỡ hẳn lời gọi fetch (`BO-HAN-FETCH`), hoặc cho fetch thất bại mà vẫn so tiếp
(`FETCH-HONG-VAN-DI-TIEP`), đều **9 passed**.

Đây không phải lỗ hổng lý thuyết: mô tả PR gọi việc fetch là lý do tồn tại của
cổng ("so với một `origin/main` chưa fetch là đúng lỗi này lặp lại một tầng
trên"), và chặng 4 dưới đây cho thấy fetch **đổi phán quyết** từ mã 1 sang mã 0.
Tính chất được quảng cáo to nhất lại là tính chất không ca nào ghim.

---

## Chặng 3 — openapi.json hỏng phải ra mã 2

Chạy cổng như **tiến trình con** (không phải `gate.main()` trong tiến trình), vì
thứ cần đo là mã thoát mà cron/`make` thật sự nhận.

10 dạng hỏng: body không phải JSON · thiếu `paths` · `paths` là list · `paths`
null · `paths` rỗng · body rỗng · JSON cụt · HTML 502 · HTTP 404 · JSON
top-level là list.

**9/10 ra đúng mã 2, không traceback.** Ca còn lại:

```
JSON top-level là list  ->  mã 1  +  AttributeError: 'list' object has no attribute 'get'
```

`doc.get("paths")` ở dòng 228 giả định `json.loads` trả về dict. Trả về list thì
`AttributeError` không ai bắt, Python thoát **mã 1**.

Mã 1 là giá trị tệ nhất có thể ra ở đây: theo chính hợp đồng của cổng, **1 nghĩa
là "máy demo lệch so với main"**. Người đọc sẽ đi dựng lại máy demo để đuổi một
sai lệch chưa từng được đo. Đó đúng là việc gộp "không chạy được" vào "lệch" mà
`test_ba_ma_thoat_la_ba_gia_tri_khac_nhau` tồn tại để cấm.

**Phạm vi thiệt hại — nhỏ hơn tôi tưởng lúc đầu, và phải nói ra:**

```
exit code   : 1
stdout      : ''            <- rỗng, vì crash xảy ra TRƯỚC lúc in JSON
parse_report('') -> None
```

`demo_watch.py` đòi đọc được JSON trên stdout trước khi tin mã thoát; stdout rỗng
nên nó rơi vào nhánh `cannot(...)` và ghi **đúng** "không đối chiếu được" (mã 2).
Nên **lượt canh định kỳ không bị đánh lừa** — nhưng nó được cứu bởi một guard
thứ hai, không phải bởi mã thoát đúng. Người gọi trực tiếp (`make demo-check`,
một người, một cổng khác đọc `$?`) thì không có guard đó.

Sửa: `if not isinstance(doc, dict)` trước khi `.get`, trả `die(...)`.

---

## Chặng 4 — `--no-fetch` có thật sự không fetch không

Không đo bằng cách đọc code. Dựng một upstream **tôi kiểm soát**, để chữ "mới"
là thứ tôi tạo ra chứ không phải thứ tôi hy vọng đã xảy ra:

```
upstream v1 = /a /b        -> clone; origin/main trên đĩa ghim v1 (7a15790)
upstream v2 = /a /b /c     -> đẩy SAU khi clone
máy chủ stub phục vụ /a /b /c  -> khớp v2, KHÔNG khớp v1
```

Hai lượt chỉ khác nhau ở chỗ đọc `origin/main` nào. Một shim `git` trên `PATH`
ghi lại mọi lời gọi, nên "có fetch không" là **quan sát được**, không phải suy đoán.

| lượt | mã thoát | số lần gọi `git fetch` | `origin/main` sau lượt |
|---|---|---|---|
| A — có `--no-fetch` | **1** | **0** | 7a15790 (đứng yên) |
| B — mặc định | **0** | **1** | 7a15790 → **2fdbf82** |

- **A**: 0 lần fetch. Cổng so với bản cũ trên đĩa, thấy `/c` là THỪA → mã 1. Và
  nó tự khai: `(--no-fetch: so với origin/main đang có sẵn trên máy, có thể đã cũ.)`
- **B**: đúng 1 lần fetch, ref nhích v1→v2, cổng neo vào **main mới** → `Máy demo
  khớp origin/main: 3 route` mã 0.

Cả hai vế của câu 4 đều đúng như PR khai. Đây là tính chất **duy nhất** trong PR
mà tôi xác nhận bằng tay nhưng bộ test không ghim chút nào (lỗ hổng 3 & 4).

---

## Ngoài lề, nhưng cần hành động NGAY — máy demo 8099 lại đang lệch

Lúc dọn dẹp tôi thấy 8099 phục vụ 65 route trong khi `origin/main` khai 69. Chĩa
đúng cổng của PR này vào máy demo thật (chỉ đọc, không chạm gì):

```
$ python3 scripts/check_demo_matches_main.py --url http://127.0.0.1:8099 --ref origin/main --json
   origin/main khai 69 route, máy chủ phục vụ 65.
   THIẾU 4 route — leader bấm vào sẽ nhận 404:
      /contexts/{context_id}/albums
      /contexts/{context_id}/albums/{outing_id}
      /contexts/{context_id}/contextual-suggestion
      /contexts/{context_id}/preference-profile
exit 1
```

Đây là cùng một kiểu hỏng PR này sinh ra để bắt, tái diễn **sau khi PR đã merge**,
vì lượt canh định kỳ chưa được cắm (mô tả PR nói rõ: crontab đang rỗng, phải chạy
`demo_watch.py install --apply` sau merge — và việc đó chưa ai làm).

Hai điều đáng nói:

1. **Cổng hoạt động đúng như quảng cáo trên dữ liệu sống.** Đây là bằng chứng
   mạnh hơn mọi ca test trong báo cáo này: nó bắt một sai lệch thật mà không ai
   dựng sẵn cho nó.
2. **Hạn là 31/08.** Bốn route thiếu là tính năng album kỷ niệm và gợi ý theo
   ngữ cảnh. Leader mở 8099 để quyết định sản phẩm có chạy không sẽ nhận 404.
   Cần `git checkout --detach origin/main && make up` trên cây dựng demo, rồi
   cắm lượt canh định kỳ.

## Bốn việc cho PR tiếp theo (devops)

Xếp theo mức, không theo thứ tự dễ làm:

1. **Đổi canary hình-dạng-chữ thành ca hành vi.** `assert 'REPO_ROOT / "services"'
   not in src` chỉ bắt được một cách gõ; `.joinpath` cùng vi phạm đi lọt và dựng
   lại nguyên sự cố 30/08 với mã 0.
2. **`isinstance(doc, dict)` trước `.get("paths")`.** JSON top-level là list →
   mã 1 + traceback; mã 1 nghĩa là "lệch".
3. **Bỏ `autouse` khỏi `_no_network`**, thêm ca cho fetch: fetch bị gọi khi không
   có `--no-fetch`, không bị gọi khi có, và fetch hỏng → mã 2.
4. **Thêm ca content-type nói dối** (JSON hợp lệ + `text/plain`) — hiện gỡ guard
   đó ra thì cổng trả mã 0.

Việc 1 và 3 gác chính hai tính chất mà mô tả PR dựa vào nhiều nhất.

---

## Cái này KHÔNG chứng minh

- **Không đo máy demo 8099 thật.** Tôi cố ý không chạm nó: tag ảnh
  `mobile-local/api:dev` là toàn cục, `make up` từ worktree này sẽ ghi đè ảnh
  của chính máy demo. Mọi số trên đây đến từ container riêng cổng 8393.
- **Không đo `demo_watch.py` chạy dưới cron thật.** Tôi chỉ đo nhánh mã nó chọn
  khi cổng crash (`parse_report` → `cannot`), không đo lượt cron sống.
- Cổng so **đường dẫn**. Route có mà trả 500 vẫn ĐẠT. Không đổi so với PR khai.
- **Điểm đột biến 64% là sàn, không phải trần.** 12 đột biến là do tôi chọn tay;
  chúng không vắt kiệt không gian đột biến của file.
- Không chạy `make gate` / toàn bộ suite trong lượt này. Cây git của tôi **sạch**
  (`git status --porcelain` rỗng) — mọi đột biến chạy trên bản sao `/tmp`, nên
  không có gì để hồi quy. Ba file test liên quan: `43 passed in 10.57s`.

## Dọn dẹp

`docker rm -f qa3tt0033-old`, `docker rmi qa3tt0033/api:65319b5`,
`git worktree remove --force /tmp/qa3-demo-old`. Ảnh `mobile-local/api:dev`
không bị chạm (vẫn là bản dựng 2 giờ trước lúc tôi bắt đầu).
