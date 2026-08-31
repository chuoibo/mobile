/* Một cú bấm bị rơi thì máy lái bấm lại — nhưng chỉ khi bước đó xin phép.
 *
 * ## Lỗi có thật, đo được, không phải giả thuyết
 *
 * `duong-vao-mon-cua-toi.test.mjs` đỏ khoảng 1/10 lượt trên máy này — 2 lần
 * trong 20 lượt `node --test` đo liên tiếp cùng một SHA. Lượt đỏ in ra:
 *
 *     [nhịp] "mở Món của tôi": 17 bước, chờ lâu nhất 505ms
 *     het gio cho "Danh sách gửi lên thay hết món bạn nhận trước đó"
 *         sau 20038ms (ngan sach 20000ms)
 *     ms mỗi bước: [505,41,6,145,0,11,2,5,44,8,4,131,57,2,29,89,1]
 *
 * Bước cuối cùng chạy xong là `{"bamChu":"Món của tôi"}` và nó tốn **1ms**.
 * Mọi bước đều dưới 505ms, rồi màn đích không bao giờ tới. Đó không phải máy
 * chậm — nới ngân sách lên 60s cũng không cứu, vì cái màn ấy sẽ không tới nữa.
 * Đó là **một cú bấm bị rơi**: `el.click()` bắn đi rồi báo thành công ngay,
 * và máy lái không có cách nào phân biệt "đã bấm trúng" với "bấm xong không ai
 * nghe".
 *
 * ## Vì sao bấm lại phải là OPT-IN, không phải mặc định
 *
 * Bản đầu của bản sửa này bấm lại ở MỌI bước, và tự bảo vệ bằng một câu:
 * *"nút đã biến mất nghĩa là cú bấm đã ăn"*. Câu đó sai. Nút "Lưu", thanh tab,
 * nút toggle đều **ở lại** trong lúc việc đang bay, nên `bamDuoc()` vẫn trả về
 * element và điều kiện chặn không bao giờ thành lập. Đo ra: 2 trên 3 trang bị
 * gửi hai lần (#502 -> #504).
 *
 * Và cái guard ấy **không vá được**. So hàng NUỐT MỘT CÚ với hàng LƯU CHẬM ở
 * dưới: một bên nuốt cú bấm, một bên ĂN cú bấm nhưng màn đích còn 4 giây nữa
 * mới tới. Ở mốc 2500ms cả hai trình ra cho vòng `poll` **đúng một quan sát**:
 * nút còn gắn DOM, không disabled, handler đã chạy, chữ đích chưa có. Cùng một
 * quan sát, hai hành động đúng ngược nhau. Hàng CÙNG MỘT QUAN SÁT ở dưới đo
 * thẳng điều đó, để nó là số liệu chứ không phải lời giải thích.
 *
 * Thứ phân biệt được hai ca ấy không nằm trên trang: nó là "cú bấm này lặp lại
 * có an toàn không", và chỉ người viết kịch bản biết. Nên họ khai — `bamLai:
 * true` — còn mặc định là không bấm lại.
 *
 * ## Ca này đo được cái mà "chạy lại vài lượt" không đo được
 *
 * Lỗi thật chỉ hiện ~1/10 lượt, nên "chạy 8 lượt xanh" không chứng minh gì:
 * xác suất 8 lượt xanh liên tiếp khi chưa sửa gì đã là 43%. Ca này **ép** cú
 * bấm rơi, nên nó đỏ 100% ở bản chưa sửa và xanh 100% ở bản đã sửa.
 *
 * Nó không dựng app, không cần bundle expo, không cần server API. Nó chỉ dựng
 * đúng `laiTrongTrang` — thứ đang được sửa — trên trang HTML tự viết, với
 * `<button>` thật và `addEventListener("click")` thật, nên cái gì đỏ ở đây là
 * máy lái đỏ chứ không phải màn hình đỏ.
 *
 * Handler tự đếm số lần nó **thật sự chạy** (`window.__dem`). Đó là cú gửi,
 * không phải lời khai của máy lái về cú gửi: `bam_lai` rỗng mà `__dem` bằng 2
 * thì máy lái đang bấm ở chỗ nó không ghi.
 *
 * Chạy:
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/bam-truot-thi-bam-lai.test.mjs
 */
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { laiTrongTrang } from "../tools/quet-man-sau-tap.mjs";

const NHAN = "Đi tiếp";
const DICH = "Đã tới màn sau";

