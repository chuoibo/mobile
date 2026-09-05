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

## 5. Quyết định

Lead (13:0x, 05/09) giao cho Claude tự chọn và tự thực hiện, đánh giá bằng ảnh thật. Theo hợp đồng của direction round, khi người quyết định uỷ quyền thì **hướng được gán là hướng xây** (taste không phải cơ sở để tự re-roll): **«Nhật ký chuyến đi sau giờ làm»**, rendition bão hoà, mang đủ 6 raise. «Bàn nhậu nhìn từ trên» (PICK) và «Đông Hồ» (competitive) ghi lại làm phương án dự phòng nếu finish reviewer hoặc Lead bác thế giới này sau lát UI-1.

**Thế giới (OWN-WORLD, đọc được khi bỏ hết chữ):** một cuốn sổ chuyến đi. *Bìa* vải indigo đậm là bề mặt Persuade (Welcome, Login, OTP) và dải đầu trang của các màn kể chuyện; *trang giấy* trắng ngà sáng là bề mặt Operate; ba tông nghĩa là ba cuộn *washi* bão hoà (cam = rủ/hành động, teal = tiền, tím = AI) chỉ dán lên **vùng đang quan trọng**; trạng thái là *con dấu* (viền mực + chữ ngắn), không phải chip màu lẫn chữ; ảnh là *Instax* có viền và dòng nguồn; kèo là *đường route bút mực* liên tục; khung kẻ (keyline) in trước, màu đổ sau khi có dữ liệu; lưới 4pt, snap ô nguyên. Display face: **Bricolage Grotesque** (một face, grotesque «lắp ghép từ mảnh tìm được» đúng tinh thần sổ dán vé và băng dính; có trục wdth cho tem/nhãn; bộ chữ Việt đầy đủ); body giữ system. Wordmark: outline Baloo 2 ExtraBold nghiêng 9° chuyển SVG (chữ script nghiêng đậm, dấu hỏi là một phần hình).

## 6. Vòng chụp và những gì ảnh nói (UI-0 + vào cửa)

**Vòng 1 (light, dấu vân `652496a`, nền tảng chưa đổi màn):** nền giấy `#f7f3ec` thay kem đào; tiêu đề/số tiền Bricolage ExtraBold đọc rõ, dấu Việt đúng ở 21–28 sp; logo + wordmark vector ổn. **Lỗi thấy bằng mắt, không thấy bằng code:** chỉ báo tab tô cả cột 20 % cam (style inline ghi đè container trong suốt) → sửa; bóng FAB nặng → hạ elevation.

**Vòng 2 lần 1 (light, `fc434be`, Welcome/Login/OTP v2):** ảnh Welcome đầu đẹp và đúng thế giới (bìa indigo, wordmark dập nổi, washi coral chữ mực, con dấu CTA), nhưng **flow 01/02 đỏ ngay sau cú bấm đầu**: LogBox «Cannot read property 'forEach' of null» — `StampButton` ghi `transform: undefined`, Reanimated đổi thành `null`. tsc/npm test mù; chỉ emulator thấy. Sửa ở ba primitive. Cũng từ ảnh: hàng logo nhỏ trùng wordmark lớn (bỏ), khoảng trống chết giữa washi và đoạn giới thiệu (lấp bằng `RouteLine`, motif kế hoạch của sản phẩm).

**Vòng 2 lần 2 (light, `48754d0`):** đang chạy; kế tiếp dark + font 1.3, mini-bảng flow 22 để chụp Login/OTP thật, rồi finish reviewer (context mới).

**Sự cố emulator chung (14:47).** Trong lúc tôi chụp tablet thủ công (`pm clear` + `wm size 1600x2560` + deep link Metro), một lane khác đã bắt đầu bảng `--otp --ai` từ `wt-m10` trên cùng emulator-5554 (Metro 8095 của cây họ, từ ~14:44). Lệnh của tôi gần chắc chắn làm hỏng lượt đó (pm clear xoá phiên giữa flow; onboarding dev menu hiện lại). Ảnh «tablet» chụp ra là app của cây `wt-m10` (Welcome cũ) với sheet developer menu → không dùng. Bài học đã có trong memory («một emulator một lane»); từ đây tôi chỉ đụng emulator khi `pgrep -f 'mobile_native.sh'` của lane khác không còn, và ghi rõ trong PR.

## 7. Finish reviewer (context mới) — verdict `fix`, 8 mục, và lô sửa

Packet: yêu cầu gốc, 4 quyết định, contract, 12 ảnh phone (light `5eba3df`, dark/1.3 `48754d0`, OTP thật), mockup làm decision comp, craft-floor/android/operate, dòng «native không có detector». Reviewer đọc ảnh bằng PIL và lấy mẫu pixel.

