/* Bấm "Hỏi Rủ Đi AI" trong Chrome thật, xem byte gì rời máy và chữ gì hiện ra.
 *
 * ## Câu hỏi thứ nhất, và nó là câu phải trả lời TRƯỚC khi viết câu chữ
 *
 * Máy chủ chỉ trả `cooldown` khi client KHÔNG gửi `{"requested": true}` (#420).
 * Nên nếu người dùng gõ hẳn một câu hỏi rồi bấm nút mà vẫn nhận `cooldown`,
 * lỗi nằm ở client: nó đang bắn lượt TỰ NGUYỆN thay cho lượt HỎI THẲNG, và
 * viết câu chữ cho ca đó là dán băng lên chỗ sai.
 *
 * `tin-nhan.test.mjs` đã ghim rằng `goiAiTurn({hoiThang:true})` gửi cờ. Cái nó
 * không đo được là cú BẤM: `TinNhan.tsx` có hai đường gọi cùng một hàm, một
 * đường có cờ và một đường không, và một nút nối nhầm đường trông y hệt nhau ở
 * tầng module. Đó chính là hình dạng của phiếu #402 (nút có thật, đường bấm
 * không tới) và của bug-002847 (cờ có thật, không màn nào gửi).
 *
 * Nên file này đo bằng cách ghi lại thân request rời khỏi trang, cho hai hành
 * động khác nhau của một người thật:
 *
 *   bấm "Hỏi Rủ Đi AI"   -> thân phải là {"requested":true}
 *   gửi một tin nhắn      -> thân phải KHÔNG có byte nào
 *
 * Hai dòng đó phân biệt được nhau, nên một cái nối nhầm sang cái kia làm đỏ.
 *
 * ## Câu hỏi thứ hai: câu chữ có TỚI ĐƯỢC màn không
 *
 * `cau-chu-im-lang.test.mjs` chứng minh bảng câu chữ đủ tên, phân biệt được và
 * đúng số. Một bảng không ai render vẫn qua được hết những ca đó. Ở đây mỗi lý
 * do được máy chủ giả trả về một lần, rồi đọc lại chữ trên `document.body`.
 *
 * ## Chứng minh / KHÔNG chứng minh
 *
 * CHỨNG MINH: trên bản dựng trong `MOBILE_WEB_EXPORT`, Chrome này, 390x844,
 * một ngón tay đi từ màn mở đầu tới ô chat, bấm nút hỏi, và cú bấm đó gửi cờ
 * `requested`; chín outcome ra chín câu khác nhau trên màn; lượt tự động bị
 * nhịp chặn vẽ ra KHÔNG GÌ CẢ.
 * KHÔNG CHỨNG MINH: máy chủ thật trả về những tên này (stub trả lời), iOS hay
 * Android vẽ giống web, hay người thật hiểu câu chữ.
 *
 * Chạy từ apps/mobile, trên bản dựng tự tay dựng:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/cau-chu-im-lang-web.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";
import { API_BASE, installTabStubs, taoFixtures } from "../tools/tab-snapshots.mjs";
import {
  CAU_LY_DO_LA,
  CAU_NHOM_CHUA_MO_XONG,
  CAU_THEO_LY_DO,
  LY_DO_TRAN_PHUT,
} from "../dist-test/screens/chat/ai.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const GOC = join(HERE, "..");
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(GOC, ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

const KHUNG = { w: 390, h: 844 };

const NUT_MO_SHEET = "Đăng ký với Apple";
const TIEU_DE_SHEET = "Vào app với tư cách ai?";
const CHON_MINH = "Vào app với tư cách Minh";
const TAB_TIN_NHAN = "Tin nhắn: chat nhóm và AI";
const NUT_HOI_AI = "Hỏi Rủ Đi AI";
const O_NHAP = "Ô nhập tin nhắn";
const NUT_GUI = "Gửi tin nhắn";

/** Mỗi outcome một lượt: tên `reason` của thân 200, hoặc mã trạng thái. */
const LUOT = [
  { ten: "no_conversation" },
  { ten: "already_spoke_last" },
  { ten: "cooldown" },
  { ten: "rate_limited" },
  { ten: "asked_too_often" },
  { ten: "unavailable" },
  { ten: "ungrounded" },
  { ten: LY_DO_TRAN_PHUT, status: 429 },
  // Một tên bản dựng này chưa từng thấy. Máy chủ sau có thể thêm, và cái phải
  // hiện ra là câu vét chứ không phải khoảng trắng.
  { ten: "quiet_hours", cau: CAU_LY_DO_LA },
];

