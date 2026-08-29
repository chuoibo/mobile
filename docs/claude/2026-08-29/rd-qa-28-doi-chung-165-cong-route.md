# FAIL

**Lý do:** Cổng của #165 **hoạt động thật** — tôi làm nó đỏ được 4/4 lần ở 4 vị trí gọi
khác nhau, mỗi lần chỉ đúng file:line. Nhưng #165 đặt chặng tên `contract`, mà `main`
**đã có** một chặng tên `contract` khác hẳn (cổng header `X-Actor-ID` của #163). Merge
vào thì `scripts/gate.sh` có **hai `do_contract()`**, và **không cái nào nằm trong
conflict marker** — git ghép im lặng. Bash giữ định nghĩa **cuối**, nên cổng header
actor của #163 **chết**, trong khi `./scripts/gate.sh contract` vẫn in mô tả của #163
và báo `ĐẠT` exit 0. Cổng tự kiểm của repo (`test_gate_covers_every_workflow_job.py`)
vẫn xanh 5 passed / 9 subtests suốt quá trình. Đây là blocker loại **vi phạm spec/cổng**.

Gỡ chặn: đổi tên chặng của #165 (ví dụ `client-routes`) và map lại `COVERED_BY`. Phần
lõi không phải sửa gì.

---

## Đo tại

```
đo tại   399a7b0  (devops/cong-route-app-goi-co-that, head PR #165)
         f995873  (origin/main lúc đo)
sha này  399a7b0 là nhánh CHƯA merge; base của nó là 6c7d2ab, đứng SAU main 4 lần merge
         (#163 #168 #161 #170 #171 #167 #169 vào main sau khi nhánh này cắt ra)
```

`6c7d2ab` là trước `#163` — đó chính là lý do tác giả không thấy va chạm: lúc họ đặt
tên `contract`, trên nhánh của họ chưa có chặng nào tên đó.

## Phần ĐẠT — cổng này không phải đồ trang trí

Tôi không tin bảng đỏ-trước/xanh-sau trong mô tả PR, vì nó chỉ đột biến **một** chuỗi
(`/batches/current/publish` — chính chuỗi tác giả chọn). Một cổng chỉ bắt đúng chuỗi
tác giả đã thử là cổng trang trí. Nên tôi tự dựng ma trận đột biến ở **4 file client
khác nhau**, chạy trên **cả** nhánh PR **và** cây `main`:

| đột biến | file | kết quả |
|---|---|---|
| `/outing-stops/{id}/checkins` → `/outing-stop/...` | `src/api.ts:1275` | **ĐỎ** exit 1 |
| `/contexts/{id}/checkins` → `/contexts/{id}/checkin` | `screens/kham-pha/check-in.ts:69` | **ĐỎ** exit 1 |
| `/memberships/{id}/accept` → `.../approve` | `screens/vao-cua/cong-api.ts:187` | **ĐỎ** exit 1 |
| `/batches/{id}/publish` → `/batches/current/publish` | `src/api.ts:978` | **ĐỎ** exit 1 |
| `/polls` → `/poll` | `screens/chat/binh-chon.ts:5` | XANH exit 0 |

Ô cuối tôi đã **đọc nhầm là điểm mù** lúc đầu. Nó không phải: cả hai chỗ `/polls` đều
nằm trong **comment** (docstring của `binh-chon.ts` và `tin-nhan.ts`), và bỏ qua comment
là hành vi có chủ ý, có ca test ghim. Đột biến của tôi sai, không phải cổng mù. Ghi lại
đây vì đó đúng là cái bẫy mà `tests/test_api_contract.py` nói nó phòng.

Mỗi lần đỏ đều in đúng `file:line` + mã `[route_khong_ton_tai]`, không phải một dòng
"có gì đó sai".

Nền xanh, đo trên **cả hai** cây:

```
Máy chủ có 42 route. Đọc được 29 đường dẫn qua 35 lần gọi trong 8 file.
Client và máy chủ khớp hợp đồng.                                    exit 0
```

Số giống hệt nhau trên `399a7b0` và trên `f995873` — nghĩa là cổng này **không làm main
đỏ**, và nó đọc được đúng bề mặt của main chứ không chỉ của nhánh nó sinh ra.

Cổng khác, chạy trên nhánh PR trong cây sạch:

```
python3 -m pytest services/api/tests tests -q
  -> 1176 passed, 255 skipped, 4591 subtests passed in 57.83s
python3 -m pytest tests/test_api_contract.py -q      (12 ca của chính PR, chạy trên cây main)
  -> 12 passed
```

## Phần FAIL — va chạm tên chặng

`main@f995873` đã có:

```
scripts/gate.sh   STAGES=(guard ruff contract api migration shared mobile docker postgres)
                  contract) "every route wanting X-Actor-ID is called with it"
                  do_contract() -> check_actor_headers.py --selftest, rồi 61 lời gọi / 82 file
.github/workflows/test.yml   job `contract`  (dòng 122)
COVERED_BY        "contract": ("contract",)
```

`#165` thêm:

```
scripts/gate.sh   STAGES=(guard ruff api migration contract shared mobile docker postgres)
                  contract) "every route apps/mobile calls exists in the API"
                  do_contract() -> check_api_contract.py
COVERED_BY        "api": ("api", "migration", "contract")
```

Một cái tên, hai câu hỏi khác nhau, hai job đòi sở hữu.

### Vì sao nó im lặng

`git merge` báo xung đột ở **2 chỗ** (`STAGES=`, và `check_prereq`) — tác giả sẽ thấy và
sửa hai chỗ đó. Nhưng **hai thân hàm `do_contract()` được ghép tự động**, không marker:

```
$ grep -n '^do_contract()' scripts/gate.sh      # sau khi gỡ hết marker
154:do_contract() {      <- #163, header actor
184:do_contract() {      <- #165, route existence
$ grep -c '<<<<<<<\|>>>>>>>' scripts/gate.sh
0
$ bash -n scripts/gate.sh
(parse sạch)
```

Bash giữ định nghĩa **cuối cùng**. Chứng minh trực tiếp:

```
do_contract() { echo "ACTOR-HEADER (#163)"; }
do_contract() { echo "ROUTE-EXISTENCE (#165)"; }
do_contract
  -> ROUTE-EXISTENCE (#165)
```

Và `case` trong `stage_help` khớp **cái đầu**, nên phần mô tả in ra vẫn là của #163.

### Hậu quả đo được

Trên `main` sạch:

```
$ ./scripts/gate.sh contract
--- self-test: the checker has to be able to be red
  ĐẠT    canary xấu: có vi phạm (mong đợi có)
  ĐẠT    canary sạch: không có vi phạm (mong đợi không có)
Cổng header actor — 82 file client, 61 lời gọi tới route đòi X-Actor-ID.
ĐẠT — 61 lời gọi đều gửi X-Actor-ID.
```

Trên cây đã merge #165 (giải xung đột bằng cách giữ phía `HEAD` — cách một reviewer tin
rằng chặng của main là cái cần giữ sẽ làm):