/** Trang một nút, và một quy tắc về việc nó nghe cú bấm thứ mấy.
 *
 *  `boQua` = số cú bấm đầu bị NUỐT (handler chạy nhưng không làm gì).
 *  `Infinity` là nút chết hẳn. `tre` = màn đích tới sau bao nhiêu ms kể từ cú
 *  bấm được ăn; `tre: 0` là tới ngay trong handler. `bienMat` = nút tự gỡ khi
 *  màn đích tới, tức đúng ca mà lập luận "nút biến mất nghĩa là đã ăn" cho là
 *  an toàn.
 *
 *  `window.__dem` đếm mọi lần handler chạy, kể cả lần bị nuốt. */
function trangNut({ boQua = 0, tre = 0, bienMat = false }, kichBan) {
  const datDich =
    'document.getElementById("d").textContent=' +
    JSON.stringify(DICH) +
    ";" +
    (bienMat ? 'var b=document.getElementById("n");if(b)b.remove();' : "");
  return (
    "<!doctype html><html><head><meta charset=utf-8>" +
    `<script>(${laiTrongTrang.toString()})(${JSON.stringify(kichBan)},null);<\/script>` +
    "</head><body>" +
    `<button id=n>${NHAN}</button><div id=d></div>` +
    "<script>window.__dem=0;var bo=" +
    (boQua === Infinity ? "Infinity" : String(boQua)) +
    ";document.getElementById('n').addEventListener('click',function(){" +
    "window.__dem++;if(window.__dem>bo){" +
    (tre === 0 ? datDich : "setTimeout(function(){" + datDich + "}," + String(tre) + ");") +
    "}});<\/script>" +
    "</body></html>"
  );
}

const chromeBin = findChrome();
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

