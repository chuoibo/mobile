/* Sáu tính năng xã hội, đi tới bằng NGÓN TAY chứ không bằng thanh địa chỉ.
 *
 * F37 thước phim AI · F40 thả tim · F41 bình luận · F42 bốn mức người đọc.
 * (F43 bản đồ nhóm và F44 bản đồ nhiệt đã có `duong-vao-ban-do-nhom.test.mjs`
 * gác đúng kiểu này; không chép lại ở đây.)
 *
 * ## Vì sao cần file này khi bốn màn kia đã có test
 *
 * Bốn tính năng trên đã có test, và mọi test đó đều đi vào bằng một cửa mà
 * người dùng không có:
 *
 *   - `tuong.test.mjs` và `ten-dia-diem-album.test.mjs` gọi thẳng
 *     `renderToStaticMarkup(<Tuong …/>)` / `<MotAlbum …/>`. Chúng chứng minh
 *     component vẽ đúng. Không có màn nào, không có nút nào, không có shell.
 *   - `tim-binh-luan.test.mjs` chạy Chrome thật, nhưng vào bằng
 *     `#vao=ky-niem`. `tools/tab-snapshots.mjs` cũng vậy: `vao=album`,
 *     `vao=ky-niem`, `chuyen=<uuid>`.
 *
 * Header của `duong-vao-ban-do-nhom.test.mjs` đã đặt tên cho đúng khoảng cách
 * này — "reachable by URL" khác "reachable by a control a person can find" —
 * và đây là lần thứ hai nó đáng được đo. Một fragment là thứ chỉ máy quét gõ
 * được. Nếu hàng `[+]` mất `route`, hoặc `onPress` của nó bị nối vào `() => {}`,
 * thì MỌI test kể trên vẫn xanh: chúng không bao giờ đi qua cái nút ấy.
 *
 * ## Cạnh mà mỗi ca này gác — và chỉ đúng cạnh đó
 *
 *   F37  [+] → "Album chuyến đi" → bấm thẻ một chuyến → "Dựng thước phim"
 *        GET /contexts/{id}/albums · /albums/{outing} · /albums/{outing}/reel
 *   F40  [+] → "Kỷ niệm nhóm" → bấm trái tim trên thẻ ảnh
 *        POST/DELETE /contexts/{id}/memories/{mid}/reactions
 *   F41  cùng tường → bấm nút bình luận → ô soạn hiện ra
 *        GET/POST /contexts/{id}/memories/{mid}/comments
 *   F42  tab Cá nhân → "Viết lên tường" → bấm "Một nhóm"
 *        POST /posts (audience), GET /people/{id}/posts
 *
 * ## Cái file này KHÔNG chứng minh
 *
 * Không chứng minh máy chủ trả đúng (stub trả lời, không phải Postgres); không
 * chứng minh bốn mức người đọc có hậu quả THẬT ở phía đọc — đó là điều
 * qa3-tt-0035 đã ghi là còn thiếu và nó nằm ở tầng server, không ở cạnh bấm;
 * không chứng minh màn nào dễ đọc (việc của detector); và không chứng minh
 * native — xem ghi chú cuối header.
 *
 * ## Đối chứng, vì một phép đo không tự biết mình hỏng
 *
 * Ca 1 là ĐỐI CHỨNG DƯƠNG và nó chạy trước mọi ca khác: "Tạo khoản chi" là
 * tính năng cả đội biết chắc bấm tới được (đường hero). Nếu cách đo ở đây
 * (mở tab → bấm [+] → bấm một hàng) không xếp nổi nó là TỚI ĐƯỢC thì thước
 * đo hỏng, và bốn số xanh phía dưới không có nghĩa gì.
 *
 * Ca 2 là ĐỐI CHỨNG ÂM: mở `[+]` rồi KHÔNG bấm hàng nào thì không màn nào tới.
 * Nếu thiếu nó, mọi assert dưới đây có thể được thoả mãn bởi chữ nằm sẵn trong
 * chính tấm menu — menu in cả nhãn lẫn gợi ý của từng hàng, nên "Album chuyến
 * đi" và "thước phim AI" CÓ MẶT trên màn ngay khi menu mở ra mà chưa đi đâu cả.
 *
 * ## Đo trên cái gì
 *
 * `expo export` web + Chrome headless, như mọi cổng render khác trong thư mục
 * này. KHÔNG phải native: 2026-09-01 lúc ~01:0x, `adb devices` treo vô hạn
 * (server dựng lại, cả cổng 5038 riêng cũng treo) trong khi emulator `rudi`
 * vẫn báo `virtual device is running` qua console 5554. Đó là hạ tầng của
 * devops, đã báo. Nên phạm vi của file này là react-native-web, và cái nó
 * không với tới được nói thẳng ở đây chứ không làm tròn lên.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { API_BASE, NGUOI, installTabStubs, taoFixtures } from "../tools/tab-snapshots.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** Own page file: two suites writing one filename race when `--test` runs
 *  files concurrently, and the loser serves the other's stub. */