| # | Mục vật chất | Sửa (commit `ff18023`) |
|---|---|---|
| 1 | CTA là pill coral phẳng, đúng cái THESIS từ chối | `StampButton` thành con dấu: không bóng, viền mực kép, mực coral có hạt giấy, nghiêng -1.5° trên bìa; Login «Gửi mã» cũng là con dấu |
| 2 | Bìa/giấy là màu phẳng, washi là hình chữ nhật xoay | Hai ô chất liệu sinh bằng Pillow (vải, giấy) qua `Grain`; `Washi` SVG mép xé, 0.9 |
| 3 | Khe giấy giữa status bar và dải bìa | `RudiScreen surface="cover"` bỏ paddingTop trong |
| 4 | Status bar sáng trên nền giấy ở màn cũ | `StatusBar` khai trong `RudiScreen` theo bề mặt |
| 5 | Tài chính 1.3 (cắt, gãy chữ, đè divider), chưa có ảnh ở head | Đã sửa ở 5eba3df/e4e5581 + hàng giao dịch paddingVertical; chụp lại dark/1.3 ở head |
| 6 | Giả dập nổi = bóng lệch cứng | Wordmark phẳng một lớp |
| 7 | Nút back giữ ô nhấn vuông | Back tròn 48 bằng `PressScale` |
| 8 | Phần ba giữa bìa chết | Route mực đặc, chặng «đang ở» theo trang pager |

Giữ nguyên theo «keep» của reviewer: wordmark nghiêng lớn, washi tagline, Bricolage, cấu trúc bìa/giấy. Chụp lại cùng viewport + tablet trên `ff18023` → verdict pass.

**Chụp lại lần 1 trên `ff18023` (15:09) đỏ cả 10 flow** — không phải harness: màn dev client «This development build encountered the following error: java.lang.IllegalArgumentException: Invalid number formatting character … com.horcrux.svg.PathParser.parse_number … PathView.setD». Mép xé bên trái của `Washi` được đảo chuỗi bằng split/reverse/join nên đường ra `… L 6 304.4 28 … L  Z` (hai số dính nhau, một `L` trống). react-native-svg parse `d` trong Java **lúc mount** → ném trong Fabric, không LogBox, app chết trước khung hình đầu. tsc mù (chuỗi), web export mù (trình duyệt vẽ đường cụt). Sửa ở `d14793f`: builder đường tách ra `src/rudi/ui/duong-svg.ts` (không React) + `tests/duong-svg.test.mjs` parse đúng cách Java parse (lệnh + arity, số thập phân thường); chạy trên thân cũ đỏ đúng chỗ, thân mới xanh. Chuỗi chụp lại chạy trên `d14793f`. Lần chụp trước đó bị ABORT đúng luật vì lane khác đang có bảng trên emulator chung — không đụng, chờ xong.

**Chụp lại trên `d14793f` (light XANH 19 ảnh · dark/1.3 rc=0 · OTP mini 5 ảnh · tablet) — tôi xem từng ảnh và đo pixel trước khi gửi verdict pass; bốn thứ chưa đạt → lô sửa 2 = `8ac1a16`:**

| Thấy gì (ảnh, số đo) | Nguyên nhân | Sửa |
|---|---|---|
| Login/OTP: vệt giấy `(247,243,236)` trên cùng với icon status bar sáng khó đọc; dải bìa bắt đầu dưới status bar | lớp giấy absolute phủ cả vùng inset của SafeAreaView; band nằm sau inset | `RudiScreen surface="cover"` bỏ edge top; `CoverBand underStatusBar` tự cộng `insets.top` |
| Bìa Welcome: stddev **0.0** từ y≈700 trở xuống, chỉ phần trên có vân (2.7 mức); trang giấy tương tự | `Image resizeMode="repeat"` Android raster một lần theo cỡ view lúc yêu cầu → bitmap ngắn hơn view (đọc `ReactImageView.kt` `TilePostprocessor`) | `Grain` = lưới Image thường, ô = PNG ở đúng pixel máy, ≤ 60 view (`ui/luoi-chat-lieu.ts` + test); opacity đo lại bằng composite: bìa 0.30 (stddev ≈ 8), giấy 0.45 (≈ 2) — 0.11/0.07 là màu phẳng |
| Scheme tối: chữ trên washi và trên con dấu là `(244,241,234)` trên coral `(251,105,62)` ≈ 2.4:1 | `colors.ink` đổi theo scheme nhưng coral không đổi | `mauSang.ink` tĩnh cho tagline, nhãn/viền/icon con dấu (5.41:1 cả hai scheme) |
| Route: bốn vòng tròn rỗng, không nghĩa; trên tablet S-curve kéo ngang 1600px như sợi dây | — | `RouteLine glyphs` (people · compass · receipt · images, một glyph mỗi trang), chặng đang ở = con dấu coral viền mực; route/pager giữ bề rộng 560/640 trên medium/expanded |
| OTP: vệt vuông tối đúng bounds nút back tròn trên nền có vân (zoom 4x) | PressScale animate `opacity` → lớp theo bounds hình chữ nhật | PressScale chỉ scale; mặt tròn là View con |

