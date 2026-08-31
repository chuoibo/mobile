# Hai chỗ `?? id` ở màn Đề Xuất: đọc trên MÀN, không đọc mã nguồn — 0 trên đường demo, nhưng hai lý do khác hẳn nhau

- task_id: `qa2-111127`
- protocol_version: v1
- Đo trên `main` = `ec0c0fb`, Chrome thật (Google Chrome for Testing 151), 390x844
  (số hiệu bản dựng đầy đủ bị lược: repo guard đọc dãy số dài liền nhau như số tài khoản)
- verdict: **CONFIRMED** cho lời khai của frontend ("mới là khớp hình dạng, chưa
  phải rõ đã xác nhận") — hình dạng có thật, triệu chứng **không** xuất hiện trên
  đường demo
- Blocker còn mở: không. Đây là phép đo, bản vá đang nằm ở nhánh của frontend.

## Câu hỏi được giao

Frontend quét AST toàn cây và tìm ra 3 chỗ còn lấy id thô làm mặc định, **hai
trong đó ở `DeXuat.tsx`** — màn chốt tiền vào sổ:

```
advancerName = people.find(p => p.id === proposal.advancerId)?.name ?? proposal.advancerId
gainerNames  = proposal.roundingGainers.map(id => people.find(...)?.name ?? id)
```

Họ khai rõ đó mới là **khớp hình dạng**. Lead giao tôi đo độc lập: mở Chrome
thật, đi tới màn Đề Xuất, **nhìn màn hình** xem có chuỗi 36 ký tự nào hiện ra
không.

## Trả lời ngắn

| | Trên đường demo | Nhánh có sống không |
|---|---|---|
| `gainerNames` | **không hiện** — vì cả thẻ chứa nó không render | **SỐNG**. Bơm một id lạ từ phía máy chủ → UUID hiện nguyên trên màn |
| `advancerName` | **không hiện** | Có một cửa duy nhất vào, và cửa đó **đang đóng** ở client |

Một số 0 không có đối chứng dương thì không phân biệt được với một máy quét
hỏng, nên phép đo này chạy hai đối chứng dương trong **cùng trình duyệt, cùng
máy đọc chữ**.

## Cách đo

`apps/mobile/tests/qa2-111127-hai-cho-de-xuat/probe-in-id-tren-man.mjs`. Không
đọc file nguồn dòng nào; nó lái bản `expo export` thật trong Chrome thật qua
đúng các cú bấm của đường demo (đăng nhập → Khám phá → Tạo khoản chi → chọn ảnh
bill → AI đọc món → gán món → Khoản chi mới → Chia tiền), rồi đọc
`document.body.innerText` của màn đã render.

Máy đọc quét hai thước: dạng UUID v4, **và** bất kỳ dãy 36 ký tự liền không có
khoảng trắng (rộng hơn UUID có chủ ý — câu hỏi được giao là "chuỗi 36 ký tự",
nên một id đổi dạng không được phép đổi thành vô hình).

Hai cái nó **không** gộp làm một: chữ trên kính và `aria-label`. Cái thứ hai
được in riêng, vì trình đọc màn hình đọc được thứ `innerText` không mang.

## A · Đường demo thật — SẠCH

```
SẠCH  A · DeXuat, roster đủ: uuid=0 chuoi36=0 (279 ký tự trên màn)
      aria-label mang uuid: 0
      thẻ "chia không hết chẵn" có mặt: false
```

Toàn bộ chữ trên màn:

```
Chia bữa lẩu tối thứ bảy
Minh đã trả trước 480.000đ.
Minh (trả trước)  160.000đ
Trang             160.000đ
Hải               160.000đ
Tổng              480.000đ
2 người sẽ cần gửi tiền cho Minh. Chưa ai bị nhắn gì cho tới khi bạn phát đợt thu.
```

Đọc kỹ dòng cuối của khối đo: **thẻ "Chia không hết chẵn" không hề render**.
480.000 chia hết cho 3, nên `rounding_gainers` rỗng, nên `gainerNames` là mảng
rỗng và cả `Card` chứa nó bị bỏ. Nghĩa là đường demo **không đi qua** nhánh thứ
nhất chút nào — đây không phải "nhánh đó an toàn", đây là "chưa ai đi tới đó".

## B · Đối chứng dương 1 — máy chủ gọi tên người mà bill không biết

Một shim `fetch` đặt **ngoài app**, đăng ký sau `installBeforeApp`, viết lại
`rounding_gainers` trong trả lời `POST /expenses` thành một id không có trong
roster. Không vá dòng nào của sản phẩm; đây là lời nói dối của **máy chủ**.

```
số lần cắt ngang /expenses: 2
CÓ ID  B · DeXuat, gainer lạ: uuid=1 chuoi36=1 (378 ký tự trên màn)
       uuid: 0f9c8b7a-1d2e-4f30-9a41-5b6c7d8e9f01
```

Và nó hiện ra đúng ở câu giải thích đồng lẻ, trên màn chốt tiền:

```
Chia không hết chẵn. 0f9c8b7a-1d2e-4f30-9a41-5b6c7d8e9f01 chịu thêm 1đ lẻ,
vì theo thứ tự cố định.
```

**Điều kiện hiện ra**: máy chủ đặt tên một id không có trong roster mà client đã
chụp lại. Hai danh sách này **khác nguồn** — `participants` là người dùng gõ trên
máy (`draft.participants`), `roundingGainers` là `result.allocation.rounding_gainers`
máy chủ trả về (`api.ts:653,683`). Chúng trùng nhau hôm nay vì client gửi đúng
danh sách đó đi và allocator chỉ chia trong đám đã gửi — **một bất biến nằm ở
phía bên kia dây**. Client không có lớp phòng nào của riêng nó.

## D · Vì sao A ra 0 ở chỗ thứ hai — cánh cửa

Trên màn "Khoản chi mới": chọn Minh làm người ứng tiền, rồi bấm "Bỏ" đúng Minh.

```
sau khi chọn Minh làm người ứng tiền: Chia tiền disabled=false
bấm được "Bỏ": true
sau khi bỏ Minh:                      Chia tiền disabled=true
radio còn lại: [{"ten":"Trang","chon":"false"},{"ten":"Hải","chon":"false"}]
```

Ba mắt xích, tất cả ở client: `removeParticipant` đặt `advancerId = null` khi
người bị bỏ chính là người ứng tiền (`participants.ts:123`); `advancer(roster)`
trả `null` nếu id không tìm thấy **trong danh sách** (`:146`); `ready` đòi
`advancer(roster) !== null` (`NhapKhoanChi.tsx:84-85`) và nút mang `disabled`.

Đó là **một lớp**. Và `App.tsx:97` là nơi duy nhất trong cả cây import màn
`DeXuat`, nên chỉ có một cửa để canh.

## C · Đối chứng dương 2 — nếu cửa đó mở thì màn trông thế nào

Dựng chính `DeXuat` (bản biên dịch thật, qua react-native-web, có CSS) với
`advancerId` ngoài roster, mở trong cùng Chrome:

```
CÓ ID  C · DeXuat, advancer ngoài roster: uuid=2 chuoi36=3 (369 ký tự)
```
```
0f9c8b7a-1d2e-4f30-9a41-5b6c7d8e9f01 đã trả trước 300.001đ.
...
2 người sẽ cần gửi tiền cho 0f9c8b7a-1d2e-4f30-9a41-5b6c7d8e9f01.
```

Hai chỗ trên một màn, và chỗ thứ ba ("Đã ghi tài khoản nhận của …") chỉ vắng vì
props không có `taiKhoanNhan`.

## Chỗ đáng lo hơn cả hai con số: trạng thái đó ĐÃ TỒN TẠI ở nơi khác

"Người trả trước không nằm trong danh sách chia" không phải trạng thái bịa để
làm đối chứng. Nó **hợp lệ theo hợp đồng tiền**:

- `allocator.py:293` — `advancer_not_participant` là **warning**, không phải lỗi.
  Có golden vector cho nó: `01_even_split.json`, và G23/G24 trong
  `06_composition_va_canh_bien.json`.
- `nhap-tu-chat.ts:136-161` (`banNhapDeGhi`) **cố ý** không nhét người trả vào
  danh sách chia, và comment nói rõ vì sao: nhét vào là "app quyết một câu hỏi
  tiền bằng linh cảm", nó dịch tiền khỏi dòng của mọi người khác.

Đường nhập-từ-chat đó gọi thẳng `proposeSplit` + `confirmExpense`
(`TinNhan.tsx:386-394`) và **không đi qua `DeXuat`** — nên hôm nay không lộ. Nó
cũng đã có sẵn cách gọi tên đúng: `tenTuRoster` trả `TEN_CHUA_BIET`, không bao
giờ trả id.

Nói gọn: **#450 lần nữa, cùng hình dạng.** Lỗ không phải "không có", mà là "chưa
có đường đi tới". Cái đi tới nó chỉ cần một trong hai chuyện: nối màn chốt vào
bản nháp đọc từ chat, hoặc nới `ready` để đỡ được ca "trả tiền hộ, không ăn".

## Đề xuất (không phải blocker)

1. `participants.ts` đã có `labelFor` và `labelInGroup` — cả hai không bao giờ
   trả id, `labelInGroup` còn đánh số người trùng tên. `DeXuat.tsx` tự viết lại
   phép tra cứu thay vì gọi chúng; đó là toàn bộ lỗi.
2. Ba chỗ trước của bug-050923 đều có ca canh riêng
   (`nguoi-chuyen-khong-in-id`, `so-du-khong-in-id`,
   `ten-tu-may-chu-khong-in-id`, `ten-dia-diem-album`). `DeXuat` chưa có.
   Ca cho nó phải render với **id lạ**, vì roster đủ thì cả hai nhánh im.
3. Tôi **không** sửa `DeXuat.tsx`: bản vá đang ở nhánh
   `frontend/co-may-sinh-mac-dinh-id` của frontend.

## Phép đo này KHÔNG chứng minh

- Rằng máy chủ thật không bao giờ trả `rounding_gainers` ngoài `participant_ids`.
  Đó là khẳng định về `services/api`, không phải về trình duyệt này. B chỉ đo
  **client làm gì nếu điều đó xảy ra** — và câu trả lời là: in id ra.
- Rằng không màn nào khác in id. Chỉ `DeXuat` được đi tới.
- Rằng cửa ở D đóng trên iOS/Android. `react-native-web` không phải
  `react-native`.
- Rằng `ready` sẽ còn đóng ở bản sau. Một cửa giữ bằng một phép kiểm là cửa mà
  một thay đổi sau này mở được mà không ai thấy.

## Tái lập

```bash
cd apps/mobile
npm run build:check
npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs   # cho đối chứng C
node tests/qa2-111127-hai-cho-de-xuat/probe-in-id-tren-man.mjs
```

Chạy 3 lượt, số ra giống hệt nhau, và `A-de-xuat.png` **trùng từng byte** giữa
các lượt (94428 byte). Ảnh chụp và chữ đổ ra nằm ở thư mục tạm của OS, ngoài
repo — bill và ảnh màn hình không vào Git.
