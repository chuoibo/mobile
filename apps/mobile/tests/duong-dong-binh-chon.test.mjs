/* "Đóng bình chọn" là một cú bấm có thật, và cú bấm đó đi lên đường dây.
 *
 * ## Vì sao file này tồn tại
 *
 * #402 đi bộ và tìm ra: bình chọn của sản phẩm nằm HOÀN TOÀN trong luồng tin
 * nhắn (`cardMoBinhChon` / `cardBoPhieu` do `TinNhan.tsx` gửi), còn nút "Đóng
 * bình chọn" thì chỉ tồn tại trên `screens/binh-chon/BinhChon.tsx` — một màn
 * chỉ mở được sau cửa quét `?man=binh-chon`, nơi `App.tsx` truyền
 * `onDong={() => {}}`. Hai đầu, không có ở giữa. Đo lúc đó: `votes` 0 dòng,
 * `vote_ballots` 0 dòng, dù `/votes/{id}/close` có route và có wrapper.
 *
 * Nên câu hỏi của file này không phải "nút có được vẽ không" —
 * `dong-binh-chon-the.test.mjs` đã trả lời bằng markup. Câu hỏi là: một ngón
 * tay đi từ màn mở đầu có tới được nó không, và bấm vào thì CÓ GÌ ĐI LÊN MÁY
 * CHỦ không.
 *
 * ## Vì sao phải đọc thẻ đã gửi, không chỉ đọc màn
 *
 * `onDong={() => {}}` vẫn làm màn vẽ lại và vẫn không lỗi. Chuỗi "Đã đóng"
 * trên màn chỉ xuất hiện khi `tongHopBinhChon` thấy một thẻ `poll_close` trong
 * luồng, mà luồng thì chỉ có cái máy chủ trả về — nên hai phép đo dưới đây bổ
 * cho nhau: `__snapshotTheDaGui` nói thẻ đã RỜI máy, chữ trên màn nói thẻ đã
 * QUAY LẠI và được đếm. No-op giết được bằng cái thứ nhất; một thẻ gửi đi mà
 * phép gấp bỏ qua thì giết được bằng cái thứ hai.
 *
 * CHỨNG MINH: có đường bấm từ màn mở đầu tới nút; nút gửi đúng một thẻ
 * `poll_close`; sau khi đóng thì thẻ nói "Đã đóng", gọi tên bên được chọn, và
 * hàng phiếu khoá lại; người KHÔNG mở thì không thấy nút.
 * KHÔNG CHỨNG MINH: máy chủ thật lưu và phát lại thẻ này cho phone khác (stub
 * trả lời, không phải Postgres); native vẽ giống web; hay chuyện gì xảy ra khi
 * POST lỗi.
 *
 * Chạy từ apps/mobile, trên bản dựng tự tay dựng:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/duong-dong-binh-chon.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { trangTuLai } from "../tools/quet-man-sau-tap.mjs";
import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

const RONG = 390;
const CAO = 844;

/** Người đăng nhập, và vì thế là người MỞ bình chọn trong kịch bản này. Stub
 *  đọc `author_id` từ header `X-Actor-ID`, đúng như máy chủ thật làm, nên
 *  "người mở" ở đây là một sự thật của đường dây chứ không phải một cờ cục bộ. */
const TOI = "Minh";
const KHAC = "Trang";

const CAU_HOI = "Ăn tối ngày 1 ở đâu nhỉ?";
const QUAN_A = "Tiệm nướng Xóm Lèo";
const QUAN_B = "Lẩu gà lá é Tao Ngộ";

/** Bình chọn stub đã gieo sẵn, do NGƯỜI KHÁC (Trang) mở. Đối chứng âm sống
 *  cùng màn với bình chọn của tôi, nên "nút theo người mở" đo được trên một
 *  màn duy nhất — một lần tải trang là một người, nên không có cách nào khác. */
const CAU_HOI_CUA_TRANG = "Sáng mai ăn gì?";

/** Câu chỉ tấm thẻ ĐÃ ĐÓNG in ra. Không dùng "Đã đóng" một mình làm needle cho
 *  phép đo cuối: nó là hai chữ ngắn và dễ trùng; câu này gọi tên bên được chọn
 *  nên nó cũng chứng minh phép gấp đã đếm, không chỉ đổi nhãn. */
