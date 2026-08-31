# Đếm TỬ SỐ của "41/47" — đo tại `2a8362d`

- **task_id**: `qa-114244` / `12012801` (tách đôi: repo guard đọc chuỗi liền thành số 14 chữ số)
- **đo tại**: `2a8362d52396f27b98c4f323af7c5f65e39e7ca5`
- **sha này**: ĐÃ ở `origin/main` (`git merge-base --is-ancestor origin/main HEAD` → đúng, nhánh cắt thẳng từ main)
- **verdict**: xem dòng đầu báo cáo gửi Lead

## Kết quả, trước phần chi tiết

| con số | giá trị | trạng thái |
|---|---|---|
| MẪU SỐ | **47** | **ĐO ĐƯỢC.** Spec tự khai `F01`…`F47`, liên tục, không trùng, không hụt |
| TỬ SỐ, chỉ máy đo | **18/47** | sàn dưới nghiêm ngặt của một phép đi bộ bằng chuột |
| TỬ SỐ, sau đối chứng dương | **26/47** | sàn dưới sau khi đường hero được chứng minh đi được |
| "41" | — | **không tái lập được.** Không phép đo nào ra 41 |

Cả hai con số tử số là **SÀN DƯỚI**, không phải đáp án. Lý do ở mục "Vì sao 18
không phải đáp án".

## Đơn vị đếm, và vì sao chọn nó

Ba đơn vị đã hỏng ở repo này: đếm theo **tên hàm**, đếm **số lần nhắc tên màn**,
và **danh sách viết tay**. Cả ba đều là thứ người viết code sửa được để làm đẹp
con số.

Đơn vị dùng ở đây là **một request quan sát được trong trình duyệt, sau một chuỗi
bấm thật bắt đầu từ lúc mở app**. Không ai đổi tên để đi vào đó được.

Ba chân, ba nguồn độc lập:

| chân | đo bằng | ai đổi được |
|---|---|---|
| **có API** | `/openapi.json` của uvicorn thật dựng từ `2a8362d` | phải đăng ký route thật |
| **màn gọi route** | `window.__snapshotApiLog` đọc từ trang sống | phải gọi fetch thật |
| **bấm tới được** | BFS bấm chuột thật, từ màn mở app | phải có nút dẫn tới |

Mẫu số dùng đầu đề `F<nn>` trong `product/feature_list.md`. File đó **sửa đúng
một lần trong cả lịch sử repo** (`2a82b1a`, commit đưa tài liệu sản phẩm lên) và
chưa lane nào chạm vào từ đó. Không phải một lựa chọn cách đếm.

## Số đo thô

```
uvicorn app.api.main:app --port 8211      (cây 2a8362d)
GET /openapi.json  -> 77 path, 89 (method × path)

BFS bấm — khách ("Bỏ qua"):      38 view,  241s,   1 đường API
BFS bấm — đăng nhập (Minh):     112 view,  691s,  21 đường API
                                          1242 nút CHƯA thử (hết ngân sách)
đối chứng dương (hero walk):     12 màn ghi ra file, exit 0, VietQR thật
```

### Bảng 47 ô

`A` = có API + có màn + bấm tới được · `B` = có API + client có gọi, chưa bấm tới
· `C` = có API, client không gọi · `E` = không có route nào

```
F01 A  Account Registration          F25 B* Expense From Receipt
F02 A  Personal Profile              F26 C  Expense From Screenshot
F03 B  Add Friends                   F27 B* Smart Settlement
F04 A  Friend Request                F28 B* Settlement Tracking
F05 E  QR Friend Add                 F29 B* Payment Link / QR
F06 A  Create Group                  F30 A  Group Memory
F07 A  Group Chat                    F31 A  Group Preference Profile
F08 A  AI Member                     F32 A  Proactive Suggestion
F09 A  Discover Places               F33 A  Contextual Suggestions
F10 C  Place Detail                  F34 A  Budget Awareness
F11 A  AI Place Match                F35 A  Group Memory Wall
F12 C  NL Place Search               F36 A  Automatic Trip Album
F13 A  Create Outing                 F37 B  AI Highlight Reel
F14 B  Invite Members                F38 A  Locket Style Widget
F15 B  Outing Timeline               F39 A  Post
F16 E  AI Itinerary Generator        F40 B  Reactions
F17 B  Voting                        F41 B  Comments
F18 B* Receipt OCR                   F42 B  Privacy
F19 B* Bill Item Detection           F43 B  Social Map
F20 B* Assign Food To Person         F44 C  Group Heatmap
F21 B  AI Person Recognition         F45 C  Meet-in-the-middle
F22 E  Visual Food Participation     F46 B  Group Check-in
F23 B* Confidence Score              F47 C  Automatic Place Detection
F24 B  Expense From Chat

A=18   B=18 (trong đó 8 ô B*)   C=8   E=3
```

