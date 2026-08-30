<div align="center">

<img src="docs/assets/banner.svg" alt="Rủ Đi — AI đi chơi, chia bill thông minh" width="100%">

**Rủ nhau đi chơi → ăn uống → chia bill → thu tiền về.**<br>
Một app, một vòng lặp, và đúng **một** phép chia tiền trong toàn hệ.

![Trạng thái](https://img.shields.io/badge/tr%E1%BA%A1ng_th%C3%A1i-PoC_%C2%B7_l%C3%A1t_c%E1%BA%AFt_d%E1%BB%8Dc_ch%E1%BA%A1y_%C4%91%C6%B0%E1%BB%A3c-c93900?style=flat-square&labelColor=1f2230)
![Test](https://img.shields.io/badge/test-3143_ca-00756b?style=flat-square&labelColor=1f2230)
![API](https://img.shields.io/badge/API-FastAPI_0.115_%C2%B7_Python_3.12-0f766e?style=flat-square&labelColor=1f2230)
![App](https://img.shields.io/badge/app-Expo_57_%C2%B7_RN_0.86_%C2%B7_TS_strict-7d49ef?style=flat-square&labelColor=1f2230)
![Database](https://img.shields.io/badge/database-PostgreSQL_16-336791?style=flat-square&labelColor=1f2230)
![Giấy phép](https://img.shields.io/badge/gi%E1%BA%A5y_ph%C3%A9p-MIT-676e7b?style=flat-square&labelColor=1f2230)

<br>

<img src="docs/assets/hero-mockup.jpg" alt="Sáu màn concept của Rủ Đi" width="92%">

<sub>Mockup concept đã duyệt. Mọi con số và tên người trong ảnh là **dữ liệu trình diễn**, không phải người dùng thật.</sub>

</div>

---

## Phần đau thật không phải là chia tiền

Nhóm bạn Việt đi chơi cùng nhau. Một người ứng tiền trả bill, rồi phải đi đòi lại:
nhắn riêng từng người, gửi số tài khoản, nhớ ai đã chuyển, nhắc mà không mất lòng.

> Spec kết luận rằng phần đau thật **không phải chia tiền mà là đi thu tiền**.
> Nên màn hình trung tâm là **bảng thu tiền**, không phải màn chia tiền.

Từ đó ra hai vai, và hai bề mặt cho hai vai:

| Vai | Họ muốn gì | Họ dùng gì |
|---|---|---|
| **Người tổ chức** | Rủ, chốt chỗ, ứng tiền, rồi đòi lại mà không mất lòng | App Expo (`apps/mobile/`) |
| **Người được rủ** | Đúng hai điều: *mình nợ bao nhiêu* và *chuyển cho ai* | Một link trong chat nhóm, **không cần cài app** (`app/web/`) |

Người không cài app vẫn là người dùng hạng nhất. Trang khách dùng chung hệ thiết kế
với app, không phải một hệ thứ hai.

---

## Vòng lặp sản phẩm

<div align="center">
<img src="docs/assets/so-do-1-vong-lap.svg" alt="Vòng lặp sản phẩm: trước buổi đi là khám phá, nhóm chat, bình chọn, đi chơi; sau bữa ăn là chụp bill, chia tiền, VietQR, kỷ niệm" width="100%">

<sub>Và vòng khép lại: xong một chuyến, AI biết thêm nhóm này thích gì và ai đã trả cho ai, nên lần gợi ý sau khá hơn lần trước.</sub>
</div>

<details>
<summary><b>Nguồn Mermaid của sơ đồ này</b></summary>

```mermaid
flowchart TB
    subgraph TRUOC["Trước buổi đi"]
        direction LR
        A["Khám phá<br/>AI gợi ý chỗ"] --> B["Nhóm chat<br/>AI lên kế hoạch"]
        B --> C["Bình chọn<br/>chốt kèo"]
        C --> D["Đi chơi<br/>check-in"]
    end
    subgraph SAU["Sau bữa ăn"]
        direction LR
        E["Chụp bill<br/>AI đọc từng món"] --> F["Chia tiền<br/>gán món cho người"]
        F --> G["VietQR<br/>thu tiền về"]
        G --> H["Kỷ niệm<br/>tường nhóm"]
    end
    TRUOC --> SAU

    classDef brand fill:#fff0ea,stroke:#c93900,stroke-width:2px,color:#1f2230
    classDef ai fill:#f5f1ff,stroke:#7d49ef,stroke-width:2px,color:#1f2230
    classDef money fill:#d5f5f0,stroke:#00756b,stroke-width:2px,color:#1f2230
    class A,C,D,H brand
    class B,E ai
    class F,G money
    style TRUOC fill:#ffffff,stroke:#e7dace,color:#4e5563
    style SAU fill:#ffffff,stroke:#e7dace,color:#4e5563
```

Ảnh trên render sẵn từ chính nguồn này, không nhờ trình render của GitHub.
Muốn dựng lại: mermaid `11.4.1`, `htmlLabels:false` (bắt buộc — nhãn dạng
`<foreignObject>` **không** hiện khi SVG được nạp qua `<img>`, mà GitHub nạp ảnh
bằng `<img>`), `securityLevel:'strict'`, `useMaxWidth:false`, rồi lấy `viewBox`
từ `getBBox()` chứ đừng tin `viewBox` mermaid tự ghi — nó hụt và cắt mất nhãn
actor dưới đáy sơ đồ tuần tự.

</details>

Đây là câu mà một sản phẩm hàng xóm không sao chép được nếu chỉ làm một chặng:
**cùng một AI đã gợi ý quán là AI đọc hoá đơn của quán đó, và nó biết ai đã ngồi ở đó.**
Splitwise chia tiền nhưng không biết nhóm bạn là ai. Nhóm chat rủ được nhưng không chia được tiền.

<table>
<tr>
<td width="25%" align="center"><img src="docs/assets/man-kham-pha.jpg" alt="Màn Khám phá" width="100%"></td>
<td width="25%" align="center"><img src="docs/assets/man-chat-ai.jpg" alt="Màn Nhóm chat với AI" width="100%"></td>
<td width="25%" align="center"><img src="docs/assets/man-thanh-toan.jpg" alt="Màn Kết quả thanh toán" width="100%"></td>
<td width="25%" align="center"><img src="docs/assets/man-tai-chinh.jpg" alt="Màn Tài chính cá nhân" width="100%"></td>
</tr>
<tr>
<td align="center"><b>Khám phá</b><br><sub>AI gợi ý chỗ theo gu của nhóm</sub></td>
<td align="center"><b>Nhóm chat</b><br><sub>AI ở trong nhóm, có context của nhóm</sub></td>
<td align="center"><b>Thu tiền</b><br><sub>ai chuyển cho ai, còn thiếu bao nhiêu</sub></td>
<td align="center"><b>Cá nhân</b><br><sub>tài chính xuyên nhóm, không chỉ một chuyến</sub></td>
</tr>
</table>

<sub>Mockup concept, **dữ liệu trình diễn**. Màn Cá nhân là tài chính xuyên nhóm: rời một nhóm không xoá được khoản còn nợ.</sub>

---

## Lát cắt dọc của tiền

Đây là đường đi đã chạy thật, đầu tới cuối:

<div align="center">
<img src="docs/assets/so-do-2-lat-cat-doc.svg" alt="Sơ đồ tuần tự của lát cắt dọc: người tổ chức gọi POST /expenses, domain chia tiền, sổ cái ghi event, khách mở link và báo đã chuyển" width="100%">
</div>

<details>
<summary><b>Nguồn Mermaid của sơ đồ này</b></summary>

```mermaid
sequenceDiagram
    autonumber
    actor T as Người tổ chức
    participant API as FastAPI
    participant D as domain/allocator
    participant S as Sổ cái
    actor K as Người được rủ

    T->>API: POST /expenses
    API->>D: chia tiền bằng Fraction, kết quả là số nguyên đồng
    D-->>API: phân bổ, Σ đúng bằng tổng khoản chi
    T->>API: confirm
    API->>S: ghi event, không ghi đè
    T->>API: POST /batches rồi publish
    API-->>T: envelope kèm chuỗi VietQR
    K->>API: GET /g/{token}
    API-->>K: trang khách, chỉ envelope của chính mình
    K->>API: tôi đã chuyển rồi
    T->>API: confirm-receipt
    Note over API,S: completed do domain transition sinh ra.<br/>Không có nút "đánh dấu xong".
```

Ảnh trên render sẵn từ chính nguồn này, không nhờ trình render của GitHub.
Muốn dựng lại: mermaid `11.4.1`, `htmlLabels:false` (bắt buộc — nhãn dạng
`<foreignObject>` **không** hiện khi SVG được nạp qua `<img>`, mà GitHub nạp ảnh
bằng `<img>`), `securityLevel:'strict'`, `useMaxWidth:false`, rồi lấy `viewBox`
từ `getBBox()` chứ đừng tin `viewBox` mermaid tự ghi — nó hụt và cắt mất nhãn
actor dưới đáy sơ đồ tuần tự.

</details>

Vài điều cố ý, đừng đọc nhầm thành thiếu sót:

- **Sản phẩm không giữ tiền và không chuyển tiền.** Nó dựng chuỗi EMVCo để người
  dùng tự quét bằng app ngân hàng của họ.
- **`receiver_confirmed` không phải bằng chứng ngân hàng**, và câu chữ trên màn
  hình không được nói như thể nó là.
- **Sửa khoản chi tạo phiên bản mới**, không ghi đè bản cũ.
- Khách chỉ thấy envelope của chính mình: không số dư nhóm, không lịch sử,
  không allocation của người khác.

<div align="center">
<img src="docs/assets/luong-chia-tien.jpg" alt="Bốn bước chia bill: chụp bill, AI nhận diện món, gán món cho người, kết quả thanh toán kèm VietQR" width="78%">
</div>

<sub>Bốn bước của chặng chia bill trong mockup. **AI có mặt thì phải nói rõ là AI**: mọi kết quả máy đọc ra đều sửa được bằng tay trước khi chốt, và không có bước nào AI tự quyết chuyện tiền thay người dùng.</sub>

---

## Ba luật về tiền, không thương lượng

<table>
<tr>
<td width="33%" valign="top">

### 1 · Số nguyên đồng

Không `float`, không `Decimal`, kể cả ở giá trị trung gian.
`allocator.py` dùng `Fraction` để giữ hữu tỉ chính xác rồi mới rơi về đồng.

</td>
<td width="33%" valign="top">

### 2 · Σ = đúng tổng

Tổng phân bổ bằng **100%** khoản chi, không ngoại lệ.
**41 golden vector tính tay** giữ điều này.

</td>
<td width="33%" valign="top">

### 3 · Sổ là nguồn sự thật

Số dư luôn **tính lại được từ sổ**.
Cache không bao giờ là nguồn sự thật.

</td>
</tr>
</table>

> Đổi bất kỳ luật nào ở trên thì **mở ADR trước**, đừng sửa code trước.

---

## Kiến trúc

<div align="center">
<img src="docs/assets/so-do-3-kien-truc.svg" alt="Sơ đồ tầng: apps/mobile và app/web gọi app/api; app/api gọi domain, db, payments; db nói chuyện với PostgreSQL" width="100%">
</div>

<details>
<summary><b>Nguồn Mermaid của sơ đồ này</b></summary>

```mermaid
flowchart TB
    subgraph BM["Bề mặt"]
        M["apps/mobile<br/>Expo · React Native · TS strict"]
        W["app/web<br/>trang khách, render từ server"]
    end
    subgraph SH["Dùng chung"]
        P["packages/shared<br/>tokens.json · money.mjs · banks.json"]
    end
    subgraph BE["services/api"]
        A["app/api<br/>FastAPI · service · repository"]
        DOM["app/domain<br/>thuần: dict vào, dict ra"]
        DB["app/db<br/>SQLAlchemy · Alembic"]
        PAY["app/payments<br/>EMVCo + CRC"]
    end
    PG[("PostgreSQL 16<br/>JSONB · partial unique index · trigger append-only")]

    M --> A
    W --> A
    M -.-> P
    W -.-> P
    A --> DOM
    A --> DB
    A --> PAY
    DB --> PG

    classDef brand fill:#fff0ea,stroke:#c93900,stroke-width:2px,color:#1f2230
    classDef ai fill:#f5f1ff,stroke:#7d49ef,stroke-width:2px,color:#1f2230
    classDef money fill:#d5f5f0,stroke:#00756b,stroke-width:2px,color:#1f2230
    class M,W brand
    class P ai
    class A,DOM,DB,PAY,PG money
    style BM fill:#ffffff,stroke:#e7dace,color:#4e5563
    style SH fill:#ffffff,stroke:#e7dace,color:#4e5563
    style BE fill:#ffffff,stroke:#e7dace,color:#4e5563
```

Ảnh trên render sẵn từ chính nguồn này, không nhờ trình render của GitHub.
Muốn dựng lại: mermaid `11.4.1`, `htmlLabels:false` (bắt buộc — nhãn dạng
`<foreignObject>` **không** hiện khi SVG được nạp qua `<img>`, mà GitHub nạp ảnh
bằng `<img>`), `securityLevel:'strict'`, `useMaxWidth:false`, rồi lấy `viewBox`
từ `getBBox()` chứ đừng tin `viewBox` mermaid tự ghi — nó hụt và cắt mất nhãn
actor dưới đáy sơ đồ tuần tự.

</details>

| Tầng | Việc của nó | Ràng buộc cứng |
|---|---|---|
| `app/domain/` | Tiền, sổ, đợt thu, quyền, hiển thị | 🚫 **Không được import** `app.db`, `app.api`, `app.payments`, `sqlalchemy`, `fastapi`, `alembic`, `pydantic` |
| `app/api/service.py` | Workflow: gọi domain trước, rồi mới gọi repository | Repository không bao giờ tự chế allocation |
| `app/api/repository.py` | `ApiRepository` (Protocol) + bản SQLAlchemy | Trạng thái nghĩa vụ **suy ra từ event**, không đọc cột đã lưu |
| `app/web/guest_view.py` | Biên rò rỉ của trang khách | Template **không bao giờ tự query**, chỉ render view model |
| `app/payments/vietqr.py` | Dựng chuỗi EMVCo + CRC | Không giữ tiền, không chuyển tiền |

Ranh giới `domain/` không phải lời hứa: `tests/test_import_boundary.py` parse AST và
cưỡng chế nó. Lý do là luật tiền số 3 ở trên.

`/healthz` cố ý **không** chạm database: restart API không sửa được Postgres.

<details>
<summary><b>Đo lại các con số trong README này</b></summary>

```bash
git rev-parse --short HEAD                                    # f3d4ede khi đo
python3 -m pytest services/api/tests tests -q --collect-only   # 3143 ca
python3 -c "import sys; sys.path.insert(0,'services/api')
from app.api.main import app; from fastapi.routing import APIRoute
print(len([r for r in app.routes if isinstance(r, APIRoute)]))"   # 90 route
ls services/api/app/api/routes/*.py | wc -l                    # 28 module route
ls services/api/app/domain/*.py | wc -l                        # 27 module domain
find apps/mobile/src -name '*.ts*' | wc -l                     # 104 file
find apps/mobile/src -name '*.ts*' | xargs cat | wc -l         # 28274 dòng
python3 -c "import json,glob; print(sum(len(json.load(open(f))) for f in glob.glob('services/api/tests/domain/golden/*.json')))"   # 41 golden vector
```

Đếm route bằng hai cách khác nhau ra hai con số khác nhau (`grep` decorator ra 89,
`app.routes` ra 90, số path duy nhất là 78). Con số trong README là `APIRoute` thật
sự được đăng ký, vì đó là thứ trả lời được câu "server này phục vụ cái gì".

Repo này có nhiều lane cùng đẩy vào `main`, nên các con số trên **trôi theo ngày**.
Chúng được đo tại `f3d4ede`; lệch vài đơn vị so với hôm nay là bình thường, lệch
hàng chục thì đoạn văn quanh nó đã cũ.

</details>

---

## Hệ thiết kế

Màu **không phải trang trí**. Nhìn thấy màu là biết đang ở phần nào của sản phẩm:

<img src="docs/assets/bang-mau.svg" alt="Ba tông màu: cam accent, teal split, tím ai, kèm tỉ lệ tương phản đo được" width="100%">

| Tông | Token | Nghĩa | Sáng | Tối |
|---|---|---|---|---|
| Cam | `accent` | Thương hiệu và hành động chính | `#c93900` · 5.16:1 | `#fb693e` · 5.77:1 |
| Teal | `split` | Chia bill, tiền, quyết toán | `#00756b` · 5.59:1 | `#02a498` · 5.42:1 |
| Tím | `ai` | Do máy sinh ra, người còn sửa được | `#7d49ef` · 5.16:1 | `#9667ff` · 4.55:1 |

**Một màn hình chỉ có MỘT tông dẫn.** Hai tông dẫn cùng lúc là lỗi, không phải lựa chọn.
Trang khách là mặt quyết toán nên tông dẫn của nó là teal, dù cam mới là màu thương hiệu.

- Nguồn số duy nhất: [`packages/shared/tokens.json`](packages/shared/tokens.json). Hai bề mặt đọc lại cùng một file.
- Màu **đo bằng script lấy mẫu điểm ảnh** trên mockup, không ước lượng bằng mắt.
  Màu nào không đạt WCAG AA thì bị làm tối lại, và **cả hai số đều ghi lại** trong [`DESIGN.md`](DESIGN.md).
- 46 cặp chữ trên nền đều được đo. Thấp nhất 4.52:1, không cặp nào dưới ngưỡng AA.
- Đích ngắm tối thiểu 44×44pt. Chuyện chia tiền xảy ra khi người ta đang đứng dậy ra về, một tay cầm điện thoại.

Xem thử hệ thiết kế và trang khách mà **không cần database**:

```bash
cd services/api && python3 -m app.web.preview
```

---

## Chạy thử

<table>
<tr><td width="50%" valign="top">

**Đường nhanh nhất — Docker, có sẵn dữ liệu demo**

```bash
make demo     # dựng hệ + nạp "Team Đà Lạt":
              # 7 người, 3 chuyến, còn nợ thật
make smoke    # gọi /healthz qua cổng đã publish
make logs     # bám log API và Postgres
make down     # tắt, GIỮ dữ liệu trong volume
```

</td><td width="50%" valign="top">

**Đường thủ công**

```bash
docker compose up -d postgres
cp .env.example .env
pip install -r services/api/requirements-dev.txt
cd services/api && alembic upgrade head
uvicorn app.api.main:app --host 0.0.0.0 --port 8099
```

</td></tr>
</table>

`--host 0.0.0.0` không phải trang trí: mặc định `uvicorn` chỉ nghe `127.0.0.1`,
và điện thoại không tới được loopback của máy khác.

Mặc định là **API 8099**, Metro 8081. 8099 là con số app tự rơi về khi không có
`EXPO_PUBLIC_API_URL` (`apps/mobile/src/api.ts`), nên đừng đổi nó chỉ vì quen tay gõ 8000.

⚠️ `make clean` **xoá cả volume Postgres lẫn ảnh đã tải lên của cả máy**, nên nó đòi `CONFIRM=<tên project>`.

<details>
<summary><b>Dựng ảnh Docker của API</b></summary>

```bash
cd services/api && docker build -t mobile-api .
```

Build context là `services/api/`, **không phải** gốc repo. Docker chỉ đọc
`.dockerignore` ở gốc build context, nên file đó phải nằm trong `services/api/`;
đặt ở gốc repo là không có tác dụng.

</details>

---

## Chạy trên điện thoại thật (Expo Go)

Điện thoại và máy này phải **cùng một Wi-Fi**. Kiểm trước khi mở Expo Go:

```bash
scripts/phone_path.py check     # thoát 1 nếu đường chưa thông, kèm cách sửa
scripts/phone_path.py up        # kiểm rồi phát QR trỏ vào địa chỉ LAN
```

Rồi mở **Expo Go** và quét mã. `up` in sẵn hai dòng cho biết QR trỏ đi đâu và app
sẽ gọi API ở đâu. Đọc hai dòng đó trước khi quét.

<details>
<summary><b>Bốn lý do app không lên, không cái nào tự nói ra</b></summary>

| Triệu chứng trên điện thoại | Nguyên nhân | Cách sửa |
|---|---|---|
| Quét xong quay mãi rồi hết giờ | WSL2 chặn kết nối từ ngoài vào (`DefaultInboundAction = Block`) | `scripts/phone_path.py open-firewall` — cần quyền Administrator, mở đúng 2 cổng TCP cho riêng subnet Wi-Fi hiện tại |
| App lên nhưng mọi màn báo lỗi mạng | `BASE_URL` còn là `localhost`, mà trên điện thoại `localhost` là chính nó | dùng `up`, nó tự đặt `EXPO_PUBLIC_API_URL` theo IP LAN |
| Terminal xanh nhưng không có server | cổng 8081 bận; `expo start` hỏi đổi cổng, trong shell không tương tác nó in `Skipping dev server` rồi **thoát mã 0** | `--metro-port 8082` |
| Metro chết ngay khi khởi động: `configs.toReversed is not a function` | `node` trên PATH quá cũ (Debian/Ubuntu cài sẵn 18.x; RN 0.86 cần `^20.19.4 \|\| ^22.13.0 \|\| ^24.3.0 \|\| >= 25`) | không phải lỗi app. `up` tự dùng bản hợp lệ đã cài (nvm/fnm) và in ra nó đã đổi; nếu máy không có bản nào: `nvm install 20` |

Không cần tự nhớ mình đang ở Node nào. `check` đọc dải phiên bản từ chính
`apps/mobile/node_modules` và nói ra; `up` chạy Metro dưới bản hợp lệ dù PATH của
bạn trỏ vào đâu. Việc đổi chỉ áp dụng cho tiến trình `up` sinh ra.

Khi cổng bận thật, hoặc khi máy có nhiều card mạng:

```bash
scripts/phone_path.py --api-port 8100 --metro-port 8082 up
scripts/phone_path.py up --host <ip-LAN-của-máy-này>
eval "$(scripts/phone_path.py env)"   # chỉ lấy biến, tự chạy expo sau
```

Đổi `--api-port` thì phải bật `uvicorn` ở đúng cổng đó. Script chỉ nói cho app
biết gọi đi đâu, nó không dựng server hộ bạn.

Gỡ luật tường lửa khi không cần nữa:

```powershell
Remove-NetFirewallHyperVRule -Name 'RuDi-ExpoGo'
```

Điện thoại không cùng Wi-Fi được (mạng khách chặn máy nói chuyện với nhau) thì
`npx expo start --tunnel` vẫn nạp được app, nhưng tunnel chỉ đưa Metro ra ngoài,
**không** đưa API, nên app lên rồi vẫn không gọi được server.

</details>

---

## Test

```bash
python3 -m pytest services/api/tests tests -q   # domain + API (fake repo) + repo guard
node packages/shared/money.test.mjs             # hai bề mặt, cùng một bộ golden
scripts/setup-hooks.sh                          # bật repo guard trước khi commit
make gate                                       # chạy các cổng của CI ngay tại máy
```

Tầng chạy trên **PostgreSQL thật** mặc định bị skip nếu thiếu URL. Skip không phải là xanh:

```bash
make test-db      # database dùng một lần, tự dựng tự dọn
```

### Mỗi tầng chứng minh được gì, và không chứng minh gì

Đọc kỹ **cột phải** trước khi tin một dấu xanh.

| Tầng | Chứng minh | **Không** chứng minh |
|---|---|---|
| 41 golden vector + `test_golden_selfcheck.py` | Corpus nhất quán nội tại theo ADR-0004 | Tác giả corpus đọc đúng contract — cùng một người viết cả hai |
| `test_selfcheck_catches_mutants.py` | Self-check thực sự đỏ khi đáp án sai | — |
| `tests/api/` với fake repository | Orchestration HTTP ↔ domain | Bất kỳ câu SQL, index, view, trigger nào |
| `tests/postgres/` | Repository thật sau khi Alembic migrate một schema riêng | Mọi method, mọi race, mọi query plan |
| `tests/db/test_migration_matches_models.py` | Migration khớp models, không cần DB | — |
| QA hình ảnh + thăm dò (ADR-0010) | Trang render được, đọc được, không lộ dữ liệu người khác, ở các trạng thái **đã quét** | **Mã QR có quét được bằng app ngân hàng thật không** · người thật có hiểu không · ô nào **chưa** quét |

SQLite bị từ chối có chủ ý: schema production dựa vào JSONB, partial unique index,
view và trigger append-only. Thêm hành vi persistence mới thì **thêm ca live tương ứng**;
mở rộng fake rồi coi đó là bằng chứng DB là nói dối.

Ảnh trong README lấy từ `product/` — spec 47 feature và bộ mockup 21 màn. Thư mục đó
**không có trên `main`**: nó nặng 51 MB và chỉ là nguồn thiết kế, nên bản clone sạch sẽ
không có nó. Cái đã commit là 8 file trong `docs/assets/`, mỗi file pin sha256 trong
`.repo-guard-allowlist.json`, thu nhỏ và cắt lại từ chính bộ mockup đó.

---

## Bố cục repo

```
services/api/app/domain/     thuần: tiền, sổ, đợt thu, quyền, hiển thị (27 module)
services/api/app/db/         SQLAlchemy + Alembic
services/api/app/api/        FastAPI, 90 route trên 28 module
services/api/app/web/        trang khách, render từ server
services/api/app/payments/   chuỗi VietQR EMVCo + CRC
apps/mobile/                 Expo + TypeScript (104 file, ~28.3k dòng)
packages/shared/             token thiết kế, định dạng tiền, danh sách ngân hàng
docs/assets/                 ảnh của README, pin sha256 trong repo guard allowlist
docs/decisions/              ADR — đọc trước khi đổi hành vi
phase0/  docs/protocol/v1/   ĐÓNG BĂNG tại chỗ, không sửa, không xoá
```

---

## Quy trình

Nguồn sự thật: [`docs/team/charter.md`](docs/team/charter.md) ·
[`docs/decisions/`](docs/decisions/) ·
[`docs/architecture/00-layout-va-so-huu.md`](docs/architecture/00-layout-va-so-huu.md).
Đọc trước khi đổi hành vi.

- **Ranh giới sở hữu.** Claude giữ `app/web/` và `apps/mobile/`. Codex giữ `db/`,
  `api/`, `payments/`, `domain/` và test backend. Ở trang khách: route và truy cập
  dữ liệu là của Codex, template không bao giờ tự query.
- **Nhánh**: `<owner>/p0-w<N>-<slug>`, slug phải là Work ID cụ thể.
- **PR** (ADR-0007): review sống trên GitHub PR. Verdict đúng ba giá trị:
  `APPROVE` / `REQUEST_CHANGES` / `REJECT`. **Không tự review PR của chính mình.**
- **Blocker chỉ hợp lệ** khi thuộc 5 loại: vi phạm spec/cổng · sai tiền ·
  quyền riêng tư/bảo mật/consent · hỏng tính hợp lệ thí nghiệm · không tái lập được.
  Đặt tên và "tôi thích cách kia hơn" là suggestion, không phải blocker.
- **Repo guard fail closed** với binary, file text > 2 MiB, symlink, gitlink mới.
  Muốn thêm artifact thì pin `path` + `sha256` + `rules` + `reason` vào
  `.repo-guard-allowlist.json`. Xem [`docs/security/repo-guard.md`](docs/security/repo-guard.md).
- **Không bao giờ đưa vào Git**: ảnh bill, số tài khoản, tên người tham gia,
  transcript thô, file export, `.env` thật. `.gitignore` không phải nơi lưu an toàn.

---

## Cái này KHÔNG phải là gì

Phần quan trọng nhất của README này. Đọc trước khi tin bất cứ dấu xanh nào ở trên.

- ❌ **Chưa có bằng chứng hành vi nào.** [ADR-0006](docs/decisions/ADR-0006-gac-giai-doan-0-de-dung-san-pham.md)
  ghi rõ: Giai đoạn 0 bị gác lại theo quyết định có ý thức của chủ sản phẩm. Đây là
  một canh bạc, không phải một giả thuyết đã được kiểm chứng. **Đừng đọc bộ test xanh
  thành "sản phẩm này đúng".**
- ❌ **Chưa có auth production.** Header `X-Actor-ID` / `X-Actor-Roles` /
  `X-Actor-Contexts` do gateway tin cậy ghi đè là chỗ tạm cho lát cắt dọc.
  Đừng xây thêm gì dựa trên giả định nó an toàn.
- ❌ **Chưa có người dùng thật**, chưa có testimonial, chưa có số liệu tăng trưởng,
  chưa có app trên store. Mọi con số trong mockup (4.9 sao, "AI MATCH 95%", tên
  Minh Anh / Quang Huy, số tài khoản) là **dữ liệu trình diễn**.
- ❌ **Không giữ tiền, không chuyển tiền.** Chỉ sinh chuỗi VietQR.
- ❌ **Chưa quyết Home và cấu trúc tab.** Spec mục 14.3 cấm thiết kế Home trước khi
  biết hành động nào tồn tại.
- ⚠️ **Branch protection chưa bật** (GitHub free + repo private không cho), nên mọi
  luật merge ở trên là **kỷ luật**, không phải cưỡng chế. Hook local vẫn bị
  `--no-verify` đi qua.
- ⚠️ **Ruff được cấu hình nhưng cây hiện không sạch và CI không gate nó.** Chạy ruff
  trên file mình đang sửa; đừng chạy `--fix`/`format` cả cây, diff format sẽ nhấn
  chìm thay đổi thật.

Nguyên tắc phía sau danh sách này: **vỏ thì nói là vỏ.** Feature nằm ngoài đường đi
chính được làm đúng vỏ và dán nhãn. Giấu chuyện nó là vỏ mới là lỗi.

---

<div align="center">

**Rủ Đi thôi!**

[`PRODUCT.md`](PRODUCT.md) · [`DESIGN.md`](DESIGN.md) · [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md) · [`docs/codex/QUEUE.md`](docs/codex/QUEUE.md)

Giấy phép [MIT](LICENSE) · © 2026

</div>
