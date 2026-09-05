# UI v2 — Direction round (Impeccable, Flow A «Redesign», code-led)

Nhánh: `claude/p0-w-ui0-nen-tang-design-system` (trên head #562 `078d9c3`). Tham chiếu: `reference/new-work.md §3`, plan `~/.claude/plans/t-i-nh-n-c-1-squishy-shell.md`. Danh sách dưới đây được **cố định trước khi roll**; dice chọn theo chỉ số của danh sách này.

## 1. Khung

- **Cơ chế độc nhất (một câu):** một trợ lý sống trong nhóm và giữ ngữ cảnh xuyên cả buổi: cùng một AI gợi ý quán là AI đọc hoá đơn quán đó và biết ai ngồi ở đó; sản phẩm nói phần của mỗi người rồi dừng.
- **Cảnh thật:** hội 4–10 bạn trẻ Việt, buổi tối, đang đứng dậy ra về sau bữa ăn, một tay cầm điện thoại, 4G, ánh đèn quán vàng; kế hoạch được chốt trong nhóm chat ồn ào mười ý kiến; cuối tuần Đà Lạt, quán nướng, cà phê view.
- **Cultural home:** văn hoá đi chơi của giới trẻ đô thị Việt: quán ốc/nướng lề đường, cà phê sân vườn, chợ đêm, phượt xe máy, «check-in», bill giấy nhiệt, chuyển khoản rồi screenshot «đã ck nhé», nhóm chat Zalo/Messenger, sticker.
- **Welcome phải chứng minh:** đây là app của *buổi đi chơi của hội mình* (không phải app tài chính), ấm và có năng lượng «rủ»; một hành động duy nhất: «Rủ Đi thôi!».
- **Rut, để ngoài danh sách:** (a) thứ thể loại luôn ship: ảnh hoàng hôn full-bleed + thẻ trắng bo tròn + CTA pill cam gradient (chính là mockup và bản hiện tại); (b) đối nghịch dự đoán được: fintech tối + một màu neon; (c) đọc nghĩa đen của brief «nhật ký chuyến đi giấy kem + tem» của báo cáo → chỉ tiêu một ứng viên (số 6).

## 2. Bảy chất liệu người dùng thuộc lòng (≥ 3 họ vật liệu)

| # | Chất liệu | Họ | Vì sao vang và chở được cơ chế |
|---|---|---|---|
| 1 | **Bàn ăn nhìn từ trên xuống** — đĩa tròn, bát chung, ly, nhiều đôi đũa | nghi thức | Bữa Việt là bữa chung; «ai ăn gì» chính là đĩa nào trước mặt ai. Chở được gán món, chia bill, nhóm. |
| 2 | **Biển hiệu vẽ tay + đèn dây quán đêm** — sans nén đậm có dấu, hai màu, đổ bóng, bảng giá phấn | đồ hoạ + nơi chốn | Năng lượng «đi chơi tối»; chữ Việt có dấu là chất liệu hình. Chở được khám phá, CTA, trạng thái sáng/tắt. |
| 3 | **Bản đồ du lịch vẽ tay gấp ba** — route, pin số, chú giải, landmark | hệ đồ hoạ | Cuối tuần Đà Lạt bắt đầu bằng tấm bản đồ; đường route là «đường đi» của hội. Chở được kèo, timeline, check-in. |
| 4 | **Hoá đơn giấy nhiệt** — cột món/giá tabular, mép răng cưa, mực nhạt, dấu mộc | giấy-vật | Vật đầu tiên mọi người cầm khi chia tiền; trung thực từng đồng. Chở được bill, sổ, quyết toán. |
| 5 | **Vé xe/vé tàu + tem** — perforation, số ghế, «ĐÃ SOÁT» | giấy-vật | Trạng thái là con dấu, không phải chữ inline. Chở được «Đã tới», «Đã trả», «Đã phát». |
| 6 | **Tường Instax + sổ tay dán washi** | giấy-vật / nghi thức | Payoff kỷ niệm; đọc nghĩa đen của brief nên chỉ một ứng viên. |
| 7 | **Nhóm chat Zalo/Messenger** — bubble, sticker, poll, mention | màn hình | Nơi mọi kèo được chốt; ngữ pháp người dùng đọc mỗi ngày. Rủi ro sao chép công cụ đang có. |

## 3. Bảy hướng hoàn chỉnh, xếp theo resonance (chỉ số cho dice)

1. **«Bàn nhậu nhìn từ trên»** (từ #1) — Thế giới: nền ink ấm đậm như mặt bàn gỗ/khăn trải; người = chỗ ngồi quanh bàn; món = đĩa tròn màu no; ba tông nghĩa là ba loại ánh đèn trên bàn (cam = rủ/hành động, teal = tiền, tím = AI); số tiền là tờ hoá đơn đặt trên bàn; display tròn đậm. Welcome: bàn trống dần đầy — đĩa, ly hạ xuống theo nhịp, wordmark là tấm menu dựng, CTA «Rủ Đi thôi!» là đĩa lớn nhất. Signature: gán món = kéo đĩa tới avatar quanh bàn. Rủi ro: sân khấu hoá; màn Operate (tài chính, hồ sơ) phải kìm bằng «bàn đã dọn».
2. **«Biển hiệu đêm»** (từ #2) — Thế giới: nền dusk indigo/ink làm nền chung (drenched), display là sans nén đậm kiểu biển hiệu vẽ tay đủ dấu, ba tông nghĩa là ba loại đèn (neon cam, ống teal, tím) — một biển hiệu sáng mỗi màn; thẻ = bảng giá phấn; kẻ = ống neon mảnh. Welcome: biển hiệu tối bật sáng từng chữ «Rủ Đi thôi!» (celebrate duy nhất), dãy đèn dây bên dưới. Rủi ro: tối cho màn tiền đọc thành fintech; phải chứng minh ledger đọc được trên nền đêm, hoặc scheme sáng của cùng thế giới = «ban ngày trước giờ mở».
3. **«Bản đồ gấp cuối tuần»** (từ #3) — Thế giới: nền giấy bản đồ sáng lạnh nhẹ (không kem vàng), route cam dày liên tục xuyên app, pin số, chú giải; teal = vùng nước/tiền; tím = vùng AI gạch chéo; nhãn condensed địa lý + display cho tên điểm. Welcome: bản đồ gấp mở từng nếp, route vẽ dần tới CTA. Signature: kèo = route vẽ dần, check-in = pin cắm. Rủi ro: không có map SDK → bản đồ là ẩn dụ đồ hoạ, tuyệt đối không giả bản đồ thật.
4. **«Hoá đơn nhiệt»** (từ #4) — Thế giới: giấy nhiệt trắng ấm, mực đen/xám mờ, cột số tabular, răng cưa, ba tông là ba màu mực **dấu mộc** (cam/teal/tím) đóng lên trạng thái; display khác mono. Welcome: tờ hoá đơn in dần «Tối nay · 6 người · ai trả gì» rồi «Rủ Đi thôi!». Rủi ro: lạnh, gần receipt-app; Persuade yếu.
5. **«Vé & tem»** (từ #5) — Thế giới: vé perforated, tem trạng thái, số ghế, giấy dày; cam = vé rủ, teal = vé tiền, tím = vé AI. Welcome: xé vé. Rủi ro: cùng họ giấy với #4/#6; hình vé lặp thành template.
6. **«Nhật ký chuyến đi Việt Nam sau giờ làm»** (từ #6; đọc nghĩa đen của báo cáo) — Thế giới: giấy kem, washi, Instax, viết tay, coral dusk/teal/violet. Welcome: sổ mở, ảnh dán. Rủi ro: cream + paper là rendition đã tiêu (new-work §4); đặc trưng khó vượt.
7. **«Bảng tin nhóm»** (từ #7) — Thế giới: chat-first, mọi thứ là tin/thẻ trong luồng, sticker minh hoạ. Welcome: một cuộc chat rủ nhau chạy dần. Rủi ro: sao chép Zalo; gần rut nhóm chat.

Mọi hướng đều khả thi code-led: minh hoạ vector SVG, gradient, font display tự host; không bịa số, không ảnh stock, không QR.

## 4. Roll và fuse (điền sau khi chạy `imp concept-seed --scope direction --mode persuade`)

`imp concept-seed --scope direction --mode persuade` → **seed key `c8e88116`, ASSIGNED INDEX 6** = «Nhật ký chuyến đi Việt Nam sau giờ làm». Xúc xắc rơi đúng vào ứng viên đọc nghĩa đen của báo cáo. Không có cơ sở *sự thật* để tự re-roll (hướng chở được sản phẩm), nên trình bày nó — nhưng theo new-work §4, rendition «giấy kem + chữ viết tay» là bản đã tiêu; hướng được trình bày ở **rendition bão hoà của chính thế giới sổ du lịch**: bìa vải indigo đậm cho lúc rủ (Welcome/Login), trang giấy sáng cho lúc làm, washi bão hoà cam/teal/tím là ba tông nghĩa, con dấu mực là trạng thái, Instax là kỷ niệm, bút mực vẽ route.

### Fuse và verdict (hai trục: nhận diện của người dùng · độ rõ của sản phẩm)

| Challenger (catalog) | Fuse với Rủ Đi | Nhận diện | Rõ | Verdict | Giữ lại / raise cho hướng được gán |
|---|---|---|---|---|---|
| Star atlas (navy, sao theo cấp, đỏ đèn pin) | Địa điểm = sao, cỡ sao = độ hợp gu, chòm sao = route | thua (bản đồ sao không phải đời sống hội bạn) | giữ một phần (thứ bậc bằng cỡ trên thang cố định) | **declined** | Xếp hạng AI bằng kích cỡ/độ đậm trên thang cố định, **không in % giả** |
| Ukiyo-e block registration → fuse thành **tranh khắc gỗ Đông Hồ** | Mỗi màn in từng lớp: khung đen trước, cam/teal/tím đổ vào theo lẫy; chưa tải = chỉ khung | giữ một phần (di sản ai cũng biết, nhưng không đọc mỗi ngày) | **giữ** (trạng thái = lớp mực; khung không dời) | **competitive** | Trạng thái là lớp mực: khung in trước (skeleton), màu đổ vào khi có dữ liệu; **khung không bao giờ dời** |
| Glazier colour-field partition | Ô kính = vùng; ô đang quan trọng mới có màu; disabled = mờ sương | thua | giữ một phần | **declined** | Màu chỉ đổ vào **vùng đang quan trọng**: một tông dẫn sáng đúng một vùng mỗi màn |
| Azulejo station hall | Gạch cobalt/trắng — trái cam kết ba tông | thua | thua (đơn sắc phá nghĩa màu) | **declined** | Bố cục **snap theo ô nguyên** trên lưới 4pt; album/collage không ô lẻ |
| Variable type specimen | Wordmark/display cỡ khổng lồ, thứ bậc bằng cỡ | thua | giữ một phần | **declined** | Thứ bậc bằng **tương phản cỡ**, không ornament; hero Welcome để wordmark rất lớn |
| CRT oscilloscope | Tiền như trace trên lưới 10 vạch | thua | thua | **declined** | **Một lưới đo** xuyên app: khoảng cách/chiều cao hàng cùng nhịp |

Không challenger nào thắng cả hai trục → hướng được gán vẫn là ứng viên xây, đã nâng bằng 6 raise có tên. Thẻ **IMPECCABLE’S PICK** = ứng viên số 1 của tôi («Bàn nhậu nhìn từ trên»), không chiếm vị trí dẫn. Lối ra chuẩn thể loại (mockup chơi thẳng) luôn có trên trang, không được tôi khuyên.

### Trang quyết định
Payload: `.impeccable/decision/ui-v2-direction.json` (trong worktree). Kết quả điền ở §5 sau khi người dùng chọn.

**Nhật ký trang quyết định.** Server đầu (`http://127.0.0.1:44661/`, key `9b142e1b`) mở lúc 11:0x, trình duyệt Windows đã mở qua `cmd.exe start`; sau ~30 phút không có câu trả lời thì `--wait` báo «question server is gone» (rc=2, lỗi server, không phải người dùng từ chối). Khởi động lại đúng payload: `http://127.0.0.1:44817/`, key `0fa42bd7`, mở lại trình duyệt, tiếp tục chờ. Trong lúc chờ chỉ làm phần không phụ thuộc hướng (adaptive, motion, skeleton, empty/error, sheet, money, avatar, stepper, media slot, plugin FAB, dep svg/font, rebuild dev client).

Server thứ hai (`44817`, key `0fa42bd7`) cũng «gone» sau ~10 phút không có người mở. Kết luận vận hành: daemon `serve-question` không sống lâu khi không có phiên trình duyệt; chỉ khởi động khi Lead đang ngồi trước máy, và Lead chọn trong vài phút. Cho tới lúc đó, UI-0 chỉ làm phần không phụ thuộc hướng và dựng/cài dev client mới.

**P0 (bánh răng dev menu) — bằng chứng.** Dev client dựng lại từ nhánh này (gradle 8m34s, x86_64, APK 101 MB, sha256 `89014b3d…`) cài lên emulator-5554; lượt bảng mặc định lượt 12:34:55 ngày 05/09 (dấu vân `cb58977`) chụp `00-welcome.png` **không còn nút nổi «Tools»** ở góc phải trên, trong khi mọi ảnh của các lượt M8/M10 (`~/rudi-anh/20260905-M*/`) đều có. Manifest sinh bởi prebuild mang `EXDevMenuShowFloatingActionButton=false` (dòng 18 `android/app/src/main/AndroidManifest.xml`). Dev menu vẫn mở bằng `adb shell input keyevent 82`.
APK kiểm bằng `zipfile`: ABI chỉ `x86_64`; dex có `com/horcrux/svg/RNSVG` (10), `expo/modules/font/FontLoaderModule` (17), `com/swmansion/worklets` (34); `lib/x86_64/libworklets.so` + `libreanimated.so`. Tức là wordmark/minh hoạ SVG, display face runtime và Reanimated đều có native trên máy.
Bảng mặc định trên bản dựng này: `XANH: bảng qua (1 lượt), NEO 2b cắn, canary đỏ đúng thiết kế` (rc=0, 19 ảnh, 0 FAILED); thư mục bàn giao tạm `~/rudi-anh/20260905-UI0/`.
