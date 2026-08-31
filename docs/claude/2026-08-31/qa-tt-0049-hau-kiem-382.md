# PASS cho PR #382 tại `eb02968` (hậu kiểm)

Chip thứ 5 đã ra khỏi tablist thật. Đối chứng đỏ→xanh sạch, 4/4 đột biến bị giết,
và cả 4 route mà màn gọi đều có thật trên máy chủ với đường dẫn khớp từng ký tự.

- **protocol_version**: v1
- **verdict**: `PASS`
- **blocker còn mở**: không có
- **đo tại**: `eb02968` (head của #382)
- **sha này**: ĐÃ ở main — #382 squash-merge thành `2870ae9` lúc 2026-08-30T20:33:43Z,
  **trong lúc cổng của tôi đang chạy**. Nên đây là **hậu kiểm**, không phải cổng trước merge.
- **main lúc viết**: `2977280`

## Đo trên cái gì, và nó có ở main không

Cả 6 file #382 đụng tới đều **byte-identical** giữa `eb02968` và `origin/main`
(kiểm bằng `git rev-parse <ref>:<file>`, chạy lại sau khi main nhích lên `2977280`):

```
GIONG HET  apps/mobile/src/screens/ai-hieu-nhom/AiHieuNhom.tsx
GIONG HET  apps/mobile/src/screens/ai-hieu-nhom/ai-hieu-nhom.ts
GIONG HET  apps/mobile/src/screens/chat/TinNhan.tsx
GIONG HET  apps/mobile/tests/ai-hieu-nhom.test.mjs
GIONG HET  apps/mobile/tests/nhom-chat-web.test.mjs
GIONG HET  apps/mobile/tsconfig.test.json
```

Nên số đo ở `eb02968` **là** số đo của main. Mọi bản dựng dưới đây được dựng lại
từ chính cây đang đo — `tuoi-ban-dung.mjs` từ chối báo cáo khi nguồn mới hơn bundle.

## DA CHAY

| Chặng | Kết quả |
|---|---|
| `pytest services/api/tests tests` | **2664 passed, 574 skipped**, 4891 subtests (267s) |
| `npm test` (apps/mobile, `MOBILE_REQUIRE_WEB_A11Y=1`) | 920 ca — **919 pass, 1 fail** (fail là meta-gate, xem dưới) |
| `nhom-chat-web.test.mjs` chạy riêng | **9/9 pass, 0 skipped** |
| `make test-db` (Postgres thật, DB dùng-một-lần) | `tests/postgres` **517 passed** · `tests/qa` **89 passed** · **0 skipped** |
| `make gate ONLY="guard ruff contract client-routes server-routes screens cors migration pinned-import shared"` | **ĐẠT 9 · HỎNG 0 · BỎ QUA 1** |
| Đối chứng đỏ→xanh | 3 đỏ trước sửa → 9 xanh sau sửa |
| Đột biến trên cổng mới | **4/4 bị giết** |
| Thăm dò hộp nút ở 320 / 390 / 1280 | nằm trong màn cả ba, cao 44, không cắt chữ |

`ruff` là chặng **BỎ QUA** duy nhất, và nó tự khai lý do: *"nhánh không đổi file
Python nào so với origin/main"*. Đúng — #382 thuần client. Bỏ qua không phải đạt.

## KHONG CHAY — phần này quan trọng hơn phần trên

| Chặng / ô | Vì sao không chạy |
|---|---|
| `e2e` (lát cắt dọc `vertical-slice.test.mjs`) | Cần uvicorn + Postgres dựng sẵn ở 8000. Tôi không dựng vì máy đang có ~10 container Postgres của các lane khác và `make up` đụng bộ dùng chung. **Chưa ai đi lát cắt dọc trên bản này.** |
| `docker`, `demo-watch`, `guard-range` | Không chạy. `guard-range` cần base…head, vô nghĩa khi nhánh đã bằng main. |
| **4 route AI với máy chủ SỐNG + Gemini thật** | Tôi chứng minh được đường dẫn **tồn tại** và **khớp**, và cổng `client-routes` đồng ý. Tôi **không** chứng minh màn render được dữ liệu thật — chỉ `ai-hieu-nhom.test.mjs` với fetch giả phủ phần parse. |
| Màn `AiHieuNhom` ở 320 / 1280, chủ đề tối | Hai ca mới chỉ đo **390x844**. Tôi thăm dò riêng cái nút (sạch, xem dưới), nhưng **bản thân panel AI chưa được quét** ở khổ khác hay nền tối. |
| iOS / Android | Cổng chạy trên Chrome. Layout engine khác là code khác. |
| Mã QR quét bằng app ngân hàng thật | Không agent nào làm được. Vẫn là ô chưa quét, chờ leader. |

## Ca đỏ duy nhất KHÔNG phải lỗi sản phẩm

`stacked-branch.test.mjs` → *"nhánh này không mang lại file nào đã có nguyên vẹn
trên origin/main"*, liệt kê đúng 6/6 file. Nó đỏ vì #382 **được merge giữa lúc tôi
đang chạy** — sau squash, nhánh không còn gì mới so với main. Chính ca đó nói ra:

> *Khong phai loi: dung rebase, chi can sang origin/main va mo nhanh moi tu do.*

Đây là meta-gate hoạt động đúng, không phải hồi quy. Mọi ca sản phẩm đều xanh.

## Đối chứng: cổng mới có đỏ được ở bản cũ không

Tách đúng **một** biến. `8e625c7` là cha trực tiếp của `eb02968` và `TinNhan.tsx`
ở đó **giống hệt** `5703986` (bản tôi đã FAIL) — nên nó là bản "trước sửa" hợp lệ
mà không kéo theo khác biệt của lần merge main. Ghép **chỉ** file cổng mới từ
`eb02968` lên nó, rồi **dựng lại** (cổng đọc bundle, không đọc nguồn — sửa nguồn
mà không dựng lại là no-op):

```
TRUOC SUA (8e625c7 + cổng mới):   9 ca — 6 pass, 3 FAIL
  not ok 5 - hàng chip là tablist đúng chuẩn: đúng 4 tab, không lẫn nút khác
  not ok 6 - 'AI hiểu nhóm' là button và nằm NGOÀI tablist
  not ok 7 - bấm 'AI hiểu nhóm' vẫn mở được màn, và tablist vẫn đúng 4 tab
    role=tab · trong-tablist=true
    sau khi mở: tab = Chat · Plan · Thành viên · File · AI hiểu nhóm   <- 5 tab

SAU SUA (eb02968):                9 ca — 9 pass, 0 fail
    role=button · trong-tablist=false
    sau khi mở: tab = Chat · Plan · Thành viên · File                  <- 4 tab
```

Đỏ trước, xanh sau, cùng một file cổng, không sửa assert. Lỗi tôi báo ở
`5703986` là có thật và **đã được sửa thật**.

## Đột biến: cổng mới có răng không — 4/4 bị giết

Cổng này tự nhận là gác được "sửa cho xanh bằng cách xoá đường vào". Tôi kiểm
đúng lời nó nói. Mỗi đột biến **dựng lại bundle** rồi mới chạy; script từ chối
chạy tiếp nếu đột biến không ăn vào ký tự nào (chặn đột biến no-op đọc thành sống).

| # | Đột biến | Kết quả |
|---|---|---|
| M1 | Xoá hẳn `<Pressable>` đường vào | **GIẾT** — 2 đỏ (ca 6 chết ở `entry.found`, ca 7) |
| M2 | Trả chip về trong tablist (= chính bản `5703986`) | **GIẾT** — 3 đỏ |
| M3 | `onPress={() => {}}` — nút còn đó, bấm không mở | **GIẾT** — 1 đỏ (ca 7) |
| M4 | `accessibilityRole` `button`→`tab`, vẫn ngoài tablist | **GIẾT** — 1 đỏ (ca 6, đúng dòng role) |

M1 là cái đáng giá nhất: nó chứng minh cổng không thể bị làm xanh bằng cách xoá
đường vào — tức bốn route không thể lặng lẽ quay về trạng thái "không ai gọi",
đúng cái lỗ #382 sinh ra để bịt. M3 và M4 tách được hai khẳng định của ca 6 và
ca 7 ra, nên không có ca nào đỏ nhờ ăn ké ca kia.

Cây được khôi phục sạch sau mỗi lượt (`git status --porcelain` = 0).

## Bốn route: có thật, và khớp từng ký tự

`napAiHieuNhom` bắn song song 4 request. So với bảng route dựng từ chính
`app.api.main:app` (không phải đọc chuỗi trong nguồn):

| Client gọi | Máy chủ có |
|---|---|
| `/contexts/{id}/preference-profile` | `/contexts/{context_id}/preference-profile` |
| `/contexts/{id}/suggestion` | `/contexts/{context_id}/suggestion` |
| `/contexts/{id}/contextual-suggestion` | `/contexts/{context_id}/contextual-suggestion` |
| `/contexts/{id}/budget` | `/contexts/{context_id}/budget` |

4/4 khớp. Chặng `client-routes` (chạy toàn cây, có `--selftest`) độc lập đồng ý.
Chặng `screens` (`check_screens_reachable.py`, cũng có `--selftest`) đạt — tức màn
`AiHieuNhom` **có đường bấm tới**, không chỉ có tên trong nguồn.

Nhắc lại giới hạn: cái này chứng minh **đường dẫn tồn tại**, không chứng minh
**máy chủ trả dữ liệu dùng được**.

## Thăm dò ngoài phạm vi cổng: nút ở khổ hẹp

Hai ca mới chỉ đo 390x844. Nút là nhãn tiếng Việt dài nằm một hàng riêng, nên 320
mới là khổ nó tràn nếu nó định tràn — đúng khổ đã từng bắt được nút "Gửi" văng ra
ngoài mép. Tôi dựng lại bundle rồi đo hộp thật:

```
320x720 : role=button left=16 right=304  288x44  trong-man=CO cham-44=CO cat-chu=khong
390x844 : role=button left=16 right=374  358x44  trong-man=CO cham-44=CO cat-chu=khong
1280x800: role=button left=16 right=1264 1248x44 trong-man=CO cham-44=CO cat-chu=khong
```

Sạch cả ba. Đây là **lỗ hổng phạm vi của cổng, không phải lỗi đang sống** — tôi đo
tay lần này, lần sau không ai đo. Ghi thành gợi ý dưới, không phải blocker.

## Suggestion (không chặn)

1. Hai ca mới nên chạy vòng `VIEWPORTS` như ca 1 thay vì ghim 390x844. Hôm nay
   320 sạch; không có gì giữ cho nó sạch ở lần sửa style sau.
2. Panel `AiHieuNhom` (không phải cái nút) vẫn chưa được render-test ở khổ nào
   ngoài 390, và chưa ở nền tối.

Cả hai thuộc `apps/mobile/` — frontend hoặc backend tuỳ ai nhận, không phải việc tôi sửa.

## Trả lời câu hỏi của Lead về #321

**#321 đã CLOSED** lúc 2026-08-30T19:12:53Z, không cần ai đóng nữa. Lưu ý tiêu đề
thật của nó là *"Phán quyết QA: PASS cho #133 tại be574da…"* (rd-qa-24) — tức là
một PR phán quyết QA, không phải PR backend mang `votes.py`/`repository.py`/
`service.py` như mô tả trong ghi chú. Nếu cái Lead định đóng là PR backend kia
thì số hiệu đang lệch, cho tôi số đúng tôi kiểm lại.

## Vẫn đúng, bất kể bảng trên xanh cỡ nào

Repo này **chưa có bằng chứng hành vi nào** (ADR-0006, Giai đoạn 0 bị gác theo
quyết định của leader). Bảng trên nói code làm đúng điều tác giả nghĩ và màn có
đường bấm tới. Nó không nói người thật mở màn "AI hiểu nhóm" ra rồi hiểu được gì.