const TRANG = "__test-duong-vao-xa-hoi.html";

/** `ThanhTab`'s centre control, by its `accessibilityLabel` when shut. */
const NUT_TAO = "Tạo mới";

/** Hàng trong `MenuTao`, nhận diện bằng ĐẦU của `aria-label`.
 *
 *  Nhãn thật là `${label}. ${hint}` ghép trong `MenuTao.tsx`. Ghim cả câu vào
 *  đây thì sửa một chữ trong `hint` — thuần văn phong — làm đỏ một ca điều
 *  hướng, và cái đỏ đó dạy người ta rằng file này hay kêu oan. Ghim phần
 *  `label` thôi: đó là phần mang danh tính của hàng. */
const HANG_ALBUM = "Album chuyến đi.";
const HANG_KY_NIEM = "Kỷ niệm nhóm.";
const HANG_KHOAN_CHI = "Tạo khoản chi.";

/** Chữ chỉ có ở đáy mỗi đường, không có ở tab xuất phát và không có trên menu.
 *
 *  Mỗi cái đều là chữ của TRẠNG THÁI ĐÃ TẢI XONG, không phải tiêu đề: `Bia`
 *  và `Khung` vẽ tiêu đề ở cả nhánh từ chối, nên một tiêu đề sẽ cho qua đúng
 *  cái hỏng đáng bắt. Cùng lý do đã viết trong `tools/tab-snapshots.mjs`. */
const CHU_KE_ALBUM = "Nhóm đã có";
const CHU_MOT_ALBUM = "Tên album là tên chuyến";
const CHU_THUOC_PHIM = "AI viết câu này";
const CHU_TUONG_KY_NIEM = "Đã đi cùng nhau";

/** `ChupBill`'s shutter, the bottom of the control path. An `aria-label`
 *  rather than visible words: the button draws a glyph. */
const NHAN_CHUP_BILL = "Chụp bill";

/** Nút mở ô soạn bài trên tường Cá nhân, và bốn mức người đọc dưới nó. */
const NUT_VIET_TUONG = "Viết lên tường";
const MUC_MOT_NHOM = "Một nhóm.";
const BON_MUC = ["Chỉ mình tôi.", "Bạn bè.", "Một nhóm.", "Công khai."];

/** Hậu quả nhìn thấy được của việc chọn "Một nhóm", ở cả hai ngả.
 *
 *  Hai câu vì `Tuong` rẽ theo `nhom.length`, và ca dưới không được quyền giả
 *  định `CaNhan` đưa xuống bao nhiêu nhóm — nó khẳng định CÓ hậu quả, và in ra
 *  hậu quả nào đã xảy ra. */
const HAU_QUA_MOT_NHOM = ["Nhóm nào được đọc", "Bạn chưa có nhóm nào để chọn"];

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");

/** Chữ đang được VẼ, khoảng trắng gộp lại.
 *
 *  `innerText` chứ không `textContent`: thẻ ảnh mang tên chỗ trong `aria-label`
 *  mà không ai đọc, và tính cả những cái đó thì mọi đối chứng âm ở dưới đều
 *  thành nói dối. */
function chuTrenMan() {
  return document.body.innerText.replace(/\s+/g, " ");
}

/** Mọi `aria-label` bắt đầu bằng `dau`, theo thứ tự trong DOM.
 *
 *  Trả cả danh sách chứ không trả cái đầu: người gọi cần phân biệt "không có
 *  hàng nào" với "có ba hàng trùng tên", và hai cái đó cần hai lời nhắn khác
 *  nhau. `clickLabel` từ chối bấm khi trùng, nên biết trước là biết sớm. */
function nhanTheoDau(dau) {
  return [...document.querySelectorAll("[aria-label]")]
    .map((e) => e.getAttribute("aria-label"))
    .filter((n) => n.startsWith(dau));
}