```
$ ./scripts/gate.sh contract
=== contract === every route wanting X-Actor-ID is called with it (test.yml: contract)
Máy chủ có 42 route. Đọc được 29 đường dẫn qua 35 lần gọi trong 8 file.
Client và máy chủ khớp hợp đồng.
ĐẠT     contract (2s)
EXIT=0
```

Cổng **nói** nó kiểm `X-Actor-ID`. Nó **chạy** kiểm route existence. Nó báo `ĐẠT`. Hai
canary của #163 không chạy. 61 lời gọi không ai đếm.

Và cổng-canh-cổng của repo không kêu:

```
$ python3 -m pytest tests/test_gate_covers_every_workflow_job.py -q
5 passed, 9 subtests passed
```

Đây đúng là kiểu hỏng mà #163 sinh ra để chặn: `bug-191433` (ô tìm kiếm Khám phá thiếu
`X-Actor-ID`) đã tốn hai tiếng, và `rd-qa-25` đo được nó chết **100%** trên main. Merge
#165 nguyên trạng là tháo cái cổng đó ra mà không ai thấy dấu đỏ nào.

## Tái lập

```bash
bash tests/qa/rd-qa-28/va-cham-ten-chang-contract.sh
```

Exit 0 = va chạm tái lập được. Exit 1 = PR đã rebase/đổi tên, đo lại. Script tự dựng
worktree tạm, tự dọn, không đụng cây đang làm việc.

## Tiêu chí gỡ chặn

Đổi tên chặng của #165 sang tên không trùng — `client-routes` là gợi ý (`routes` dễ lẫn
với `scripts/check_server_routes.py` của #170 đã ở main) — rồi:

1. `STAGES=` giữ **cả hai** tên,
2. `stage_help` và `check_prereq` có mục riêng cho tên mới,
3. `COVERED_BY` giữ `"contract": ("contract",)` và thêm tên mới vào `"api"`,
4. rebase lên `origin/main` để hai chỗ xung đột kia biến mất.

Sau đó tôi chạy lại ma trận đột biến + `gate.sh` cho cả hai chặng và đổi phán quyết.

## Ô CHƯA quét

- **Chưa** chạy `cd apps/mobile && npm test` trên nhánh này (`apps/mobile/node_modules`
  chưa cài trong worktree đo; `tests/test_phone_path.py` skip vì đúng lý do đó). Cổng
  `mobile` của #165 không đổi gì nên rủi ro thấp, nhưng tôi không đo nên không nói nó xanh.
- **Chưa** chạy tầng `tests/postgres` với `MOBILE_REQUIRE_POSTGRES_TESTS=1` — 255 skipped
  ở trên **không phải** xanh. #165 không chạm persistence.
- **Chưa** kiểm method/body/query/quyền: cổng này chỉ so **đường dẫn**. Một path có thật
  cho `GET` mà client gọi bằng `POST` vẫn ĐẠT. Tác giả đã nói rõ điều này trong PR.
- **Chưa** kiểm đường dẫn ghép từ biến ở nhiều tầng — tôi chỉ xác nhận cổng đọc được 29
  đường dẫn / 35 lời gọi, **không** chứng minh được đó là *toàn bộ* lời gọi trong app.
- **Chưa** quét giao diện: PR này không đụng UI.
