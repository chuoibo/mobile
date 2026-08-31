# Còn ô nào nữa không: quét hình dạng "trạng thái rỗng bị đối xử như không cần xét"

- lượt: `qa2-080313`
- nhánh: `qa2/kiem-muoi-cong-can-duoc-khong`
- main lúc đo: `2f8a301`, HEAD lúc đo: `5c3f418`
- protocol_version: v1
- verdict: **FYI — danh sách, không sửa gì** (leader yêu cầu thấy danh sách trước rồi xếp lịch)
- skill dùng: `ai-qa-review` (batch audit một smell duy nhất trên toàn bộ suite cổng)

## Câu hỏi

Ba lần trong một đêm, ba người khác nhau viết ra cùng một hình dạng:

| PR | giá trị trung tính | bị đọc thành |
|---|---|---|
| #359 | tập persona RỖNG | SẠCH |
| #430 | danh sách wrapper RỖNG | KHÔNG MẤT GÌ |
| #439 | cây `clean` | KHÔNG CÓ GÌ ĐỂ SO |

Việc: còn ô nào nữa không. Và nếu ra 0 thì phải là **0 đo được**, không phải 0 vì
không ai tìm.

## Cách đo, và tại sao con số dưới đây đọc được

Hai file, đều nằm trong PR này:

- `tests/qa/qa2-080313-o-rong/quet_o_rong.py` — quét AST 6 hình dạng (V1..V6),
  **kể cả Python nhúng trong heredoc của shell**. Bỏ chặng đó là bỏ mất chính
  #439, vì nó nằm trong `python3 - <<'PY'` bên trong `hero_walk.sh`.
- `tests/qa/qa2-080313-o-rong/do_o_rong.py` — **đo** từng ứng viên: làm rỗng bảng
  rồi gọi lại đúng entry point thật, xem cổng ĐỎ hơn hay XANH hơn.

### Đối chứng dương — điều kiện để tin con số

Máy quét phải bắt lại được cả ba ca đã biết, và phải **im** ở bản sau khi vá.
Đo trên commit thật:

```
ca                          TRƯỚC vá   SAU vá
#430 WRAPPERS               1 hit      0 hit     (d416de3^ → d416de3)
#359 people                 1 hit      0 hit     (dd5e8a3^ → dd5e8a3)
#439 tree == "clean"        1 hit      n/a       (chưa vá, trên cây hiện tại)
```

Hai lần đầu là canary hai chiều: máy quét đổi câu trả lời đúng ở chỗ bản vá chạm
vào. Nếu nó chỉ biết kêu mà không biết im, con số 0 ở dưới sẽ vô nghĩa.

Selftest của chính máy quét: 12/12 ĐẠT, gồm **4 ca âm** — `if rc != 0: raise` và
`if x.bad: raise` phải im, vì đó là phép kiểm chứ không phải vỏ bọc. Không có mấy
ca âm đó thì máy quét kêu ở mọi `if` trong repo, và "kêu ở mọi chỗ" cũng là một
cách không tìm thấy gì.

### Phễu

```
234 file đọc, 213 khối phân tích được, 0 khối không parse được
  185 ứng viên thô
→ 111 nằm trong cổng SỐNG (74 còn lại là probe một-lần dưới tests/qa/)
→  69 bảng neo cấp module, 59 không có sàn
→ phân loại theo HƯỚNG: rỗng làm cổng IM hơn hay ỒN hơn
→   4 chỗ đem đi đo thật
```

**Hướng là chỗ phân định.** Quá nửa bảng bị máy quét nêu tên là *danh sách miễn
trừ* — `EXEMPT_ROUTES`, `DIRECT_FETCH`, `SAFELISTED_*`. Làm rỗng chúng thì cổng
**chặt hơn**, ồn hơn, không giấu gì. Chỉ hướng IM mới giấu được lỗi. Một báo cáo
liệt kê cả 59 bảng "không có sàn" sẽ đúng về hình dạng và vô dụng về hành động.