/* ------------------------------------------------ chạy trong trang ------- */

/** Chặn riêng `/ai-turn`, ghi lại thân, trả lời theo `window.__aiTraLoi`.
 *
 *  Cài SAU `installTabStubs` nên nó bọc bản đã vá: mọi route khác vẫn do
 *  fixture trả lời, còn lượt AI thì file này cầm lái. */
function caiStubAiTurn() {
  const truoc = window.fetch.bind(window);
  window.__aiThan = [];
  window.__aiTraLoi = { status: 200, body: null };
  window.fetch = async (dia, init) => {
    const url = typeof dia === "string" ? dia : String(dia && dia.url ? dia.url : dia);
    if (!url.endsWith("/ai-turn")) return truoc(dia, init);
    // `undefined` và `null` là hai chuyện khác nhau ở đây: lượt tự động không
    // đặt khoá `body` nào cả. Ghi lại nguyên trạng, đừng gấp về một giá trị.
    window.__aiThan.push(init && "body" in init ? init.body : null);
    const tl = window.__aiTraLoi;
    return new Response(JSON.stringify(tl.body), {
      status: tl.status,
      headers: { "Content-Type": "application/json" },
    });
  };
}

/** Treo `GET /contexts/{id}/members`, bước cuối của `khoiDongNhom`.
 *
 *  Nhóm dừng ở `dang-tai` mãi mãi, nên cửa sổ "nút đã vẽ, nhóm chưa xong" trở
 *  thành một trạng thái đứng yên đo được thay vì một cuộc đua vài chục ms. Chỉ
 *  treo GET: POST members là bước mời người, treo nó thì dừng sớm hơn một bước
 *  và màn hiện ra một câu khác. */
function treoRouteNhom() {
  const truoc = window.fetch.bind(window);
  window.fetch = async (dia, init) => {
    const url = typeof dia === "string" ? dia : String(dia && dia.url ? dia.url : dia);
    const method = ((init && init.method) || "GET").toUpperCase();
    if (method === "GET" && /\/contexts\/[^/]+\/members$/.test(url)) {
      return new Promise(() => {});
    }
    return truoc(dia, init);
  };
}

function datTraLoi(tl) {
  window.__aiTraLoi = tl;
  return true;
}

function docThan() {
  return window.__aiThan;
}

const chuTrenMan = () => document.body.innerText.replace(/\s+/g, " ");

/* ------------------------------------------------ cổng ------------------- */

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
const cu = lyDoBanDungCu(EXPORT_DIR, GOC);
if (cu) reasons.push(cu);

