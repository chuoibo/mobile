# ADR-0020 — Hệ hình ảnh v2: thẩm quyền thị giác phân tầng, một display face tự host, bốn bậc chuyển động

- **Trạng thái:** 🟡 **ĐỀ XUẤT** 2026-09-05 — chờ Lead đánh ĐÃ CHẤP NHẬN. Lát UI-1 trở đi không merge trước khi dòng này đổi; UI-0 (nền tảng) có thể merge vì không đổi màn nào.
- **Quyết định bởi:** Lead (bốn quyết định chốt trong phiên 2026-09-05, ghi lại ở mục 2).
- **Hiện thực:** chiến dịch UI v2, 9 PR xếp chồng bắt đầu từ `claude/p0-w-ui0-nen-tang-design-system`; kế hoạch ở `~/.claude/plans/t-i-nh-n-c-1-squishy-shell.md`, bản sao đưa vào `docs/architecture/03-ui-v2.md` ở PR UI-1.
- **Thay đổi hệ hình ảnh và hai quyết định đã ghi trong DESIGN.md** (system stack; «bản ship là ground truth»), không đổi route, API, domain hay ba luật tiền.

## 1. Bối cảnh

Critique Impeccable 2026-09-04 (`.impeccable/critique/2026-09-04T17-34-40Z__apps-mobile.md`, chép ra `docs/claude/2026-09-05/bao-cao-cai-thien-ui-rudi.md`) chấm 22/40 heuristic và 6/10 độ đặc trưng: sau đăng nhập mọi màn là một công thức lặp (nền kem, thẻ trắng bo tròn, CTA cam), không hình ảnh ở bản live, không ngôn ngữ chuyển động (`react-native-reanimated` cài mà 0 import), màn danh sách trống 70–90 % khi ít dữ liệu, và bánh răng dev client nổi trên mọi ảnh chụp kể cả màn tiền. Đối chiếu 8 mockup với 12 ảnh emulator lượt M10 xác nhận cả năm điểm.

DESIGN.md hiện ghi hai quyết định mà việc sửa phải có chỗ ghi lại: (a) «System stack, không webfont» là quyết định có chủ ý; (b) «Bản ship là ground truth của file này, không phải mockup». Charter cấm hợp thức hoá hậu nghiệm, nên ADR này mở trước khi lát UI-1 đổi màn đầu tiên.

## 2. Quyết định

### 2.1 Thẩm quyền thị giác phân ba tầng
1. **Sự thật sản phẩm** = ADR + hành vi live (ADR-0015 không đường thanh toán; ADR-0016 phạm vi v1; ba luật tiền). Không hình ảnh nào được nói ngược.
2. **Ngôi sao dẫn đường thị giác** = hợp đồng hướng đi v2 trong `apps/mobile/app/_layout.tsx` (THESIS/OWN-WORLD/STORY/FIRST VIEWPORT/FORM/FINISH, seed `c8e88116`) và DESIGN.md v2 do documenter đo lại từ bản ship sau mỗi lát. Bản ship vẫn là ground truth của *số đo*; hợp đồng là ground truth của *ý định*.
3. **Mockup 21 màn** = decision comp và tham chiếu critique, có nhãn stale khi lệch. Không chép số, tên, QR hay ảnh người thật từ PNG.

### 2.2 Hướng hình ảnh chọn bằng direction round, không ghim trước
Chạy `concept-seed --scope direction --mode persuade` trên danh sách 7 hướng cố định trước roll (doc `docs/claude/2026-09-05/ui-v2-direction-round.md`), trình một hướng đã nâng + challenger + lối ra chuẩn thể loại lên trang quyết định; Lead chọn. Hướng được chọn (Lead uỷ quyền cho Claude 05/09, xây hướng được gán): **«Nhật ký chuyến đi sau giờ làm»** — bìa vải indigo cho Persuade, trang giấy sáng cho Operate, washi bão hoà cam/teal/tím chỉ dán lên vùng đang quan trọng, con dấu là trạng thái, Instax có dòng nguồn cho ảnh, route bút mực cho kèo, khung kẻ in trước màu đổ sau. Display face **Bricolage Grotesque** (OFL), wordmark SVG từ outline Baloo 2 ExtraBold nghiêng.

Cam kết thương hiệu **không đổi** dù hướng nào: wordmark «Rủ Đi» script nghiêng có dấu hỏi là một phần hình; logo squircle gradient `#fc7b37 → #e75262`; ba tông mang nghĩa (cam = hành động, teal = tiền, tím = AI), một tông dẫn mỗi màn; giọng «Rủ Đi thôi!».

### 2.3 Một display face tự host, body giữ system, wordmark vector
- **Một** face display có bộ chữ Việt đầy đủ, chọn từ thế giới của hướng (không theo liên tưởng thể loại, không nằm trong danh sách mặc định của Impeccable), nhúng bằng plugin `expo-font` lúc build, file `.ttf` pin vào `.repo-guard-allowlist.json` với giấy phép OFL và nguồn. Chỉ dùng cho tiêu đề, số tiền lớn và thương hiệu; body, nhãn, ô nhập, chip vẫn system (Roboto/SF) để dấu tiếng Việt và cỡ chữ hệ thống chắc chắn.
- **Cổng chọn face**: render «Rủ Đi thôi! ế ự ỡ ạ ổ ầ ẫ ỹ Đ đ» ở 12/17/28/40 sp trên emulator ở font 1.0 và 1.3; một dấu đặt sai là loại. Face được chọn ghi ở DESIGN.md v2 kèm ảnh chứng minh.
- **Wordmark** là SVG (`react-native-svg`), không còn `fontStyle: "italic"` giả wordmark. Thêm `react-native-svg` và `expo-font` → rebuild dev client một lần (đã dự trong UI-0).