## Bảng kết quả

| chỗ | giá trị trung tính | có phải trạng thái hợp lệ cần kiểm? | kết luận |
|---|---|---|---|
| `scripts/check_pin_drift.py` :: `IMPORT_CRITICAL` | tập rỗng | **Có** — rỗng là lỗi cấu hình, không phải "không pin nào quan trọng" | **MÙ, đo được**. Cùng một cây lệch pin: bảng đầy → `exit 1`; bảng rỗng → `exit 0` |
| `scripts/repo_guard.py` :: `SECRET_RULES` | tập rỗng | **Có** — rỗng nghĩa là "không có gì là bí mật" | **MÙ, đo được**. `ALLOWLISTABLE_RULES = CONTENT_RULES - SECRET_RULES`: rỗng thì `google-api-key` từ *không allowlist được* thành *allowlist được* |
| `scripts/check_api_contract.py` :: `REQUEST_FUNCTIONS` | dict rỗng | **Có** — đây là bảng neo mà `WRAPPERS` của #430 suy ra từ đó | **Chặn BẰNG TAI NẠN**. Rỗng → `KeyError: 'fetch'` ở `canary_through` (dòng ~1054). Đúng cấu trúc mà commit của #430 gọi là không đủ — chỉ là `IndexError` đổi thành `KeyError`, một tầng neo lên trên, chưa vá |
| `scripts/dot_bien_cong_drift_hanh_vi.py` :: `ROWS` | list rỗng | **Có** — 0 đột biến không phải "gác kín" | **MÙ (đọc, chưa đo)**. `verdicts` rỗng → in `ALL ROWS AS EXPECTED -- no evasion shape tried here got through` và `return 0`. Câu đó đúng nguyên văn và sai hoàn toàn về nghĩa |
| `scripts/dot_bien_demo_watch.py` :: `MUTATIONS` | list rỗng | **Có** — như trên | **MÙ (đọc, chưa đo)**. `rows=[]`, `failures=0` → in `0 hàng đúng kỳ vọng.` → `return 0`. Cùng câu chữ với #359 (`SẠCH — cả 0 persona`) |
| `scripts/dot_bien_demo_matches_main.py` :: `MUTATIONS` | list rỗng | **Có** | **MÙ (đọc, chưa đo)** — cùng hình dạng |
| `scripts/dot_bien_dia_diem_ban_do.py` :: `ROWS` | list rỗng | **Có** | **MÙ (đọc, chưa đo)** — cùng hình dạng |
| `scripts/mutation_cong_cua_so_model.py` :: `MUTATIONS` | list rỗng | **Có** | **MÙ (đọc, chưa đo)** — cùng hình dạng |
| `scripts/hero_walk.sh:340` :: `tree == "clean"` | `"clean"` | **Có** | **#439, đã báo, chưa vá** — nhắc lại vì máy quét độc lập tìm lại được nó |
| `scripts/repo_guard.py` :: `FORBIDDEN_SEQUENCES` | tập rỗng | Có, nhưng | **KHÔNG mù, đo được**. `FORBIDDEN_COMPONENTS` bắt độc lập; làm rỗng bảng này không đổi phán quyết trên 4 đường dẫn mẫu |
| `scripts/check_cors_contract.py` :: `CANARIES` | list rỗng | Có | **KHÔNG mù — có sàn ở file khác**: `test_cors_contract_gate.py:144` `assertGreaterEqual(len(mod.CANARIES), 8)`. Bản thân `selftest()` vẫn in `ĐẠT: 0 canary` nếu rỗng, nhưng hệ thống bắt được |
| `scripts/check_actor_headers.py` :: `_scan_roots()` | list rỗng | Không | **KHÔNG mù** — có hai sàn hạ nguồn: `if not files: die(...)` và `if call_sites == 0: die(...)` |
| `scripts/check_screens_reachable.py` :: `bound_names()` | list rỗng | Không | **KHÔNG mù** — mệnh đề import không ràng buộc tên nào là trạng thái hợp lệ thật |
| `tests/test_phone_path.py:131` :: `all(...)` trên `choice.rejected` | rỗng | Không | **KHÔNG mù** — dòng ngay trên là `assertEqual(2, len(choice.rejected))`, mẫu số đặt đúng chỗ |
| `scripts/qc/probe_duong_tien_bill.py:174,199` :: `all(...)` | alloc rỗng | Không | **KHÔNG mù** — `sum(alloc.values()) == odd_total` ngay bên cạnh đỏ trước, vì tổng khác 0 |