if (reasons.length && !REQUIRED) {
  test(`câu chữ im lặng trên trang render — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("câu chữ khi AI không trả lời, đo bằng cú bấm trên trang render thật", () => {
    let page;
    let server;

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      await page.viewport(KHUNG.w, KHUNG.h);
      console.log(`  đo trên: ${EXPORT_DIR}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
    });

    /** Vào ô chat từ màn mở đầu, với cả hai tầng stub đã cài. */
    async function vaoChat() {
      await page.goto(server.url, (chu) => document.body.innerText.includes(chu), NUT_MO_SHEET);
      await page.evaluate(installTabStubs, API_BASE, taoFixtures());
      await page.evaluate(caiStubAiTurn);
      await page.clickChu(NUT_MO_SHEET);
      await page.waitFor((chu) => document.body.innerText.includes(chu), { label: "sheet chọn người" }, TIEU_DE_SHEET);
      await page.clickLabel(CHON_MINH);
      await page.waitFor(() => document.querySelectorAll('[role="tab"]').length === 4, { label: "bốn tab của vỏ" });
      await page.clickLabel(TAB_TIN_NHAN);
      await page.waitFor(
        (nhan) => !!document.querySelector(`[aria-label="${nhan}"]`),
        { label: "nút hỏi AI" },
        NUT_HOI_AI,
      );
      // Nút hiện ra TRƯỚC khi nhóm mở xong, và bấm lúc đó là một ca khác hẳn
      // (`nhom-chua-mo-xong` ở dưới đo nó). Đợi số thành viên, thứ chỉ được vẽ
      // khi `nhom.kind === "xong"`. Bỏ bước này thì các ca dưới thỉnh thoảng
      // bấm trúng cửa sổ đó và đỏ vì lý do không liên quan; đã đo thấy đúng
      // một lần như vậy trước khi thêm dòng này.
      await page.waitFor(() => /\d+ thành viên/.test(document.body.innerText), {
        label: "nhóm mở xong",
      });
    }

    /* --- câu hỏi 1: cú bấm gửi cờ gì --------------------------------------- */

    test("bấm nút hỏi thì thân request là {\"requested\":true}", async () => {
      await vaoChat();
      await page.evaluate(datTraLoi, {
        status: 200,
        body: { context_id: null, spoke: false, reason: "asked_too_often", message: null },
      });
      await page.clickLabel(NUT_HOI_AI);
      await page.waitFor(
        (chu) => document.body.innerText.includes(chu),
        { label: "câu trả lời cho asked_too_often" },
        CAU_THEO_LY_DO.asked_too_often,
      );

      const than = await page.evaluate(docThan);
      console.log(`  thân rời trang khi BẤM NÚT: ${JSON.stringify(than)}`);
      assert.equal(than.length, 1, `chờ đúng một lượt AI, đếm được ${than.length}`);
      assert.deepEqual(
        JSON.parse(than[0]),
        { requested: true },
        "cú bấm không mang cờ requested. Máy chủ sẽ trả cooldown cho một câu " +
          "người ta vừa hỏi, và đó là lỗi ở đây chứ không phải ở nhịp.",
      );
    });

    test("gửi một tin nhắn thì lượt AI KHÔNG mang cờ, và nhịp vẽ ra không gì cả", async () => {
      await vaoChat();
      // Cùng một `reason` như ca trên sẽ vẽ ra một câu; ở đây phải KHÔNG có
      // câu nào, vì không ai đang đợi. Dùng `cooldown` cho đúng ca của phiếu.
      await page.evaluate(datTraLoi, {
        status: 200,
        body: { context_id: null, spoke: false, reason: "cooldown", message: null },
      });
      await page.typeInto(O_NHAP, "tối nay ăn gì");
      await page.clickLabel(NUT_GUI);
      await page.waitFor(() => window.__aiThan.length === 1, { label: "lượt AI sau khi gửi tin" });

      const than = await page.evaluate(docThan);
      console.log(`  thân rời trang khi GỬI TIN: ${JSON.stringify(than)}`);
      assert.deepEqual(
        than,
        [null],
        "lượt tự động gửi kèm thân. Gửi {\"requested\":true} ở đây thì AI trả " +
          "lời từng dòng một của một cuộc nói nhanh, đúng cái nhịp 90 giây tồn tại để chặn.",
      );

      const chu = await page.evaluate(chuTrenMan);
      assert.equal(
        chu.includes(CAU_THEO_LY_DO.cooldown),
        false,
        "lượt không ai hỏi mà vẫn vẽ câu giải thích ra màn: đó là tiếng ồn",
      );
    });

    /* --- câu hỏi 2: chín outcome ra chín câu ------------------------------- */

    const daThay = new Map();

    for (const luot of LUOT) {
      const cho = luot.cau ?? CAU_THEO_LY_DO[luot.ten];
      const status = luot.status ?? 200;
      test(`${luot.ten}: hiện đúng câu của nó trên màn`, async () => {
        assert.ok(cho, `không có câu chữ nào cho ${luot.ten}`);
        await vaoChat();

        const truoc = await page.evaluate(chuTrenMan);
        assert.equal(
          truoc.includes(cho),
          false,
          `"${cho.slice(0, 40)}…" đã có trên màn trước khi bấm; chuỗi này không phân biệt được gì`,
        );

        await page.evaluate(datTraLoi, {
          status,
          body:
            status === 429
              ? {
                  code: "companion_turn_rate_limited",
                  detail: "Quá nhiều lượt hỏi trợ lý nhóm; tối đa 30 lượt mỗi 60 giây. Thử lại sau ít phút.",
                }
              : { context_id: null, spoke: false, reason: luot.ten, message: null },
        });
        await page.clickLabel(NUT_HOI_AI);
        await page.waitFor((c) => document.body.innerText.includes(c), { label: luot.ten }, cho);

        const chu = await page.evaluate(chuTrenMan);
        console.log(`  ${luot.ten.padEnd(28)} -> "${cho.slice(0, 52)}…"`);

        // Không lộ chữ của máy. 429 là ca từng in nguyên `code` ra màn.
        for (const may of ["companion_turn_rate_limited", "HTTP 429", "Máy chủ trả lỗi", luot.ten]) {
          assert.equal(chu.includes(may), false, `màn hiện chữ của máy: "${may}"`);
        }
        // "còn nợ" là nhãn của route CHƯA CÓ (404). Một cái trần đang làm đúng
        // việc của nó không phải việc còn nợ ai.
        assert.equal(
          chu.includes("còn nợ"),
          false,
          `${luot.ten} đeo nhãn "còn nợ", nhãn đó chỉ dành cho API build chưa có route`,
        );

        const trung = daThay.get(cho);
        assert.equal(trung, undefined, `${luot.ten} hiện đúng câu mà ${trung} đã hiện`);
        daThay.set(cho, luot.ten);
      });
    }

    test("chín outcome đã đi qua, và chúng để lại chín câu khác nhau", () => {
      assert.equal(
        daThay.size,
        LUOT.length,
        `mới đo được ${daThay.size}/${LUOT.length} outcome; một ca ở trên đã đỏ`,
      );
    });

    /* --- bấm lúc nhóm chưa mở xong: không được đứng im ------------------- */

    test("bấm khi nhóm chưa mở xong thì nói ra, không đứng im", async () => {
      // Đo được bằng tay trước khi có bản vá: bấm trong cửa sổ nhóm đang tải
      // gửi ZERO request và vẽ ZERO chữ, kể cả nhãn "Đang hỏi…". Ca này dựng
      // lại cửa sổ đó một cách xác định bằng cách treo route của nhóm.
      await page.goto(server.url, (chu) => document.body.innerText.includes(chu), NUT_MO_SHEET);
      await page.evaluate(installTabStubs, API_BASE, taoFixtures());
      await page.evaluate(caiStubAiTurn);
      await page.evaluate(treoRouteNhom);
      await page.clickChu(NUT_MO_SHEET);
      await page.waitFor((chu) => document.body.innerText.includes(chu), { label: "sheet chọn người" }, TIEU_DE_SHEET);
      await page.clickLabel(CHON_MINH);
      await page.waitFor(() => document.querySelectorAll('[role="tab"]').length === 4, { label: "bốn tab của vỏ" });
      await page.clickLabel(TAB_TIN_NHAN);
      await page.waitFor((nhan) => !!document.querySelector(`[aria-label="${nhan}"]`), { label: "nút hỏi AI" }, NUT_HOI_AI);

      const soThanhVien = await page.evaluate(() => /\d+ thành viên/.test(document.body.innerText));
      assert.equal(soThanhVien, false, "nhóm đã mở xong; ca này không còn dựng được cửa sổ cần đo");

      await page.clickLabel(NUT_HOI_AI);
      await page.waitFor((c) => document.body.innerText.includes(c), { label: "câu nhóm chưa mở xong" }, CAU_NHOM_CHUA_MO_XONG);

      const than = await page.evaluate(docThan);
      assert.deepEqual(than, [], "bấm lúc nhóm chưa mở mà vẫn bắn lượt lên máy chủ");
    });

    /* --- câu chữ phải tự báo mình, không chỉ nằm im trong luồng ----------- */

    test("băng câu trả lời mang role=alert nên người đọc bằng tai cũng biết", async () => {
      await vaoChat();
      await page.evaluate(datTraLoi, {
        status: 200,
        body: { context_id: null, spoke: false, reason: "unavailable", message: null },
      });
      await page.clickLabel(NUT_HOI_AI);
      await page.waitFor((c) => document.body.innerText.includes(c), { label: "unavailable" }, CAU_THEO_LY_DO.unavailable);

      const vai = await page.evaluate((cau) => {
        const els = [...document.querySelectorAll('[role="alert"]')];
        return els.map((e) => (e.innerText || "").replace(/\s+/g, " ")).filter((t) => t.includes(cau));
      }, CAU_THEO_LY_DO.unavailable);
      console.log(`  [role=alert] chứa câu: ${vai.length}`);
      assert.equal(
        vai.length,
        1,
        "câu trả lời không nằm trong một vùng role=alert; màn im lặng đổi mà " +
          "trình đọc màn hình không đọc ra thì với người đó nút vẫn là nút chết",
      );
    });
  });
}