Ngoài ra: Tài chính dark/1.3 dòng ngân sách xuống hai dòng, không cắt (fix 5 đạt); status bar tối trên giấy ở Explore/Finance (fix 4 đạt ở màn giấy); tablet lần này bị sheet dev menu che (script chưa bấm «Continue» sau `pm clear`) → sửa script, chụp lại. Hai lần chuỗi chụp tự dừng đúng: một vì lane khác đang có bảng, một vì cổng 8095 còn Metro cũ (harness từ chối, đúng thiết kế) → chuỗi chờ 8095 rảnh trước mỗi stage.

**Ảnh cuối trên `8ac1a16`** (light XANH 19 ảnh · dark/1.3 rc=0 · OTP mini 5 ảnh · tablet qua mini-bảng Maestro ở 1600×2560@320: flow 00 đỏ vì tờ dev menu thắng cuộc đua ở lần mở lạnh trên cửa sổ vừa đổi cỡ, flow 01 xanh → có Welcome trang 2 + Login + Cá nhân hoá). Đo lại: vân bìa stddev ≈ 8 ở mọi độ cao (y 200 → 2300), vệt giấy trên status bar hết (dải bìa cùng màu bìa có vân), chữ trên washi/con dấu ở scheme tối là `(31,34,48)` = mực tối, nút back không còn vệt vuông (profile hàng/cột phẳng 35±1). Tự thấy nhưng **không sửa nữa** (đã hết hai vòng tự kiểm theo trần Impeccable, để verdict pass quyết): Login trên tablet — ô số + con dấu nằm trong cột hẹp giữa, hai nút viền và dòng chú thích dưới lại kéo hết bề rộng. Gửi verdict pass cho cùng reviewer với 14 ảnh trong `.impeccable/review/`.

## 8. Verdict pass 1 (cùng reviewer, ảnh `8ac1a16`) — 7/8 đạt, 1 partial, 2 hồi quy → lô sửa 3

| # | Verdict | Bằng chứng reviewer nêu |
|---|---|---|
| 1 con dấu | **partial** | viền mực `(203,89,59)`, nghiêng, một ngôn ngữ ask ở Welcome/Login/tablet — nhưng mặt coral phẳng: stddev 2.1/1.2/1.1 (ô giấy 0.42 không đo được) |
| 2 chất liệu | đạt | bìa stddev 8.1 ở cả (60,1050) và (60,1850), dark 8.3; giấy 2.3 «ở ngưỡng, không hạ thêm»; washi răng cưa hai đầu |
| 3 khe status bar | đạt | x=540 y110–175 là indigo có vân, không còn `(247,243,236)` |
| 4 status bar trên giấy | đạt | icon tối `(99,97,94)` trên giấy ở Explore/Finance |
| 5 Tài chính 1.3 | đạt (ở head) | ngân sách xuống hai dòng phải, huy hiệu một dòng; sửa lời nhận xét cũ: «đường qua hàng cuối» là thanh gesture, không phải lỗi |
| 6 dập nổi | đạt | một lớp phẳng ở ba ảnh |
| 7 nút back | đạt | ba góc ô vuông mean `(35,38,67)` stddev 8.0 = bìa xa `(36,39,69)` 8.3 |
| 8 route | đạt | route đặc, bốn glyph, con dấu coral chạy chặng 1→2; tablet cùng bố cục 640dp |

Hồi quy do lô 2: (a) tablet Login hai lưới (cột 560 cho ô số + con dấu, phần dưới kéo hết 1600); (b) tiêu đề TopBar Tài chính lệch trái (tâm ≈480/1080) vì ô phải giãn theo huy hiệu. Keep list nguyên vẹn. **Disposition: fix — một lô nữa cho ba mục; ship sau lô đó chỉ phủ các mục đã chấm + hai hồi quy trên phone light/dark-1.3 và tablet light.**