## Ba điều đáng nói riêng

**1. `repo_guard :: SECRET_RULES` là chỗ đắt nhất.** Cổng này là thứ chặn khoá
API và ảnh bill vào Git. Hình dạng ở đây không phải vòng lặp rỗng mà là **phép
trừ tập hợp**: `CONTENT_RULES - SECRET_RULES`. Bảng rỗng không làm cổng im — nó
làm cái *không được phép miễn trừ* trở thành *miễn trừ được*. Cùng một hình dạng,
mặc một bộ quần áo mà cả ba ca trước không mặc.

**2. Bộ máy đột biến tự chấm điểm bằng chính bảng của nó.** 5/9 chỗ mù là harness
đột biến — đúng những công cụ đội này dùng để *chứng minh cổng cắn được*. Bảng
rỗng thì chúng in "mọi hàng đúng kỳ vọng" trên không hàng nào. Đây là tầng
meta: cái đo độ tin của cổng lại tự mù theo đúng kiểu mà nó sinh ra để bắt.

**3. #430 vá đúng biến, nhưng bảng neo ở tầng trên vẫn chỉ được chặn bằng tai
nạn.** `WRAPPERS` giờ có sàn. `REQUEST_FUNCTIONS` — cái mà `WRAPPERS` suy ra từ
đó — thì không, và thứ đang chặn nó là `KeyError: 'fetch'` do một canary tình cờ
tra khoá. Commit của #430 đã tự viết ra rằng bảo vệ-bằng-tai-nạn là sai chỗ và
sai mã thoát. Nhận xét đó vẫn đúng, chỉ là áp cho biến bên cạnh.

## Cái phép đo này KHÔNG chứng minh

- 5 hàng "MÙ (đọc, chưa đo)" là **đọc mã**, không phải chạy. Chúng chạy subprocess
  và bộ test thật; đo cho tử tế cần một lượt riêng. Đừng đọc chúng ngang hàng với
  ba hàng có số liệu.
- Máy quét chỉ đọc **Python** (và Python nhúng trong `.sh`). 94 file `.mjs/.js`
  dưới `tests/` **chưa quét**. Không nói được gì về chúng.
- Sàn ở *hạ nguồn, trong hàm khác* thì máy quét không thấy (đó là vì sao
  `check_actor_headers` bị nêu rồi bị tôi loại bằng tay). Nên 111 con số kia là
  **ứng viên**, không phải lỗi; phần lọc là người làm.
- Không chứng minh 59 bảng "không có sàn" còn lại là an toàn. Tôi phân loại chúng
  theo hướng và chỉ đem đi đo những cái hướng IM. Cái nào tôi xếp là "ồn hơn" mà
  xếp sai thì nó lọt.

## Tái lập

```bash
python3 tests/qa/qa2-080313-o-rong/quet_o_rong.py --selftest      # 12/12 ĐẠT
python3 tests/qa/qa2-080313-o-rong/quet_o_rong.py --only hero_walk.sh
python3 tests/qa/qa2-080313-o-rong/do_o_rong.py                   # 4 chỗ, 3 MÙ

# đối chứng dương trên commit trước bản vá
git show dd5e8a3^:scripts/cong_persona_demo_sach.py > /tmp/p/scripts/cong_persona_demo_sach.py
python3 tests/qa/qa2-080313-o-rong/quet_o_rong.py --root /tmp/p
```
