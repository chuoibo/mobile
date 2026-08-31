/* "Món của tôi" là một màn có người bấm tới được, và nút Lưu gửi thật lên server.
 *
 * F22 self-tagging đã có đủ hai đầu từ lâu và chưa bao giờ nối lại với nhau:
 * `POST /bills/{id}/my-items` có route, có service, có test backend; `MonCuaToi`
 * có file, có 192 dòng, có `?man=mon-cua-toi` để máy quét mở ra chụp ảnh. Ở
 * giữa không có gì. Đo tại d00c21b, đếm tham chiếu `nhanMonCuaToi` NGOÀI
 * `api.ts` trong `apps/mobile/src` + `App.tsx` ra **0**, và cửa quét mount màn
 * đó với `onLuu={() => {}}`.
 *
 * ## Vì sao ba cổng đang xanh không ai thấy
 *
 *   - `check_server_routes_called.py` đếm `/bills/{id}/my-items` là "có người
 *     gọi", vì wrapper trong `api.ts` là một lời gọi. Wrapper không ai gọi vẫn
 *     là wrapper.
 *   - `check_screens_reachable.py` đếm `MonCuaToi` là "tới được", vì cửa quét
 *     `?man=` render nó. Cửa quét cố ý trơ — callback là no-op — nên nó chứng
 *     minh màn VẼ ĐƯỢC, không chứng minh có đường bấm.
 *   - Đếm tên: `grep -c MonCuaToi` ra 2 (một import, một thẻ JSX) dù không nút
 *     nào dẫn tới. Đây đúng hình dạng `duong-vao-chi-tiet-dia-diem.test.mjs`
 *     mô tả: đường đi qua prop callback thì grep tên không nhìn thấy.
 *
 * Nên file này hỏi đúng cái ba cổng kia không hỏi: đi bộ đường hero thật trong
 * Chrome thật, bấm cái nút một người nhìn thấy, tới đúng màn, tích một món,
 * bấm Lưu, và **mở lại** để xem server có giữ không.
 *
 * ## Vì sao phải MỞ LẠI mới là bằng chứng
 *
 * Nếu chỉ khẳng định "bấm Lưu rồi về được goi-y" thì `onLuu={() => {}}` cũng
 * xanh: về được không có nghĩa là đã gửi. Lần mở thứ hai seed ô tích từ
 * `bill.items[].shares` do server trả về (`monToiDaNhan`), nên "Phần của bạn:
 * 280.000đ" ở lần mở thứ hai chỉ đúng khi POST đã thật sự đi và câu trả lời
 * đã được giữ lại. Đó là ca giết được đột biến no-op.
 *
 * Chứng minh: nút tồn tại, bấm được, dẫn đúng màn, và vòng ghi-đọc qua stub
 * API đi trọn. KHÔNG chứng minh: server thật lưu đúng (đó là test backend của
 * `claim_bill_items`), màn này dễ đọc hay tương phản đạt (đó là detector và
 * `accessibility-testing`), hay chuyện gì xảy ra khi POST lỗi.
 *
 * Chạy từ apps/mobile, trên bản dựng tự tay dựng:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/duong-vao-mon-cua-toi.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { MAN_SAU_TAP, trangTuLai } from "../tools/quet-man-sau-tap.mjs";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

const RONG = 390;
const CAO = 844;

/** Người đăng nhập trong kịch bản đi bộ, và cũng là người phải có mặt trên
 *  bill trước khi nút mở được — `khoaMonCuaToi` từ chối mở khi tôi chưa ở trên
 *  bill, vì ma trận vẽ cột theo roster nên cái nhận sẽ vô hình. */
const TOI = "Minh";

/** Món được GIỮ lại; hai món kia bị bỏ tích.
 *
 *  Bỏ tích chứ không phải thêm, vì đó là nửa khó của hợp đồng: body là TẬP ĐẦY
 *  ĐỦ của người gọi, nên nhả món ra chỉ hoạt động khi bên gửi thật sự gửi danh
 *  sách rút gọn và bên nhận thật sự xoá phần dư. Một stub chỉ biết THÊM, hoặc
 *  một màn gửi nguyên tập cũ, đều xanh nếu ca này chỉ đi thêm món.
 *
 *  Ba con số phân biệt được nhau: 480.000đ là cả bill (chưa gửi gì / gửi
 *  nguyên tập cũ), 280.000đ là đúng một món, 0đ là gửi tập rỗng. */
const MON_GIU = "Lẩu thái";
const BO_TICH = ["Nước sâm, 2 phần, 50.000đ, đã chọn", "Cơm rang, 150.000đ, đã chọn"];
const NHAN_MON_DA_CHON = "Lẩu thái, 280.000đ, đã chọn";
const PHAN_CA_BILL = "Phần của bạn: 480.000đ";
const PHAN_MOT_MON = "Phần của bạn: 280.000đ";