**Lô sửa 3** (`git log -1`): ô chất liệu thứ ba `muc-in.png` (script `scripts/sinh_chat_lieu_ui_v2.py`, seed cố định, ra đúng từng byte; test `tests/test_chat_lieu_tiles.py` đo stddev trên coral ở 0.26 phải nằm 6–12) cho con dấu; Login/OTP một cột 560 bọc cả trang; TopBar đo bề rộng tự nhiên hai bên và lấy max cho cả hai, huy hiệu trong TopBar rút «Demo» (accessibilityLabel đủ câu) vì ở 360dp/1.3 không thể có cả tiêu đề cân giữa lẫn nhãn dài. Chụp lại đủ bốn viewport → verdict pass 2.

**Chụp lại trên `f874b79`:** light XANH (con dấu stddev 8.6 trên coral ở cả Welcome/Login; tiêu đề Tài chính lệch −2.5 px so với tâm màn, huy hiệu «Demo» một dòng) · dark/1.3 rc=2 **hai lần** ở flow 10 (`scrollUntilVisible "Xác nhận cách chia"`), Tài chính dark/1.3 tiêu đề lệch −3 px · OTP 5 ảnh · tablet qua mini-bảng Maestro (sau khi `pm clear`, vì bảng OTP để lại phiên sống): Welcome trang 1 + Login một cột 560 cho cả trang.

**Điều tra flow 10 (không đoán):** `maestro hierarchy` sau khi tái hiện: Button «Xác nhận cách chia» `[42,2180][1038,2316]` trên màn 2400, enabled, clickable — nút **có** và **trọn trên màn**. Bốn biến thể cùng bước trên cùng màn dark/1.3: căn giữa 100 % → đỏ · căn giữa 80 % → đỏ · **không căn giữa → xanh** · vuốt ×3 + assertVisible → xanh. Kết luận: Maestro không căn giữa được phần tử cuối nội dung cuộn rồi báo «không thấy»; các lần xanh trước là may rủi của quãng vuốt. Sửa ở flow (bỏ `centerElement` đúng bước đó, giữ lời khai «thấy và bấm»), không sửa UI.

**Lô 3b (`d168b63`):** cũng từ lô 3, huy hiệu trong TopBar với nhãn khác mặc định («Nháp trên máy», «AI nháp») vẫn dài → ép tiêu đề; `DemoBadge compactLabel` áp cho mọi huy hiệu trong TopBar (hai màn dùng «Nháp»); nội dung ô phải sát mép phải khi ô trái rộng hơn. Chụp lại đủ bốn viewport trên `d168b63` → verdict pass 2. Ghi chú ngoài phạm vi: màn gán món (fixture, bố cục v1) cắt số tổng «1.28…» ở font 1.3 — để lát UI-5.

**Ảnh cuối trên `d168b63`, bốn bảng đều xanh** (light lần 1 đỏ flow 06 vì launcher khi máy bận — bẫy đã ghi, chạy lại xanh 19 ảnh; dark/1.3 xanh 19 ảnh kể cả flow 10; OTP 5; tablet 4 gồm Welcome trang 1). Đo: con dấu stddev 8.58 trên coral (Welcome, Login), vải bìa 8.14 ở y=1800, dải bìa dưới status bar `(36,39,69)`, tiêu đề Tài chính lệch −2.5 px (light) / −3 px (dark 1.3). 15 ảnh trong `.impeccable/review/` → gửi verdict pass 2 cho cùng reviewer.

## 9. Verdict pass 2 (ảnh `d168b63`) — **ship** trong phạm vi đã chấm

| Mục | Verdict | Bằng chứng reviewer nêu |
|---|---|---|
| 1 mặt con dấu | đạt | stddev 8.5/7.0/7.4 trong coral ở Welcome, Login, dark 1.3, tablet Login, tablet Welcome (từ 2.1 ở pass 1) |
| 2 tablet Login hai lưới | đạt | mọi phần tử dưới dải bìa nằm trong x≈240–1357/1600, một cột |
| 3 tiêu đề TopBar | đạt | tâm mực 537.5 (light) / 537.0 (dark 1.3) so với 540; «Demo» một dòng, không cắt; adaptation được chấp nhận |
| 7 mục pass 1 | giữ | vân bìa 8.1 ở hai độ cao; khe status bar hết; icon tối trên giấy; Tài chính 1.3; wordmark một lớp; nút back không vệt; route + con dấu trang 1→2 (tablet trang 1 nay có ảnh) |

Không hồi quy trong 15 ảnh; keep list nguyên vẹn. **Disposition: ship — phủ tám mục vật chất và hai hồi quy pass 1 trên phone light 1.0, phone dark 1.3, tablet light tại d168b63; không phải phán quyết về bố cục các màn chưa redesign hay các viewport ngoài packet** (tablet dark, iOS, máy thật; số tổng màn gán món cắt ở 1.3 → UI-5).
