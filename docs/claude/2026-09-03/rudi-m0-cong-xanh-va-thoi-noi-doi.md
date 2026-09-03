# M0 — ba cổng đỏ, và bốn câu trên màn không đúng sự thật

- **Nhánh:** `claude/p0-w-rudi-du-lieu-that`, xếp chồng trên head PR #512 (`a2f87a9`)
- **Cha để so:** `f63628d` — bản `main` mà #512 rẽ ra
- **protocol_version:** v1
- **Verdict của lượt review trước:** `REQUEST_CHANGES` trên #512 (giữ nguyên, không sửa tại chỗ)
- **Người review bản này:** Codex hoặc Lead. ADR-0007 — tôi là tác giả nên **không** tự review.
- **Đo trên:** emulator `rudi-qa3` / `emulator-5554`, Android 15, 1080×2400, Expo Go **57.0.9**, Metro của chính cây này ở `localhost:8095`, Maestro 2.10.0. Máy chủ thật ở `:8106` cho một flow.

---

## 1. Ba cổng, không phải hai

Lượt review #512 báo hai ca đỏ trong `npm test`. Chạy thêm bộ cổng Python thì ra cái thứ ba.

| Cổng | `f63628d` | `a2f87a9` (#512) | nhánh này |
|---|---|---|---|
| `apps/mobile: npm test` | 1039 pass / 0 fail | 1045 pass / **2 fail** | **1060 pass / 0 fail** |
| `scripts/check_api_contract.py` | exit 0 | **exit 1** | exit 0 |
| `scripts/check_server_routes_called.py` | exit 0 | exit 0 | exit 0 |
| `scripts/check_screens_reachable.py` | exit 0 | exit 0 | exit 0 |
| `scripts/check_actor_headers.py` | exit 0 | exit 0 | exit 0 |
| `scripts/repo_guard.py staged` | — | — | exit 0 |

**Cổng thứ ba, và vì sao nó không phải lỗi 404 thật.** `src/rudi/ledger.ts:19` gọi `/healthz`. Route đó **có thật** — tôi chạy API ở `:8106` và `GET /healthz` trả 200 — nhưng nó khai ở `services/api/app/api/main.py:220` với `include_in_schema=False`, còn cổng chỉ đọc `app/api/routes/*.py`. Đây là **điểm mù của cổng**.

Tôi **không** vá cổng: `scripts/` là hạ tầng dùng chung và sửa nó cần Codex duyệt. Tôi xoá `probeLedger()` thay vì vá, vì phép thăm dò đó vốn không đo được cái nó nói. `/healthz` cố ý **không chạm database**, nên «máy chủ sống» chỉ có nghĩa «tiến trình còn chạy» — và màn Đăng nhập đang dùng kết quả đó để quyết định câu chữ về **OTP**, một thứ `/healthz` không biết gì. Ba màn giờ hoặc nói thẳng («chưa có nhà cung cấp OTP»), hoặc để một request thật trả về lỗi thật qua `thongDiepNguoiDoc`.

**Việc còn nợ (Codex):** cho `check_api_contract.py` đọc route khai ngoài `routes/`, hoặc ghi nhận `/healthz` vào một file pin. Hôm nay bất kỳ client nào gọi `/healthz` đều làm cổng đỏ, và cái đỏ đó chỉ sai địa chỉ.

---

## 2. Bốn câu trên màn không đúng sự thật

`grep -rn "AsyncStorage|SecureStore|expo-secure-store|localStorage" apps/mobile/src apps/mobile/app` ra **rỗng**. App không lưu gì. Trong khi trên màn có:

| Chỗ | Trước | Sau |
|---|---|---|
| `Profile.tsx` nút sửa hồ sơ | «Lưu trên máy» | «Xong» |
| `Onboarding.tsx` cá nhân hoá | «Lựa chọn lưu trên máy cho bản trải nghiệm này.» | «Lựa chọn chỉ sống trong lần mở app này.» |
| `Group.tsx` phiếu bầu | «Phiếu lưu trên máy.» | «Phiếu chỉ nằm trong lần mở app này.» |
| `Profile.tsx` đã lưu | «N địa điểm trên máy» | «N địa điểm trong lần mở app này» |
| `Outing.tsx` vị trí | «chỉ lưu trạng thái trên máy» | «chỉ đổi trạng thái trong lần mở app này» |
| `Outing.tsx` / `Bill.tsx` nhắc | «Đã nhắc N người trên máy» | «... trong lần mở app này» |

Bằng chứng: `.maestro/07-mat-trang-thai-khi-tat-app.yaml` sửa slot 18:00 thành Still Cafe, `stopApp`, mở lại — slot về `BBQ bên hồ Tuyền Lâm`.

**M1 đảo lại toàn bộ bảng này.** Khi AsyncStorage vào thì «lưu trên máy» thành sự thật và câu chữ viết lại đúng như thế. Flow 07 lúc đó phải **đổi cực**: nó đang xanh vì state mất, sau M1 nó phải đỏ.

**Đăng xuất giờ xoá phiên thật.** «Đăng xuất» trước đây là `router.replace("/welcome")` và không gì khác, nên người tiếp theo bấm «Vào bản trải nghiệm» trên cùng tiến trình thừa hưởng tên, chat, check-in và địa điểm đã lưu của người trước. Đo được: đổi tên thành `NGUOI LA KHAC`, đăng xuất, vào lại — **vẫn là `NGUOI LA KHAC`**. Giờ có `resetSession()`, và `.maestro/11` gác chiều ngược lại.

---

## 3. Luật làm tròn: client lệch server một đồng

`money.ts` chia **theo từng dòng** rồi cộng, và đưa đồng dư cho **người đầu tiên trong mảng**. `services/api/app/domain/allocator.py:254-267` chia **một lần cho cả khoản chi**, bằng **largest remainder**, tie-break `(-remainder, advancer trước, id theo byte UTF-8)`.

Cả hai giữ luật tiền 2 (Σ phân bổ = tổng), nên cả hai **trông đúng** trên màn và trong một phép cộng. Chúng khác nhau ở chỗ **ai** nhận đồng lẻ, và khác nhau ở tổng mỗi người bất cứ khi nào bill có hơn một dòng — cộng các phần đã làm tròn từng dòng không phải cùng một phép tính với làm tròn một tổng.

Đo được, chạy chính allocator của máy chủ:

```
BILL mặc định        server = client cũ = client mới   (mọi dòng chia hết, không có dư)
BILL + Minh Anh vào "Bò nướng"
  server:  minh-anh 360.417 · tuan-kiet 320.416 · quang-huy 335.417   gainers: minh-anh, quang-huy
  client cũ: minh-anh 360.416
```

Một đồng. Đủ nhỏ để không ai để ý, và đủ để số trên màn **nhảy** vào ngày Pha B confirm khoản chi mà không có gì trên màn giải thích.

`money.ts` giờ chạy đúng thuật toán của server: exact share mang bằng **tử số nguyên trên một mẫu số chung** (lcm của các đầu người) nên số học trước điểm làm tròn duy nhất là số học nguyên chính xác — JS không có `Fraction`, và `/` ở đây là float mà luật tiền 1 cấm. `assertSafe` từ chối con số thay vì để tử số trôi qua 2^53 rồi nói dối trong im lặng.

`tests/rudi-money.test.mjs` neo vào **đầu ra của chính allocator**, kèm lệnh tái dẫn xuất trong docstring. Hai người viết cùng một đáp án hai lần là đúng cái hỏng mà `CLAUDE.md` nêu cho corpus golden, nên số được **chép từ bên kia** chứ không tự tính lại.

---

## 4. Deep link — và cái mà chỉ máy thật mới nói ra

### 4.1. Link vào route con bị nuốt

`exp://localhost:8095/--/settlements/team-da-lat` đáp xuống màn welcome, **4/4 lần**. A/B: bỏ đúng một dòng `<LegacyFragmentAdapter />` thì cùng link đó mở đúng màn Quyết toán.

Gốc: guard `if (pathname !== "/") return` là **đồng bộ**, còn `router.replace` nằm sau `Linking.getInitialURL().then(...)` là **bất đồng bộ**. Cold start render `/` một frame trước khi router phân giải deep link, nên guard đi qua, promise resolve sau, và `router.replace("/welcome")` đè lên đúng màn mà link vừa mở. Với scheme `rudi://` đó là **mọi** link mời, chia sẻ và thông báo đẩy.

Quyết định giờ nằm ở `src/rudi/duong-vao.ts` — hàm thuần của chuỗi URL, test được không cần thiết bị, không cần router, không cần một frame render.

### 4.2. Và bản vá đầu tiên của tôi đã sai, máy thật nói ra

Bản đầu của `duong-vao.ts` **bỏ luôn** fallback `?? "/welcome"`, lập luận rằng `app/index.tsx` vốn đã `<Redirect href="/welcome" />` cho lối vào không có path.

Lập luận đó **sai**, và không cổng nào trong repo phát hiện được:

- `console.log` đặt trong `IndexRoute` **không bao giờ chạy**.
- Cold start không path đáp xuống tab **Khám phá**, không phải welcome.
- expo-router **không** định tuyến `exp://localhost:8095` qua `/`.
- 12 flow Maestro đỏ cùng lúc, tất cả ở bước «thấy nút *Rủ Đi thôi!*».

Nghĩa là cái `router.replace` vô điều kiện kia **là thứ duy nhất** đưa người ta tới màn welcome. Nó vừa là lỗi (nuốt deep link) vừa là tính năng (màn vào cửa), và chỉ đọc nguồn thì hai vai đó không tách ra được.

`tsc` xanh, `npm test` 1060/1060 xanh, cả bốn cổng Python xanh — trong khi màn hình đầu tiên của sản phẩm đã biến mất. Đây là ca cụ thể cho dòng trong `docs/architecture/01` mục 4/B2: **mọi thứ ta biết về app này, ta biết về bản web của nó.**

Luật cuối, và lý do nó được ghi thẳng ra thay vì suy từ cây route:

| URL | Kết quả |
|---|---|
| có path (`/--/settlements/x`, `rudi://votes/y`) | `giu-nguyen` — router đã xử lý rồi |
| địa chỉ harness (`?man=`, `#k=v`) | `giu-nguyen` |
| fragment có trong bảng (`#explore`) | `doi-huong` tới route đó |
| không URL, hoặc không path và fragment lạ | `doi-huong` `/welcome` |

---

## 5. Bản dựng release chưa gọi được máy chủ nào

- `src/api.ts:72` — `BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8099"`. `EXPO_PUBLIC_*` nhúng lúc bundle, nên bản dựng không đặt biến sẽ ship cái fallback. Trên điện thoại, `localhost` **là chính cái điện thoại**.
- `eas.json` khai bốn profile, **không profile nào** đặt biến đó.
- `app.json` không khai `usesCleartextTraffic`; Android chặn cleartext từ API 28.

Không có chỗ nào để trỏ tới: `docs/architecture/01` B3 đã đo — không `fly.toml`, không `render.yaml`, không `*.tf`. Viết một URL trông hợp lý vào đây là đúng cái loại lỗi cả nhánh này đang gỡ.

Nên `tests/cau-hinh-ban-dung.test.mjs` **ghi nhận khoảng trống** thay vì lấp nó, và chính bản ghi nhận là thứ đỏ:

- thêm một profile mới mà không kể tên → đỏ
- đặt URL trong khi profile vẫn nằm trong `CHUA_CO_MAY_CHU` → đỏ
- ship `http://` mà `app.json` không khai cleartext → đỏ

Đã kiểm cả hai chiều: thêm URL vào `production` → đỏ; thêm profile `staging` → đỏ; trả lại → xanh.

---

## 6. Cổng native

`make mobile-native` — cổng **duy nhất** trong repo chạy trên target sẽ ship. Ba cái neo, vì cả ba đã hỏng thật trên máy này:

1. **Metro phải là Metro của cây này** — cổng 8081/8082/8083 là Metro của lane khác, và bundle của họ là một bundle React Native hợp lệ, mới, hot-reload đầy đủ. Không có dấu hiệu nào ở phía thiết bị phân biệt được. Đo bằng `Starting project at`.
2. **Thiết bị phải thật sự nạp bundle đó** — `curl /status` trả 200 không chứng minh gì, cổng bị chiếm cũng trả 200. Đo bằng `Android Bundled`.
3. **Canary phải đỏ** — và bảng phải **không rỗng**. Danh sách nguồn rỗng làm cổng tự tháo trong im lặng.

Hai lỗi của chính cổng này bị chính nó bắt trong lúc dựng, và cả hai được ghi lại trong nguồn:
- `${API_PORT:+VAR=...}` ở vị trí prefix bị bash chạy như **tên lệnh**, vì bash quyết định cái gì là phép gán **trước khi** expand. Neo 1 bắt đúng: «Metro không phục vụ cây này».
- `maestro test <file> --exclude-tags=...` **không lọc** khi đích là một file, nên canary vẫn chạy trong bảng. Thay bằng vòng lặp theo từng file.

`docs/architecture/01` mục 6 xếp Maestro «sau Mốc 3, cần bản dựng trên máy». **Bác bỏ được:** Expo Go nạp bundle từ Metro và Maestro lái được ngay hôm nay, không cần EAS. Doc đó hiện chưa commit trên nhánh nào nên tôi không sửa; đây là chỗ ghi lại.

Job CI `mobile-native` đã viết. Nó chạy script, và khi runner không có máy ảo thì **cảnh báo to** chứ không trả xanh im lặng; đặt `vars.MOBILE_NATIVE_RUNNER` thì từ đó «không đo được» thành **đỏ**. Fail-closed sau khi có ai đó khai là có máy — cùng hình dạng với mặc định cờ trong ADR-0014. Nhắc lại: Actions chưa khởi động job nào kể từ 2026-08-29 (B0, billing), nên hôm nay đây vẫn là **kỷ luật**, không phải cưỡng chế.

---

## 7. Cái M0 KHÔNG chứng minh

- App **dùng được**. M0 chỉ làm nó thôi nói dối. Dữ liệu vẫn là fixture, vẫn mất khi tắt app, vẫn không có tài khoản.
- An toàn. `X-Actor-ID` vẫn là header client tự khai — B1, và ADR-0014 chưa được nhận.
- iOS. Không đo. Máy thật. Không đo. Ngoài đúng một AVD. Không đo.
- Mã VietQR quét được bằng app ngân hàng thật. Không cổng nào trong repo đo được, kể cả cổng native mới.