if (!chromeBin && !REQUIRED) {
  test("bấm trượt thì bấm lại — BỎ QUA: no Chrome found", { skip: "no Chrome" }, () => {});
} else {
  describe("một cú bấm bị rơi, trên trang render thật", () => {
    let page;
    let server;
    let thuMuc;

    before(async () => {
      assert.ok(chromeBin, "MOBILE_REQUIRE_WEB_A11Y=1 nhưng không tìm thấy Chrome");
      thuMuc = mkdtempSync(join(tmpdir(), "bam-truot-"));
      server = await serve(thuMuc);
      page = await launch(chromeBin);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
      if (thuMuc) rmSync(thuMuc, { recursive: true, force: true });
    });

    /** Dựng trang, chạy máy lái trên đó, trả về `window.__lai` kèm số lần
     *  handler thật sự chạy. `xinBamLai` là thứ đang được đo: bước có khai
     *  `bamLai: true` hay không. */
    async function chay(ten, trang, { ms = 20000, xinBamLai = false } = {}) {
      const kichBan = [{ bamChu: NHAN, ...(xinBamLai ? { bamLai: true } : {}) }, { cho: DICH, ms }];
      writeFileSync(join(thuMuc, ten), trangNut(trang, kichBan));
      await page.viewport(390, 844);
      await page.goto(server.url + ten);
      await page.waitFor(() => !!(window.__lai && (window.__lai.xong || window.__lai.loi)), {
        timeout: 120000,
        label: `máy lái trên ${ten}`,
      });
      return page.evaluate(() => ({
        xong: window.__lai.xong,
        loi: window.__lai.loi,
        bam_lai: window.__lai.bam_lai,
        dem: window.__dem,
      }));
    }

    // ---- Ba hàng gốc: bấm lại CÓ khai thì vẫn cứu được cú bấm rơi ----

    test("NUỐT MỘT CÚ + bamLai: bấm rơi thì máy lái bấm lại và đi tiếp được", async () => {
      const lai = await chay("nuot-mot.html", { boQua: 1 }, { xinBamLai: true });

      assert.equal(lai.loi, null, `phải đi qua được, nhưng: ${lai.loi}`);
      assert.equal(lai.xong, true, "máy lái chưa xong");
      // Đúng MỘT lần bấm lại. Nhiều hơn nghĩa là nó bấm cả sau khi đã tới nơi.
      assert.equal(
        lai.bam_lai.length,
        1,
        `phải bấm lại đúng 1 lần, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      assert.equal(lai.bam_lai[0].cho, DICH);
      console.log(`  [nuốt một] cứu được, bấm lại ${lai.bam_lai.length} lần`);
    });

    test("NÚT CHẾT + bamLai: bấm lại KHÔNG biến một lỗi thật thành dấu xanh", async () => {
      const lai = await chay("nut-chet.html", { boQua: Infinity }, { ms: 8000, xinBamLai: true });

      assert.equal(lai.xong, false, "nút chết mà máy lái báo xong — bản sửa đang che lỗi");
      assert.match(
        String(lai.loi),
        /het gio cho/,
        `phải chết vì hết giờ chờ, thực tế: ${lai.loi}`,
      );
      // Đã thử lại đủ số lần rồi mới bỏ cuộc, chứ không phải chưa thử đã đỏ.
      assert.equal(
        lai.bam_lai.length,
        2,
        `phải thử lại 2 lần rồi mới bỏ, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      console.log(`  [nút chết] vẫn đỏ đúng như phải thế, đã thử ${lai.bam_lai.length} lần`);
    });

    test("NÚT TỐT + bamLai: ăn ngay cú đầu thì KHÔNG bấm lần nào nữa", async () => {
      const lai = await chay("nut-tot.html", { boQua: 0 }, { xinBamLai: true });

      assert.equal(lai.loi, null, `phải đi qua được, nhưng: ${lai.loi}`);
      assert.equal(lai.xong, true, "máy lái chưa xong");
      assert.deepEqual(
        lai.bam_lai,
        [],
        `màn tới ngay thì không có gì để bấm lại, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      assert.equal(lai.dem, 1, `handler phải chạy đúng 1 lần, thực tế ${lai.dem}`);
      console.log("  [nút tốt] không bấm lại lần nào");
    });

    // ---- Hàng hồi quy của #502: cú bấm ĐÃ ĂN, màn đích tới CHẬM ----
    //
    // Hàng NÚT TỐT ở trên đặt chữ đích NGAY trong handler, nên `cho()` giải
    // quyết ở vòng poll đầu và không bao giờ chạm mốc 2500ms. Tức nó chứng minh
    // "màn tới trong 2500ms", không chứng minh "bấm trúng thì không bấm lại".
    // Hàng dưới đây mới chứng minh câu thứ hai.

    test("LƯU CHẬM, mặc định: cú bấm đã ăn thì KHÔNG bao giờ gửi lần hai", async () => {
      // 4000ms > NHIP_BAM_LAI = 2500ms: đúng cửa sổ mà bản #502 bấm lại.
      const lai = await chay("luu-cham.html", { boQua: 0, tre: 4000 });

      assert.equal(lai.loi, null, `phải đi qua được, nhưng: ${lai.loi}`);
      assert.equal(lai.xong, true, "máy lái chưa xong");
      // Đây là ca chặn "Lưu" bị gửi hai lần. Đo cú gửi, không đo lời khai.
      assert.equal(
        lai.dem,
        1,
        `nút "Lưu" phải được gửi đúng 1 lần, thực tế ${lai.dem} lần ` +
          `(bam_lai: ${JSON.stringify(lai.bam_lai)})`,
      );
      assert.deepEqual(lai.bam_lai, [], "mặc định không được bấm lại");
      console.log(`  [lưu chậm] màn đích 4000ms, handler chạy ${lai.dem} lần`);
    });

    test("LƯU CHẬM + nút TỰ GỠ khi màn tới: vẫn không gửi lần hai", async () => {
      // Ca mà lập luận cũ cho là an toàn nhất ("nút biến mất nghĩa là đã ăn").
      // Nút chỉ biến mất LÚC màn đích tới; cửa sổ đang-bay trước đó vẫn còn nút.
      const lai = await chay("luu-cham-bien-mat.html", { boQua: 0, tre: 4000, bienMat: true });

      assert.equal(lai.loi, null, `phải đi qua được, nhưng: ${lai.loi}`);
      assert.equal(
        lai.dem,
        1,
        `nút tự gỡ cũng phải được gửi đúng 1 lần, thực tế ${lai.dem} lần`,
      );
      console.log(`  [lưu chậm + tự gỡ] handler chạy ${lai.dem} lần`);
    });

    // ---- Hai hàng giữ cho "opt-in" là opt-in thật ----

    test("MẶC ĐỊNH TẮT: không khai bamLai thì cú bấm rơi KHÔNG được cứu", async () => {
      // Đối chứng của hàng NUỐT MỘT CÚ: cùng trang, chỉ bỏ `bamLai`. Nếu hàng
      // này xanh (được cứu) thì cờ kia là đồ trang trí và mặc định vẫn là bấm
      // lại — tức lỗ #502 còn nguyên, chỉ đổi tên.
      const lai = await chay("nuot-mot-khong-khai.html", { boQua: 1 }, { ms: 8000 });

      assert.equal(lai.xong, false, "không khai bamLai mà vẫn được bấm lại — cờ không có tác dụng");
      assert.match(String(lai.loi), /het gio cho/, `phải hết giờ chờ, thực tế: ${lai.loi}`);
      assert.deepEqual(
        lai.bam_lai,
        [],
        `không khai thì không được bấm lại lần nào, thực tế: ${JSON.stringify(lai.bam_lai)}`,
      );
      assert.equal(lai.dem, 1, `handler chỉ được chạy 1 lần, thực tế ${lai.dem}`);
      console.log("  [mặc định tắt] không cứu, và không bấm lén lần nào");
    });

    test("CÙNG MỘT QUAN SÁT: nuốt-cú-bấm và ăn-nhưng-chậm không phân biệt được", async () => {
      // Hàng này ghim lý do bấm lại phải là opt-in, thay vì để nó nằm trong
      // comment. Hai trang khác nhau ở chỗ handler LÀM GÌ, nhưng ở mốc quyết
      // định (2500ms) chúng trình ra cho máy lái đúng một trạng thái. Ai muốn
      // thay `bamLai` bằng một phép kiểm trên trang sẽ phải làm hàng này đỏ
      // trước — và phép kiểm ấy phải đọc được thứ không có ở đây.
      const quanSat = async (ten, trang) => {
        writeFileSync(join(thuMuc, ten), trangNut(trang, []));
        await page.viewport(390, 844);
        await page.goto(server.url + ten);
        return page.evaluate(async () => {
          const nut = document.getElementById("n");
          nut.click();
          await new Promise((r) => setTimeout(r, 2500));
          const n = document.getElementById("n");
          return {
            conGanDom: !!(n && n.isConnected),
            tat: !!(n && (n.disabled || n.getAttribute("aria-disabled") === "true")),
            handlerDaChay: window.__dem > 0,
            thayChuDich: (document.body.innerText || "").includes("Đã tới màn sau"),
          };
        });
      };

      const nuot = await quanSat("qs-nuot.html", { boQua: 1 });
      const cham = await quanSat("qs-cham.html", { boQua: 0, tre: 4000 });

      assert.deepEqual(
        nuot,
        cham,
        "hai ca này phân biệt được từ trên trang — nếu vậy thì bấm lại có thể " +
          `tự quyết, không cần khai. nuốt=${JSON.stringify(nuot)} chậm=${JSON.stringify(cham)}`,
      );
      // Và trạng thái chung ấy đúng là trạng thái mà bản #502 đọc thành "bấm lại đi".
      assert.equal(nuot.conGanDom, true, "nút phải còn gắn DOM ở cả hai ca");
      assert.equal(nuot.tat, false, "nút phải còn bấm được ở cả hai ca");
      assert.equal(nuot.thayChuDich, false, "chữ đích chưa tới ở cả hai ca");
      console.log(`  [cùng một quan sát] ${JSON.stringify(nuot)}`);
    });

    // ---- Cái giá của opt-in, nói thẳng bằng số ----

    test("GIÁ CỦA bamLai: khai rồi thì màn chậm VẪN bị bấm hai lần", async () => {
      // Không phải lỗi — là cái giá, và nó phải đọc được ở đây chứ không phải
      // chỉ trong comment. `bamLai: true` nghĩa là "cú bấm này lặp lại vô hại".
      // Khai nó lên một nút ghi (POST) là gửi hai lần, và hàng này là chỗ con
      // số ấy hiện ra thay vì nằm im.
      const lai = await chay("luu-cham-co-khai.html", { boQua: 0, tre: 4000 }, { xinBamLai: true });

      assert.equal(lai.dem, 2, `khai bamLai trên màn chậm thì gửi 2 lần, thực tế ${lai.dem}`);
      assert.equal(lai.bam_lai.length, 1, "và lần bấm thừa đó phải được ghi lại, không im lặng");
      console.log(
        `  [giá của bamLai] gửi ${lai.dem} lần — nên chỉ khai trên cú bấm lặp lại được`,
      );
    });
  });
}