`B*` = tám ô mà **đối chứng dương chứng minh là A**, xem dưới. 18 + 8 = **26**.

## Đối chứng đường — phần quan trọng nhất

Luật: chọn trước một tính năng **biết chắc ở A** và một **biết chắc ở E**. Phép
đếm xếp sai một trong hai thì phép đếm hỏng, không được báo số.

**Ô E — F05 QR Friend Add.** Phép đếm xếp E. Đúng. Không route nào trên máy chủ.

**Ô A — chia bill.** Phép đếm xếp **B**. **SAI.** Và đó là lý do con số 18 không
phải đáp án.

Đối chứng chạy thật:

```
node tools/screen-snapshots.mjs --build-dir /tmp/qa-tuso-web --out /tmp/qa-hero
exit 0 — 12 màn ghi ra file, mỗi màn > 5 KB:
  mo-dau 32659 · chup-bill 19341 · ket-qua-quet-anh 15722 · ket-qua 24329
  goi-y 34928 · goi-y-dong 30378 · nhap 22954 · de-xuat 18274
  dot-thu 18744 · ket-qua-thanh-toan 84613 · chia-se 18221
```

Đây là một lượt đi bộ **bằng bấm chuột thật và một tấm ảnh thật**, từ màn mở app
tới mã VietQR vẽ ra được. Nên chụp bill → đọc món → gán món → chia → VietQR
**là ô A**, và BFS của tôi đã xếp nhầm cả tám ô đó.

## Vì sao 18 không phải đáp án — và lỗi này tự khai ra

BFS dừng khi hết ngân sách với **1242 nút chưa bấm**. Một tính năng không xuất
hiện trong tử số vì một trong hai lý do, và **phép đo không phân biệt được**:

1. thật sự không có đường bấm tới → đúng là B
2. có đường, nhưng BFS chưa đi tới → xếp nhầm thành B

Đối chứng dương chứng minh lý do 2 **có xảy ra thật**, tám lần. Nên:

> **Chỉ kết quả DƯƠNG của phép đo này đáng tin. Kết quả ÂM không đáng tin.**
> 26/47 là sàn dưới. Con số thật ≥ 26 và ≤ 44 (47 trừ 3 ô E).

Hai lỗi đã bắt được trong lúc dựng phép đo, ghi lại vì cả hai đều **xanh im lặng**:

- **`page.on("request")` đọc ra 0.** Stub thay hẳn `window.fetch`, không gì chạm
  tầng mạng. Lần chạy đầu: 8 view, **0 đường API** — trông y hệt một app không
  gọi gì.
- **Chữ ký view trùng làm mất cả nhánh đăng nhập.** Sau `Bỏ qua`, màn Khám phá vẽ
  panel "máy chủ chưa có danh mục địa điểm"; sau `Vào app với tư cách Minh` nó vẽ
  **đúng panel đó**. Một chữ ký → BFS gộp hai nhánh và không mở nổi một màn nào
  sau khi đăng nhập: **38 view, 1 đường API, và không dấu hiệu nào báo là đã bỏ
  sót**. Tách thành hai lượt chạy: 38 → **112 view**, 1 → **21 đường API**.

## Ô CHƯA quét

- 1242 nút chưa bấm. B và B* có thể còn ô A nằm trong đó.
- BFS **không gõ chữ được**. Đăng nhập bằng số điện thoại, tìm địa điểm bằng lời,
  soạn tin — mọi đường sau một ô nhập đều nằm ngoài tầm.
- Đi bộ chạy trên **stub**, không phải máy chủ thật. Chứng minh client *hỏi* route
  đó; không chứng minh máy chủ *trả lời đúng*.
- Ánh xạ `F<nn>` → route là **phán đoán của tôi**, ghi ở
  `apps/mobile/tests/qa-114244/anh-xa-f-route.json` để cãi được từng dòng.
- Không đo chất lượng màn: đẹp, đọc được, hiểu được — không ô nào ở đây trả lời.
- Mã VietQR **chưa ai quét bằng app ngân hàng thật**. Vẫn nguyên trong ô chưa quét.

## Chạy lại

```bash
cd services/api && uvicorn app.api.main:app --port 8211            # rồi GET /openapi.json
cd apps/mobile && EXPO_PUBLIC_API_URL=http://api.build-check.invalid \
  npx expo export --platform web --output-dir /tmp/qa-tuso-web --clear
node tests/qa-114244/di-bo-toan-app.mjs --workers 6 --depth 7 \
  --prefix 'chu:GĐăng ký với Google|nhan:Vào app với tư cách Minh' --out /tmp/w.json
node tools/screen-snapshots.mjs --build-dir /tmp/qa-tuso-web --out /tmp/qa-hero   # đối chứng dương
```