/** Vị trí một control theo `aria-label`, dạng chuỗi, hoặc null.
 *
 *  Chuỗi chứ không phải hộp: chỗ duy nhất dùng nó chỉ hỏi "đã đứng yên chưa",
 *  và đó là một phép `===`. */
function viTriTheoNhan(nhan) {
  const els = [...document.querySelectorAll("[aria-label]")].filter(
    (e) => e.getAttribute("aria-label") === nhan,
  );
  if (els.length !== 1) return null;
  const r = els[0].getBoundingClientRect();
  return `${Math.round(r.top)}x${Math.round(r.left)}`;
}

/** Nhật ký gọi của stub, để lời nhắn khi hỏng nói được đã gọi tới đâu. */
function nhatKyGoi() {
  return (window.__snapshotApiLog ?? []).join(" | ");
}

if (reasons.length && !REQUIRED) {
  test(`đường bấm tới sáu tính năng xã hội — BỎ QUA: ${reasons.join("; ")}`, {
    skip: reasons.join("; "),
  }, () => {});
} else {
  describe("từ shell bấm được tới thước phim, tim, bình luận và bốn mức người đọc", () => {
    let page;
    let server;
    const trangPath = join(EXPORT_DIR, TRANG);

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      const indexHtml = readFileSync(join(EXPORT_DIR, "index.html"), "utf8");
      const i = indexHtml.indexOf("<head>");
      assert.ok(i !== -1, "index.html không có <head> để chèn stub");
      const tiem =
        `<script>(${installTabStubs.toString()})(` +
        `${JSON.stringify(API_BASE)},${JSON.stringify(taoFixtures())});</script>`;
      writeFileSync(trangPath, indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6));

      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      await page.viewport(390, 844);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      try {
        unlinkSync(trangPath);
      } catch (err) {
        if (err.code !== "ENOENT") throw err;
      }
    });

    /** Wait, and say what was on screen if the wait ran out.
     *
     *  Cùng lý do như trong `duong-vao-ban-do-nhom.test.mjs`: một dòng "timed
     *  out waiting for X" trần không phân biệt nổi ba thứ cần ba cách sửa khác
     *  nhau — cú bấm trượt, một read từ chối, hay màn chỉ chậm. Màn hình và
     *  nhật ký gọi tách được ba cái đó trong một lần đọc. */
    async function doi(fn, nhan, ...args) {
      try {
        await page.waitFor(fn, { label: nhan }, ...args);
      } catch (err) {
        const chu = await page.evaluate(chuTrenMan).catch(() => "(không đọc được màn)");
        const goi = await page.evaluate(nhatKyGoi).catch(() => "(không đọc được nhật ký)");
        err.message += `\n    màn đang là: ${chu.slice(0, 600)}\n    đã gọi: ${goi}`;
        throw err;
      }
    }

    /** Giữ tới khi một control có mặt VÀ đã thôi di chuyển.
     *
     *  Điều kiện, không phải đồng hồ: hai lần đo liên tiếp cùng một toạ độ.
     *  Nguy cơ có thật và đã đo được ở file bản đồ nhóm — thẻ dưới mount muộn
     *  đẩy nút đi, và cú bấm đo trước đó rơi vào chỗ nút vừa rời khỏi. Đó là
     *  một cú TRƯỢT IM LẶNG: không lỗi, không handler, và hỏng lộ ra ba bước
     *  sau dưới tên của sản phẩm chứ không phải tên của phép đo. */
    async function choNhanYen(nhan) {
      const han = Date.now() + 15000;
      let truoc = null;
      let yen = 0;
      for (;;) {
        const vi = await page.evaluate(viTriTheoNhan, nhan).catch(() => null);
        if (vi !== null && vi === truoc) {
          if (++yen >= 2) return;
        } else {
          yen = 0;
        }
        truoc = vi;
        if (Date.now() > han) {
          const chu = await page.evaluate(chuTrenMan).catch(() => "(không đọc được màn)");
          throw new Error(
            `"${nhan}" không đứng yên (hoặc không có) sau 15s; vị trí cuối ${vi}\n` +
              `    màn đang là: ${chu.slice(0, 600)}`,
          );
        }
        await new Promise((r) => setTimeout(r, 60));
      }
    }

    /** Một lần mount thật sự mới, trên tab được nêu tên.
     *
     *  Cú nhảy qua `about:blank` là chịu lực: hai URL chỉ khác nhau sau dấu `#`
     *  là một điều hướng cùng-tài-liệu, React không remount, và ca sau bắt đầu
     *  trên đúng màn ca trước để lại — tức là đúng cái trạng thái làm cho "đã
     *  tới nơi" xanh mà không cần bấm gì. */
    async function moTab(tab) {
      await page.goto("about:blank");
      await page.goto(`${server.url}${TRANG}#tab=${tab}&nguoi=${NGUOI}`);
      // `n` đi qua tham số chứ không đóng bao: `evaluate` stringify hàm này rồi
      // gọi nó trong trang, nên một biến tự do sẽ tới nơi dưới dạng
      // `ReferenceError` ở một dòng không ai đang nhìn — và ở đây nó đội lốt
      // "tab không bao giờ render xong", tức là đổ lỗi cho sản phẩm.
      await doi(
        (n) => !!document.querySelector(`[aria-label="${n}"]`),
        `tab ${tab} render xong (thanh tab có nút "${NUT_TAO}")`,
        NUT_TAO,
      );
    }

    /** Mở tấm `[+]`, và đợi hàng cần bấm đứng yên.
     *
     *  Trả về nhãn đầy đủ của hàng, đọc từ DOM: `clickLabel` cần nhãn CHÍNH
     *  XÁC và từ chối bấm khi có hơn một cái trùng, nên đọc rồi bấm là cách
     *  duy nhất vừa bám được `hint` đang thay đổi vừa không đoán mò. */
    async function moMenuTao(dauHang) {
      await choNhanYen(NUT_TAO);
      await page.clickLabel(NUT_TAO);
      await doi(
        (d) =>
          [...document.querySelectorAll("[aria-label]")].some((e) =>
            e.getAttribute("aria-label").startsWith(d),
          ),
        `menu [+] mở ra và có hàng "${dauHang}…"`,
        dauHang,
      );
      const nhan = await page.evaluate(nhanTheoDau, dauHang);
      assert.equal(
        nhan.length,
        1,
        `phải có đúng một hàng "${dauHang}…" trong menu [+]; đang có ${nhan.length}: ${nhan.join(" / ")}`,
      );
      await choNhanYen(nhan[0]);
      return nhan[0];
    }

    /* ---------------------------------------------------------- đối chứng --- */

    test("ĐỐI CHỨNG DƯƠNG: cách đo này xếp được 'Tạo khoản chi' là bấm tới được", async () => {
      await moTab("kham-pha");

      // Trước khi bấm: chưa có màn chụp bill nào. Nếu bỏ assert này thì ca sẽ
      // xanh cả trên một shell mở thẳng vào luồng khoản chi.
      const truoc = await page.evaluate(nhanTheoDau, NHAN_CHUP_BILL);
      assert.equal(truoc.length, 0, `"${NHAN_CHUP_BILL}" không được có sẵn trên tab Khám phá`);

      const hang = await moMenuTao(HANG_KHOAN_CHI);
      await page.clickLabel(hang);

      await doi(
        (n) => !!document.querySelector(`[aria-label="${n}"]`),
        `luồng khoản chi mở ra và vẽ nút "${NHAN_CHUP_BILL}"`,
        NHAN_CHUP_BILL,
      );

      // Luồng chiếm cả màn: thanh tab biến mất. Đây là nửa phân biệt "đã đi
      // tới" với "tab mọc thêm chữ".
      const conThanhTab = await page.evaluate(nhanTheoDau, NUT_TAO);
      assert.equal(
        conThanhTab.length,
        0,
        `luồng khoản chi phải thay cả màn; nút "${NUT_TAO}" vẫn còn`,
      );
    });

    test("ĐỐI CHỨNG ÂM: chỉ mở [+] mà không bấm hàng nào thì không tới màn nào", async () => {
      await moTab("kham-pha");
      await choNhanYen(NUT_TAO);
      await page.clickLabel(NUT_TAO);
      await doi(
        (d) =>
          [...document.querySelectorAll("[aria-label]")].some((e) =>
            e.getAttribute("aria-label").startsWith(d),
          ),
        `menu [+] mở ra`,
        HANG_ALBUM,
      );

      // Menu in cả nhãn LẪN gợi ý của từng hàng, nên "thước phim AI" có mặt
      // trên màn ngay lúc này. Đó chính là lý do mọi ca dưới đây phải đứng
      // trên chữ của trạng thái ĐÃ TẢI XONG chứ không trên tên tính năng.
      const chu = await page.evaluate(chuTrenMan);
      for (const dich of [CHU_KE_ALBUM, CHU_MOT_ALBUM, CHU_THUOC_PHIM, CHU_TUONG_KY_NIEM]) {
        assert.ok(
          !chu.includes(dich),
          `mở [+] mà chưa bấm hàng nào thì không được thấy "${dich}"`,
        );
      }
      const chupBill = await page.evaluate(nhanTheoDau, NHAN_CHUP_BILL);
      assert.equal(chupBill.length, 0, `mở [+] không được vẽ sẵn "${NHAN_CHUP_BILL}"`);
    });

    /* ------------------------------------------------------------ F37 reel --- */

    test("F37: [+] → Album chuyến đi → thẻ một chuyến → 'Dựng thước phim'", async () => {
      await moTab("kham-pha");

      const hang = await moMenuTao(HANG_ALBUM);
      await page.clickLabel(hang);

      // Tầng 1: kệ album. `Nhóm đã có` là thẻ đếm, chỉ vẽ sau khi `/albums`
      // đã trả lời và parse xong.
      await doi(
        (t) => document.body.innerText.includes(t),
        `kệ album mở ra sau khi bấm hàng "${HANG_ALBUM}…"`,
        CHU_KE_ALBUM,
      );

      // Tầng 2: một chuyến. Cả tấm thẻ là nút — đọc nhãn thật rồi bấm.
      const the = await page.evaluate(nhanTheoDau, "Mở album ");
      assert.ok(the.length >= 1, "kệ album không có thẻ chuyến nào để bấm");
      await choNhanYen(the[0]);
      await page.clickLabel(the[0]);
      await doi(
        (t) => document.body.innerText.includes(t),
        `màn một album mở ra sau khi bấm "${the[0]}"`,
        CHU_MOT_ALBUM,
      );

      // Tầng 3: thước phim. Trước khi bấm, câu của reel chưa có — nếu không
      // khẳng định điều đó thì ca này xanh cả khi reel tự vẽ sẵn.
      const truoc = await page.evaluate(chuTrenMan);
      assert.ok(
        !truoc.includes(CHU_THUOC_PHIM),
        `"${CHU_THUOC_PHIM}" không được có sẵn trước khi bấm "Dựng thước phim"`,
      );
      await page.clickChu("Dựng thước phim");
      await doi(
        (t) => document.body.innerText.includes(t),
        `GET /albums/{outing}/reel trả lời và reel in "${CHU_THUOC_PHIM}"`,
        CHU_THUOC_PHIM,
      );
    });

    /* ------------------------------------------------- F40 tim · F41 bình luận --- */

    test("F40: [+] → Kỷ niệm nhóm → bấm trái tim thì tim đổi trạng thái", async () => {
      await moTab("kham-pha");

      const hang = await moMenuTao(HANG_KY_NIEM);
      await page.clickLabel(hang);
      await doi(
        (t) => document.body.innerText.includes(t),
        `tường kỷ niệm mở ra sau khi bấm hàng "${HANG_KY_NIEM}…"`,
        CHU_TUONG_KY_NIEM,
      );

      // Nhãn mang cả số đếm, nên nó vừa là chỗ để bấm vừa là chỗ đọc kết quả.
      const chuaTha = await page.evaluate(nhanTheoDau, "Thả tim.");
      assert.ok(chuaTha.length >= 1, "tường kỷ niệm không vẽ nút thả tim nào");
      const nhanTruoc = chuaTha[0];
      await choNhanYen(nhanTruoc);
      await page.clickLabel(nhanTruoc);

      // Sau POST /reactions, thẻ đọc lại và nút lật sang "Bỏ tim". Đây là
      // hậu quả nhìn thấy được của cú bấm, không phải là "nút vẫn còn đó".
      await doi(
        () =>
          [...document.querySelectorAll("[aria-label]")].some((e) =>
            e.getAttribute("aria-label").startsWith("Bỏ tim."),
          ),
        `sau khi thả tim, nút phải lật sang "Bỏ tim.…" (nhãn trước: ${nhanTruoc})`,
      );
      const goi = await page.evaluate(nhatKyGoi);
      assert.match(
        goi,
        /\/memories\/[^/\s]+\/reactions/,
        `phải có một lời gọi tới /memories/{id}/reactions; nhật ký: ${goi}`,
      );
    });

    test("F41: trên tường kỷ niệm, bấm nút bình luận thì ô soạn hiện ra", async () => {
      await moTab("kham-pha");

      const hang = await moMenuTao(HANG_KY_NIEM);
      await page.clickLabel(hang);
      await doi(
        (t) => document.body.innerText.includes(t),
        `tường kỷ niệm mở ra sau khi bấm hàng "${HANG_KY_NIEM}…"`,
        CHU_TUONG_KY_NIEM,
      );

      const O_SOAN = "Ô viết bình luận cho ảnh này";
      const truoc = await page.evaluate(nhanTheoDau, O_SOAN);
      assert.equal(truoc.length, 0, `"${O_SOAN}" không được mở sẵn trên tường`);

      // Nhãn của nút đổi theo số bình luận đang có ("Xem N bình luận…" hoặc
      // "Viết bình luận đầu tiên…"), nên bắt theo cả hai đầu.
      const nutBinhLuan = await page.evaluate(() =>
        [...document.querySelectorAll("[aria-label]")]
          .map((e) => e.getAttribute("aria-label"))
          .filter((n) => /^(Xem \d+ bình luận|Viết bình luận đầu tiên)/.test(n)),
      );
      assert.ok(nutBinhLuan.length >= 1, "tường kỷ niệm không vẽ nút bình luận nào");
      await choNhanYen(nutBinhLuan[0]);
      await page.clickLabel(nutBinhLuan[0]);

      await doi(
        (n) => !!document.querySelector(`[aria-label="${n}"]`),
        `sau khi bấm "${nutBinhLuan[0]}", ô soạn bình luận phải hiện ra`,
        O_SOAN,
      );
      const goi = await page.evaluate(nhatKyGoi);
      assert.match(
        goi,
        /\/memories\/[^/\s]+\/comments/,
        `phải có một lời gọi tới /memories/{id}/comments; nhật ký: ${goi}`,
      );
    });

    /* ------------------------------------------------------- F42 người đọc --- */

    test("F42: tab Cá nhân → 'Viết lên tường' → bốn mức, và chọn 'Một nhóm' có hậu quả", async () => {
      await moTab("ca-nhan");

      // Ô soạn đóng khi mới vào: bốn mức chưa được vẽ. Khẳng định trước, nếu
      // không thì ca này không phân biệt được "bấm mở ra" với "vốn đã mở".
      const truoc = await page.evaluate(nhanTheoDau, "Chỉ mình tôi.");
      assert.equal(truoc.length, 0, "bốn mức người đọc không được vẽ sẵn khi ô soạn còn đóng");

      await doi(
        (t) =>
          [...document.querySelectorAll("button, [role='button']")].some(
            (e) => e.textContent.replace(/\s+/g, " ").trim() === t,
          ),
        `tường Cá nhân vẽ nút "${NUT_VIET_TUONG}"`,
        NUT_VIET_TUONG,
      );
      await page.clickChu(NUT_VIET_TUONG);

      await doi(
        () =>
          [...document.querySelectorAll("[aria-label]")].some((e) =>
            e.getAttribute("aria-label").startsWith("Chỉ mình tôi."),
          ),
        `sau khi bấm "${NUT_VIET_TUONG}", ô soạn và bốn mức người đọc phải hiện ra`,
      );

      // Bốn mức, đủ cả bốn. Ba trong bốn có mặt là một sản phẩm khác.
      for (const muc of BON_MUC) {
        const co = await page.evaluate(nhanTheoDau, muc);
        assert.equal(co.length, 1, `phải có đúng một mức "${muc}…"; đang có ${co.length}`);
      }

      // Hậu quả của cú bấm. qa3-tt-0035 ghi rằng bốn mức "chưa có hậu quả nào
      // nhìn thấy được trong app"; ở phía SOẠN thì có đúng một, và đây là nó.
      const chuTruoc = await page.evaluate(chuTrenMan);
      for (const hq of HAU_QUA_MOT_NHOM) {
        assert.ok(!chuTruoc.includes(hq), `"${hq}" không được hiện trước khi chọn "Một nhóm"`);
      }

      const mucNhom = await page.evaluate(nhanTheoDau, MUC_MOT_NHOM);
      await choNhanYen(mucNhom[0]);
      await page.clickLabel(mucNhom[0]);

      await doi(
        (hq) => hq.some((t) => document.body.innerText.includes(t)),
        `chọn "Một nhóm" phải đổi màn: hiện ${HAU_QUA_MOT_NHOM.map((t) => `"${t}"`).join(" hoặc ")}`,
        HAU_QUA_MOT_NHOM,
      );
    });
  });
}