const CAU_KET_QUA = `${QUAN_A} được chọn với 1 phiếu`;

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}
// bug-010019: bản dựng cũ hơn cây nguồn thì cổng này gọi tên một nút vắng mặt
// trên một màn đang vẽ nó đúng. Từ chối báo còn hơn báo sai.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`đường đóng bình chọn — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("đường đóng bình chọn, trên trang render thật", () => {
    let page;
    let server;
    const daTao = [];

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      for (const f of daTao) rmSync(f, { force: true });
    });

    async function diBo(ten, kichBan, nhan) {
      const duong = join(EXPORT_DIR, ten);
      writeFileSync(
        duong,
        trangTuLai(readFileSync(join(EXPORT_DIR, "index.html"), "utf8"), kichBan, null),
      );
      daTao.push(duong);

      await page.viewport(RONG, CAO);
      await page.goto(server.url + ten);
      await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
        timeout: 180000,
        label: `kịch bản đi bộ "${nhan}"`,
      });
      const lai = await page.evaluate(() => ({ xong: window.__lai.xong, loi: window.__lai.loi }));
      assert.equal(lai.loi, null, `kịch bản đi bộ "${nhan}" HỎNG: ${lai.loi}`);
      assert.equal(lai.xong, true, `kịch bản đi bộ "${nhan}" chưa xong`);
    }

    /** Vào app dưới tên một người cụ thể. Người này là `X-Actor-ID` của mọi
     *  request sau đó, nên chọn ai ở đây quyết định ai là "người mở". */
    function vaoApp(ten) {
      return [
        { cho: "AI đi chơi, chia bill thông minh" },
        { bamChu: "Đăng ký với Apple" },
        { cho: "Vào app với tư cách ai?" },
        { bam: `Vào app với tư cách ${ten}` },
        { cho: "Khám phá" },
      ];
    }

    /** Vào tới tab Plan của nhóm, nơi mọi bình chọn của luồng được vẽ. */
    function denTabPlan(ten) {
      return [
        ...vaoApp(ten),
        { bam: "Tin nhắn: chat nhóm và AI" },
        // `bam` (theo aria-label), không phải `bamChu`: chip này là
        // `role="tab"`, và bộ chọn của `bamChu` chỉ phủ button/[role=button]/a
        // — đúng cái điểm mù đã làm một máy quét đọc thanh tab thành số 0.
        { bam: "Plan" },
        { cho: "Bình chọn của nhóm" },
      ];
    }

    /** Số nút "Đóng bình chọn" đang có trên màn, kèm việc nó có bấm được không.
     *
     *  Phủ hết vai trò `button` VÀ `[role=button]`: bài học của Lead tối
     *  2026-08-31 là một máy quét chỉ liệt kê `button` đọc ra số 0 trên một
     *  thanh tab có thật, và số 0 đọc y hệt "không tồn tại". */
    async function nutDong() {
      return page.evaluate(() =>
        [...document.querySelectorAll('button, [role="button"]')]
          .filter((n) => n.textContent.replace(/\s+/g, " ").trim() === "Đóng bình chọn")
          .map((n) => ({ khoa: n.disabled === true || n.getAttribute("aria-disabled") === "true" })),
      );
    }

    async function demNutDong() {
      return (await nutDong()).length;
    }

    /** Mở một bình chọn từ tab Plan, dùng hai quán stub đã gieo vào luồng. */
    function moBinhChon(ten) {
      return [
        ...denTabPlan(ten),
        { bam: "Mở bình chọn mới" },
        { cho: "Lựa chọn" },
        { go: { oNhap: CAU_HOI, chu: CAU_HOI } },
        { bam: `${QUAN_A}, chưa chọn` },
        { bam: `${QUAN_B}, chưa chọn` },
        { bamChu: "Mở bình chọn" },
        // Thẻ bình chọn đã nằm trong luồng: `Mở bình chọn` đưa về chip chat.
        { cho: CAU_HOI },
      ];
    }

    test("bình chọn của người KHÁC không mời tôi bấm Đóng", async () => {
      // Chạy trước, và cố ý: lúc này trong luồng mới có đúng một bình chọn, của
      // Trang. Số 0 ở đây không thể đọc nhầm thành "chưa có bình chọn nào",
      // vì câu hỏi của Trang phải có mặt trên màn thì ca mới đi tiếp.
      await diBo("__dong-binh-chon-nguoi-khac.html", denTabPlan(TOI), "xem bình chọn của người khác");

      const chu = await page.evaluate(() => document.body.innerText || "");
      assert.ok(
        chu.includes(CAU_HOI_CUA_TRANG),
        `không thấy bình chọn của ${KHAC}: ${JSON.stringify(chu.slice(0, 300))}`,
      );
      assert.equal(await demNutDong(), 0, `${TOI} không mở bình chọn này mà vẫn được mời bấm Đóng`);
      console.log(`  [${TOI} xem bình chọn của ${KHAC}] 0 nút Đóng`);
    });

    test("người mở đi từ màn mở đầu tới được nút Đóng bình chọn", async () => {
      await diBo("__dong-binh-chon-mo.html", moBinhChon(TOI), "mở bình chọn");

      // Nút phải BẤM ĐƯỢC, không chỉ có mặt: một `<button disabled>` cũng
      // khớp mọi phép tìm theo chữ, và không ai đi qua được nó.
      //
      // Và phải là ĐÚNG MỘT: trên màn lúc này có hai bình chọn, của tôi và của
      // Trang. Con số 1 ở đây vì thế nói cả hai vế cùng lúc — có nút cho cái
      // tôi mở, và không có nút cho cái tôi không mở.
      const nut = await nutDong();
      assert.equal(nut.length, 1, `phải thấy đúng 1 nút "Đóng bình chọn", thấy ${nut.length}`);
      assert.equal(nut[0].khoa, false, 'nút "Đóng bình chọn" đang bị khoá');
      console.log(`  [${TOI} mở] thấy 1 nút "Đóng bình chọn", bấm được`);
    });

    test("bấm Đóng thì một thẻ poll_close rời máy, và thẻ trên màn đọc là đã đóng", async () => {
      const kichBan = [
        ...moBinhChon(TOI),
        // Một phiếu trước khi đóng, để câu kết quả có tên để gọi. Nếu không có
        // phiếu nào thì "Đã đóng. Chưa có phiếu nào" cũng xanh, và ca này sẽ
        // không phân biệt được "đếm đúng" với "đổi nhãn".
        { bam: `${QUAN_A}, 0 phiếu, không đang dẫn` },
        // Chờ bằng CHỮ NHÌN THẤY, không bằng aria-label: `cho` đọc
        // `document.body.innerText`, mà innerText không mang aria-label theo.
        // Nhóm stub có 7 thành viên, nên "1/7" chỉ đúng sau khi phiếu đã đi và
        // đã quay về — không có chặng này thì cú bấm Đóng đua với POST phiếu.
        { cho: "1/7 thành viên đã bỏ phiếu" },
        { bamChu: "Đóng bình chọn" },
        { cho: CAU_KET_QUA },
      ];
      await diBo("__dong-binh-chon-bam.html", kichBan, "mở, bỏ phiếu, đóng");

      // 1. Thẻ đã RỜI máy. Đây là chặng giết `onDong={() => {}}`: một no-op vẫn
      //    vẽ lại màn và vẫn không lỗi, nhưng không để lại gì ở đây.
      const daGui = await page.evaluate(() => window.__snapshotTheDaGui ?? []);
      assert.deepEqual(
        daGui,
        ["poll", "poll_vote", "poll_close"],
        `thẻ gửi lên máy chủ phải là mở → phiếu → đóng, nhận được ${JSON.stringify(daGui)}`,
      );

      // 2. Thẻ đã QUAY LẠI và được phép gấp đếm.
      const chu = await page.evaluate(() => document.body.innerText || "");
      assert.ok(chu.includes("Đã đóng"), `màn không nói "Đã đóng": ${JSON.stringify(chu.slice(0, 400))}`);
      assert.ok(
        chu.includes(CAU_KET_QUA),
        `màn không gọi tên bên được chọn ("${CAU_KET_QUA}"): ${JSON.stringify(chu.slice(0, 400))}`,
      );

      // 3. Nút tự biến mất, và hàng phiếu khoá lại. Một bình chọn đã đóng mà
      //    còn bấm bỏ phiếu được là một cái tích gửi đi rồi bị phép gấp bỏ —
      //    người ta thấy nó xuất hiện, rồi lần đọc sau nó không còn ở đó.
      assert.equal(await demNutDong(), 0, "đóng rồi mà nút Đóng bình chọn vẫn còn");

      // Chỉ hai hàng của bình chọn TÔI vừa đóng. Bình chọn của Trang vẫn mở và
      // vẫn phải bấm được — nếu quét cả màn thì một bản sửa khoá hết mọi hàng
      // của mọi bình chọn cũng sẽ xanh ở đây.
      const tatCaHang = await page.evaluate(() =>
        [...document.querySelectorAll('[role="radio"]')].map((n) => ({
          nhan: n.getAttribute("aria-label") ?? "",
          khoa: n.disabled === true || n.getAttribute("aria-disabled") === "true",
        })),
      );
      const hang = tatCaHang.filter((h) => h.nhan.startsWith(QUAN_A) || h.nhan.startsWith(QUAN_B));
      assert.equal(hang.length, 2, `phải còn 2 hàng lựa chọn của tôi, thấy ${hang.length} trong ${JSON.stringify(tatCaHang.map((h) => h.nhan))}`);
      for (const h of hang) {
        assert.equal(h.khoa, true, `hàng "${h.nhan}" chưa khoá sau khi đóng`);
        assert.ok(
          (h.nhan ?? "").includes("đã đóng, không chọn được"),
          `hàng "${h.nhan}" không nói ra vì sao bấm không ăn`,
        );
      }
      // Và bình chọn của Trang KHÔNG bị đóng lây. Đây là ca âm cho "đóng cái
      // này không đụng cái kia", đo trên màn thay vì trên mảng.
      const hangCuaTrang = tatCaHang.filter(
        (h) => h.nhan.startsWith("Bánh mì") || h.nhan.startsWith("Phở"),
      );
      assert.equal(hangCuaTrang.length, 2, `thiếu hàng của bình chọn ${KHAC}`);
      for (const h of hangCuaTrang) {
        assert.equal(h.khoa, false, `bình chọn của ${KHAC} bị đóng lây: "${h.nhan}"`);
      }
      console.log(`  [đóng] thẻ đã gửi: ${daGui.join(" → ")}; 2 hàng khoá; "${CAU_KET_QUA}"`);
    });

  });
}