/** Câu chỉ màn `MonCuaToi` in ra. Không dùng tiêu đề "Món của tôi" làm needle:
 *  nhãn nút trên `goi-y` cũng là đúng chuỗi đó, nên needle ấy đọc là true khi
 *  còn đang đứng ở màn trước. */
const NEEDLE = "Danh sách gửi lên thay hết món bạn nhận trước đó";

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
  test(`đường vào Món của tôi — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("đường vào Món của tôi, trên trang render thật", () => {
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

    /** Chạy một kịch bản đi bộ, dùng đúng đường tiêm mà các probe QA dùng. */
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
      const lai = await page.evaluate(() => ({
        xong: window.__lai.xong,
        loi: window.__lai.loi,
        buoc: window.__lai.buoc,
        ms: window.__lai.ms,
        cho_ms: window.__lai.cho_ms,
        luc_loi: window.__lai.luc_loi ?? null,
      }));
      // Printed on every run, pass or fail. A per-step budget can only be
      // called too tight or about right by looking at the margin on the runs
      // that PASSED, and those numbers do not exist unless somebody prints
      // them. The slowest wait is the one the budget is really sized against.
      const chamNhat = lai.cho_ms.length ? Math.max(...lai.cho_ms) : 0;
      console.log(
        `  [nhịp] "${nhan}": ${lai.ms.length} bước, chờ lâu nhất ${chamNhat}ms, ` +
          `tổng ${lai.ms.reduce((a, b) => a + b, 0)}ms`,
      );
      assert.equal(
        lai.loi,
        null,
        `kịch bản đi bộ "${nhan}" HỎNG: ${lai.loi}\n` +
          `  đã qua ${lai.buoc.length} bước: ${JSON.stringify(lai.buoc)}\n` +
          `  ms mỗi bước: ${JSON.stringify(lai.ms)}\n` +
          `  ms mỗi lần chờ: ${JSON.stringify(lai.cho_ms)}\n` +
          `  màn lúc chết: ${JSON.stringify(lai.luc_loi)}`,
      );
      assert.equal(lai.xong, true, `kịch bản đi bộ "${nhan}" chưa xong`);
    }

    function denGoiY() {
      const man = MAN_SAU_TAP.find((m) => m.step === "goi-y");
      assert.ok(man, 'không có màn "goi-y" trong MAN_SAU_TAP');
      return [
        ...man.kichBan,
        // Thêm tôi vào bill. Hai việc cùng lúc, và cả hai đều cần: `khoaMonCuaToi`
        // từ chối mở khi tôi chưa có trên bill, và đây cũng là chỗ `POST /bills`
        // thật sự chạy trên đường demo -- "Tiếp tục" bỏ qua nó vì lúc ấy roster
        // còn rỗng.
        { themNguoi: TOI },
        // Chờ bill đã lưu xong. Không có chặng này thì cú bấm dưới đây là một
        // cuộc đua với `POST /bills`, và một lần thua sẽ đọc thành "nút hỏng".
        { cho: "Máy đoán sẵn" },
      ];
    }

    const MO_MON_CUA_TOI = [
      ...denGoiY(),
      { bamChu: "Món của tôi" },
      { cho: NEEDLE },
    ];

    test("nút trên goi-y dẫn tới đúng màn Món của tôi", async () => {
      await diBo("__mon-cua-toi-mo.html", MO_MON_CUA_TOI, "mở Món của tôi");

      const chu = await page.evaluate(() => document.body.innerText || "");
      assert.ok(chu.includes(NEEDLE), `mở xong nhưng không thấy "${NEEDLE}" — đang đo màn khác`);
      // Ba món của bill fixture phải có mặt, nếu không thì "không món nào ẩn"
      // sẽ đọc y hệt "màn trống".
      for (const ten of ["Lẩu thái", "Nước sâm", "Cơm rang"]) {
        assert.ok(chu.includes(ten), `màn Món của tôi thiếu món "${ten}"`);
      }
      // Ô tích được seed TỪ BILL SERVER TRẢ VỀ, không phải từ một mảng rỗng.
      // Thêm Minh vào bill đặt anh ấy lên mọi món (mặc định "cả nhóm ăn
      // chung"), `POST /bills` ghi đúng thế, và màn này đọc lại đúng thế.
      assert.ok(
        chu.includes(PHAN_CA_BILL),
        `mở lần đầu phải là "${PHAN_CA_BILL}" (seed từ bill), ` +
          `nhưng màn in: ${JSON.stringify(chu.slice(0, 400))}`,
      );
      console.log(`  [mở] thấy 3 món, ${PHAN_CA_BILL}`);
    });

    test("bỏ tích hai món rồi Lưu thì server nhả ra, và lần mở sau đọc lại được", async () => {
      const kichBan = [
        ...MO_MON_CUA_TOI,
        ...BO_TICH.map((nhan) => ({ bam: nhan })),
        // Ô đã đổi trạng thái TRƯỚC khi bấm Lưu. Không có chặng này thì một cú
        // bấm trượt sẽ gửi nguyên tập cũ và bài đo bên dưới đổ cho nút Lưu.
        { cho: PHAN_MOT_MON },
        { bamChu: "Lưu món của tôi" },
        // Về lại màn gợi ý: `onXong` đưa bước về "goi-y".
        { cho: "Gợi ý chia theo người" },
        // Mở lại. Lần này ô tích phải được seed từ bill SERVER VỪA TRẢ VỀ, nên
        // đây là chặng giết được đột biến `onLuu={() => {}}`: không gửi thì
        // `bill` không đổi, và màn mở lại vẫn là 480.000đ.
        { bamChu: "Món của tôi" },
        { cho: NEEDLE },
      ];
      await diBo("__mon-cua-toi-luu.html", kichBan, "bỏ tích, lưu, mở lại");

      const chu = await page.evaluate(() => document.body.innerText || "");
      assert.ok(
        chu.includes(PHAN_MOT_MON),
        `mở lại phải thấy "${PHAN_MOT_MON}" (server chỉ còn giữ ${MON_GIU}), ` +
          `nhưng màn in: ${JSON.stringify(chu.slice(0, 400))}`,
      );

      // Và đúng MỘT ô còn tích, trên đúng món đã giữ. Con số tiền một mình
      // không đủ: nó cũng đúng nếu server nhả nhầm món và giữ một món khác
      // cùng giá, và ở đây không có hai món cùng giá thì mai có.
      const daChon = await page.evaluate(() =>
        [...document.querySelectorAll('[role="checkbox"]')]
          .filter((n) => n.getAttribute("aria-checked") === "true")
          .map((n) => n.getAttribute("aria-label")),
      );
      assert.deepEqual(
        daChon,
        [NHAN_MON_DA_CHON],
        `sau khi mở lại phải còn đúng ô "${NHAN_MON_DA_CHON}", đang tích: ${JSON.stringify(daChon)}`,
      );
      console.log(`  [bỏ tích→lưu→mở lại] ${PHAN_MOT_MON}, còn đúng ô "${MON_GIU}"`);
    });

    /* Cái nhận phải chạm được vào ma trận của màn gợi ý, không chỉ vào server.
     *
     * Ca này tồn tại vì hai ca trên KHÔNG bắt được nó. Đo bằng đột biến: cho
     * `apDungMonCuaToi` trả nguyên ma trận cũ -- đúng cái lỗi hàm đó sinh ra để
     * chặn -- và cả hai ca trên vẫn 2 pass / 0 fail. Chúng chỉ nhìn màn
     * `MonCuaToi`, mà màn ấy seed từ `bill`, còn `bill` thì đã được cập nhật
     * đúng. Ma trận là chỗ duy nhất chênh lệch lộ ra.
     *
     * Vì sao chênh lệch đó là lỗi tiền chứ không phải lỗi hiển thị: `onSeeResults`
     * ghi ma trận CỤC BỘ đè lên cả tờ bill bằng `PUT /bills/{id}/assignments`.
     * Cái nhận không vào được ma trận là cái nhận bị cú bấm kế tiếp xoá -- sau
     * khi màn đã nói với người ta là đã lưu. */
    test("cái vừa nhận đi vào ma trận goi-y, nên Xem kết quả không xoá mất nó", async () => {
      const kichBan = [
        ...MO_MON_CUA_TOI,
        ...BO_TICH.map((nhan) => ({ bam: nhan })),
        { cho: PHAN_MOT_MON },
        { bamChu: "Lưu món của tôi" },
        { cho: "Gợi ý chia theo người" },
      ];
      await diBo("__mon-cua-toi-ma-tran.html", kichBan, "lưu rồi về ma trận");

      const oCuaToi = await page.evaluate((toi) =>
        [...document.querySelectorAll('[role="checkbox"]')]
          .map((n) => ({
            nhan: n.getAttribute("aria-label"),
            tich: n.getAttribute("aria-checked") === "true",
          }))
          .filter((o) => (o.nhan ?? "").startsWith(toi + ", ")),
        TOI,
      );

      // Ba món, ba ô của tôi. Không có chốt này thì "không ô nào còn tích" đọc
      // y hệt "không tìm thấy ô nào".
      assert.equal(oCuaToi.length, 3, `phải thấy 3 ô của ${TOI} trên ma trận, thấy ${oCuaToi.length}`);
      const conTich = oCuaToi.filter((o) => o.tich).map((o) => o.nhan);
      assert.deepEqual(
        conTich,
        [`${TOI}, ${MON_GIU}`],
        `ma trận phải còn đúng ô "${TOI}, ${MON_GIU}" — hai món đã nhả ra vẫn đang tích: ` +
          JSON.stringify(oCuaToi),
      );
      console.log(`  [ma trận sau khi lưu] ${TOI} còn đúng 1 ô: ${conTich[0]}`);
    });
  });
}