### 2.4 Bốn bậc chuyển động thay «≤ 220 ms»
`instant 100 · standard 200 · shared 300 · celebrate 550` (ms) trong `packages/shared/tokens.json`, `src/rudi/motion.ts` đọc thật. Trần: state ≤ 240 ms; `celebrate` ≤ 650 ms và **một lần mỗi sự kiện**, chỉ cho ba khoảnh khắc (chốt kèo, xong bill, mở huy hiệu). Reduce Motion đưa mọi bậc trừ `instant` về 0. **Tiền không animate trước khi domain state hợp lệ**; không ambient loop vô hạn; transform/opacity là đường chính.

### 2.5 Hình ảnh: minh hoạ vector trước, ảnh thật có giấy phép sau
Trước M12 (ADR-0017), Khám phá/Địa điểm dùng minh hoạ vector theo danh mục vẽ bằng chất liệu của hướng; `MediaSlot` giữ khe ảnh + dòng tác giả/giấy phép để M12 đổ ảnh thật vào không đổi bố cục. Không ảnh stock cho địa điểm thật; hero Welcome cũng bỏ ảnh stock `demoAssets.friends`. Avatar là ảnh người dùng tự tải (M8) hoặc chữ cái đầu; không ảnh người thật trong Git.

### 2.6 Bề mặt chụp phải sạch
Nút nổi «Tools» của `expo-dev-menu` tắt mặc định trong dev build (`plugins/tat-nut-noi-dev-menu.js`, meta-data `EXDevMenuShowFloatingActionButton=false`); dev menu vẫn mở bằng `adb shell input keyevent 82` hoặc lắc máy. Mọi ảnh bàn giao chụp trên bản dựng có plugin này.

### 2.7 Quy trình mỗi lát
Craft floor + android + operate nạp trước khi sửa UI · build đủ → một vòng chụp (light/1.0, dark/1.3, tablet bằng `wm size`) → sửa một lô → tối đa một vòng nữa · `man-ra-html` + `imp detect` + canary (detector mù với `.tsx`) · finish reviewer context mới, xử theo bốn từ `recapture/rebuild/fix/ship` · documenter sau UI-1 và UI-8 · critique so trend (mục tiêu ≥ 32/40, đặc trưng ≥ 8/10).

## 3. Hệ quả
- `DESIGN.md` §Chữ và §Chuyển động được viết lại bởi documenter, không sửa tay; bảng tương phản sinh bằng script để `test_contrast_floor` xanh; control mới phải có dòng trong `interactive_boundaries()` và test đọc thêm `src/rudi/ui/**`.
- Màu mới chỉ qua `tokens.json` → `guest.css` → DESIGN.md cùng PR; `rudi-khong-hex` giữ theme.ts là file duy nhất viết hex.
- Nền tảng v2 nằm ở `src/rudi/ui/` (một file một primitive) và `src/rudi/motion.ts`, `src/rudi/adaptive.ts`; `ui.tsx` cũ giữ chữ ký tới UI-8 để M11–M15 merge không vỡ.
- Flow Maestro sửa cùng lát khi đổi câu chữ; **giữ tên `takeScreenshot`** vì bảng đối chiếu ghim.
- Dev client rebuild sau UI-0; leader cài lại APK nếu test máy thật.

## 4. Cái này KHÔNG chứng minh
- Một hệ hình ảnh đẹp hơn không chứng minh sản phẩm đúng hướng (ADR-0006 vẫn đúng: chưa có bằng chứng hành vi).
- Điểm critique tăng là hai subagent chấm theo heuristic, không phải người dùng thật.
- Ảnh emulator chứng minh render ở thiết bị/scheme/font đã chụp, không chứng minh iOS hay máy thật.

## 5. Phương án đã bác

| Phương án | Vì sao không |
|---|---|
| Pilot 4 lát rồi dừng chờ duyệt | Lead chọn đổi đồng loạt 21 màn; cổng giữa các lát là finish reviewer, không phải cổng duyệt pilot |
| Ghim hướng «nhật ký chuyến đi» của báo cáo | Roll và challenger là thứ giữ mọi lượt không hội tụ về mặc định thể loại; hướng của báo cáo chỉ là một ứng viên |
| Bám mockup 21 màn (chuẩn thể loại) | Là lối ra luôn có trên trang quyết định, không phải khuyến nghị; mockup là comp ChatGPT khá generic |
| Giữ 100 % system font | Display voice là system sans thì thế giới riêng không có tiếng nói (craft floor); body vẫn system nên dấu tiếng Việt không rủi ro |
| `polish` trên hệ hiện tại | Concept lặp là vấn đề; polish sẽ là redesign trá hình |
| Ảnh stock tạm cho địa điểm | DESIGN.md 376: ảnh stock cho địa điểm thật là bịa; M12 mới có ảnh có giấy phép |
