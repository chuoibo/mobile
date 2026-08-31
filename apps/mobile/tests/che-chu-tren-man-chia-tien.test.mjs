/* Màn chia tiền sinh ra cảnh báo `text-occlusion`, và chúng là ARTEFACT — nhưng
 * cổng vẫn phải kết tội được một ca che thật trên chính màn đó.
 *
 * ## Vì sao file này tồn tại
 *
 * Đo trên bản dựng của cây này, ở 390x844, cửa quét `?man=goi-y-chia`:
 * `imp detect` trả về 3 finding `text-occlusion`, trong đó có
 *
 *     div.css-146c3p1 "90.000" is 100% covered by an opaque element (div.css-g5y9jx)
 *
 * Không có chữ nào bị che. Cả ba đều là hàng món nằm TRỌN DƯỚI mép cắt của vùng
 * cuộn ma trận (`#vung-cuon-ma-tran`: nội dung 732pt trong cửa sổ 365pt). Trình
 * duyệt không vẽ chúng ở toạ độ đó; thứ được vẽ ở đó là dải "Đã nhận diện 8 món"
 * và nút chân màn. Cuộn vùng cuộn tới cuối thì "Bia Sài Gòn" chạy từ y=653 lên
 * y=286, nằm trong khung 267..632, và đọc được nguyên vẹn.
 *
 * Luật của detector so hộp thô bằng `elementFromPoint` và KHÔNG có phép thử cắt.
 * Tái lập được trên một trang tổng hợp không hề có gì bị che: một vùng cuộn cao
 * 120px giữ 8 hàng, dưới nó là một dải đặc, ra 5 finding, trong đó
 * `"Bia Sai Gon 90.000" is 100% covered` — đúng hình dạng của finding sản phẩm.
 *
 * `tools/che-chu.mjs` đã có sẵn phép phân xử cho đúng lớp lỗi này (`cuon-khuat`
 * so với `that`), và `tests/che-chu.test.mjs` chứng minh nó chạy đúng TRÊN TRANG
 * TỔNG HỢP. Cái chưa ai làm: chạy nó trên MÀN TIỀN THẬT, với chính những lời tố
 * mà màn này sinh ra. Đó là khoảng trống file này lấp.
 *
 * ## Vì sao nó đáng là một cổng, không chỉ một ghi chú
 *
 * Ba cảnh báo artefact đứng thường trực trên màn hero là một cái cổng mù đang
 * hình thành: finding thứ tư — một finding THẬT — sẽ tới trong một danh sách mà
 * người đọc đã quen vẫy tay cho qua. Nên file này không chỉ khai "ba cái kia là
 * nhiễu"; nó giữ luôn phép thử ngược, rằng trên CHÍNH màn này phép phân xử vẫn
 * nói được "that" khi có vật thật đè lên một con số tiền.
 *
 * ## CHỨNG MINH
 *
 * Trên bản dựng ở `MOBILE_WEB_EXPORT`, ở 390x844, trong Chrome này:
 *   1. tiền đề còn đúng — vùng cuộn giữ nhiều hơn cửa sổ, VÀ có ít nhất một hàng
 *      chữ nằm trọn dưới mép (danh sách rỗng thì mọi khẳng định sau đều xanh vì
 *      không có gì để xét, nên nó được assert chứ không được suy);
 *   2. mọi hàng dưới mép đó được `phanLoai` xếp là KHÔNG phải lỗi, VÀ lời tha đó
 *      tới từ phép nhìn (đa số điểm mẫu có chính chữ ở trên cùng) chứ không từ
 *      cái nhãn `to-cha`. Đo được: trên màn này verdict trả về là `to-cha`, vì
 *      react-native-web gộp style giống nhau vào chung một atomic class nên
 *      selector detector in ra khớp luôn tổ tiên của chữ — đúng lối tắt
 *      `che-chu.mjs` đã gỡ bỏ. Nhãn khác nhau, lời tha vẫn phải tự đứng được;
 *   3. một con số tiền đang đọc được, trên cùng trang, được xếp là KHÔNG phải lỗi
 *      TRƯỚC khi che, và là `that` SAU khi bị một tấm đặc phủ lên.
 *
 * Cặp trước/sau ở (3) mới là thứ làm (2) có nghĩa. Thiếu nó thì một `phanLoai`
 * hỏng theo hướng "luôn tha" cũng in ra đúng bảng xanh này.
 *
 * ## KHÔNG CHỨNG MINH
 *
 * - Không chạy `imp detect`. Detector nằm ngoài repo, nên một ca gọi nó sẽ cho
 *   hai phán quyết khác nhau ở cùng một SHA tuỳ máy. Lời tố ở đây được DỰNG LẠI
 *   từ chính trang (chữ thật + phần tử thật đang được vẽ ở đó), đúng định dạng
 *   `docSnippet` đọc. Nó mô phỏng lời tố, không phải là bằng chứng rằng detector
 *   hôm nay vẫn tố đúng ba cái đó.
 * - Không nói vùng cuộn có cuộn được BẰNG NGÓN TAY trên Android/iOS không.
 *   `mon-tren-goi-y.test.mjs` hỏi câu bên cạnh: hàng có nằm trong khung ở lần vẽ
 *   đầu không. Cả hai đều đo React Native Web trong Chrome.
 * - KHÔNG quét cả màn để tìm ca che THẬT. Ca 2 chỉ xét những hàng nằm dưới mép
 *   vùng cuộn — đúng lớp artefact. Một vật đè lên chữ ở chỗ khác trên màn này sẽ
 *   đi lọt qua file này; ca 3-4 chứng minh phép phân xử còn kết tội được, không
 *   chứng minh rằng không còn gì để kết tội.
 * - Không nói màn đẹp, dễ hiểu, hay 8 món đều tới được bằng một cú vuốt.
 *
 * Chạy từ `apps/mobile`, trên bản dựng bạn tự tạo:
 *
 *     npm run build:check
 *     MOBILE_REQUIRE_WEB_A11Y=1 node --test tests/che-chu-tren-man-chia-tien.test.mjs
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { laLoiThat, phanLoai } from "../tools/che-chu.mjs";
import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** Cái điện thoại con số này được đo trên. Lỗi phụ thuộc chiều cao, nên đây
 *  không phải chi tiết khái quát hoá đi được. */
const RONG = 390;
const CAO = 844;

/** nativeID vùng cuộn ma trận, khớp `VUNG_CUON_MA_TRAN` trong `GoiYChia.tsx`.
 *  Đọc bằng id chứ không bằng class: react-native-web băm class và được phép
 *  đổi chúng bất cứ lúc nào. */
const VUNG_CUON = "vung-cuon-ma-tran";

/** Con số tiền dùng cho phép thử ngược. Nó đang ĐỌC ĐƯỢC ở trạng thái này —
 *  ca đầu của cặp trước/sau khẳng định đúng điều đó trước khi che nó đi. */
const SO_TIEN_DOC_DUOC = "450.000";

const NEEDLE = "Gợi ý chia theo người";

/* ------------------------------------------------- phép đo, chạy trong trang --- */

/**
 * Mọi hàng chữ lá nằm TRỌN dưới mép cắt của vùng cuộn, kèm phần tử đang thực sự
 * được vẽ ở toạ độ đó.
 *
 * Đây chính là hình dạng detector đọc nhầm thành "bị che": hộp của hàng vẫn nằm
 * ở toạ độ cũ sau khi nội dung tràn khỏi cửa sổ, và thứ được vẽ ở đó là một phần
 * tử khác. Trả về đủ để dựng lại lời tố, để ca dưới không phải viết tay chuỗi
 * nào — một chuỗi viết tay sẽ hết đúng lặng lẽ khi fixture đổi.
 */
function doHangDuoiMep(id) {
  const sc = document.getElementById(id);
  if (!sc) return { co: false };
  const r = sc.getBoundingClientRect();
  const mep = r.y + r.height;
  const hang = [];
  for (const e of sc.querySelectorAll("div,span")) {
    if (e.children.length > 0) continue;
    const chu = (e.textContent ?? "").trim();
    if (chu.length < 2) continue;
    const q = e.getBoundingClientRect();
    if (q.height < 6 || q.width < 6) continue;
    if (q.top < mep) continue;
    const top = document.elementFromPoint(q.left + q.width / 2, q.top + q.height / 2);
    if (!top) continue;
    // Tổ tiên đang được vẽ ở đó nghĩa là hộp của chính hàng, không phải một
    // vật lạ đè lên. Detector cũng bỏ qua ca này, nên nó không nằm trong lớp
    // artefact file này khai.
    if (top.contains(e) || e.contains(top)) continue;
    hang.push({
      chu: chu.slice(0, 24),
      y: Math.round(q.y),
      tren:
        top.tagName.toLowerCase() +
        (top.className ? "." + String(top.className).trim().split(/\s+/).join(".") : ""),
    });
  }
  return {
    co: true,
    khung: { y: Math.round(r.y), mep: Math.round(mep) },
    noiDung: Math.round(sc.scrollHeight),
    cuaSo: Math.round(sc.clientHeight),
    hang,
  };
}

/** Một tấm đặc, `position: fixed`, phủ đúng dải giữa khung nhìn — nơi
 *  `scrollIntoView({block:"center"})` của `che-chu.mjs` đưa chữ tới. Cố định chứ
 *  không tuyệt đối, để phép che không trượt khi phép phân xử cuộn trang. */
function datTamChe() {
  const d = document.createElement("div");
  d.id = "__tam-che-thu";
  d.style.cssText =
    // z-index 999999, không phải giá trị max của int32: repo guard đọc một dãy
    // 10 chữ số là số tài khoản và chặn commit. Sáu chữ số vẫn nằm trên mọi lớp
    // của màn này, đối chứng DƯƠNG dưới đây chứng minh điều đó.
    "position:fixed;left:0;right:0;top:35%;height:30%;background:#0f766e;z-index:999999";
  document.body.appendChild(d);
  return true;
}

function goTamChe() {
  document.getElementById("__tam-che-thu")?.remove();
  return true;
}

/* ---------------------------------------------------------------------- cổng --- */

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`không có bản web export ở ${EXPORT_DIR} (chạy: npm run build:check)`);
}
if (!chromeBin) reasons.push("không tìm thấy Chrome (đặt CHROME_BIN, hoặc cài qua playwright)");

// bug-010019. Cổng này đo một bản dựng sẵn và không mở file nguồn nào, nên một
// bản dựng cũ hơn cây sẽ khiến nó phán về một màn mà commit này chưa từng dựng.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`che chữ trên màn chia tiền — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("che chữ trên màn chia tiền, đo trên trang render thật", () => {
    let page;
    let server;
    let doDuoc;

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      await page.viewport(RONG, CAO);
      await page.goto(`${server.url}index.html?man=goi-y-chia`);
      await page.waitFor(
        (n) => (document.body?.innerText ?? "").includes(n),
        { timeout: 60000, label: `màn "${NEEDLE}"` },
        NEEDLE,
      );
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
      // Đợi khung yên trước khi đo. Needle chỉ nói chữ đã có trong DOM; ma trận
      // còn giãn thêm một nhịp sau đó, và đo giữa nhịp đó cho ra một TẬP HÀNG
      // khác nhau giữa hai lần chạy (đã thấy 9 rồi 6). Số ca sẽ không đỏ vì thế,
      // nhưng phạm vi phủ sẽ lặng lẽ co lại — nên chờ đúng điều kiện tiền đề.
      await page.waitFor(
        (id) => {
          const sc = document.getElementById(id);
          return !!sc && sc.scrollHeight > sc.clientHeight + 20;
        },
        { timeout: 60000, label: `vùng cuộn #${VUNG_CUON} giãn xong` },
        VUNG_CUON,
      );
      doDuoc = await page.evaluate(doHangDuoiMep, VUNG_CUON);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
    });

    /* --- 1. tiền đề: cái hình dạng này còn tồn tại trên bản dựng hôm nay --- */

    test("tiền đề: vùng cuộn giữ nhiều hơn cửa sổ, và CÓ hàng nằm dưới mép", () => {
      assert.ok(doDuoc.co, `không tìm thấy vùng cuộn ma trận (#${VUNG_CUON})`);
      console.log(
        `  khung cuộn y=${doDuoc.khung.y} mép=${doDuoc.khung.mep}, ` +
          `nội dung ${doDuoc.noiDung}pt trong cửa sổ ${doDuoc.cuaSo}pt`,
      );
      assert.ok(
        doDuoc.noiDung > doDuoc.cuaSo,
        `vùng cuộn giữ ${doDuoc.noiDung}pt trong ${doDuoc.cuaSo}pt — không có gì tràn ra, ` +
          "nên lớp artefact file này khai đã không còn tồn tại. Đọc lại phần đầu file " +
          "trước khi xoá nó: có thể màn đã đổi, cũng có thể phép đo đã gãy.",
      );
      console.log(`  hàng nằm dưới mép: ${doDuoc.hang.length}`);
      assert.ok(
        doDuoc.hang.length >= 1,
        "không hàng chữ nào nằm dưới mép vùng cuộn. Ca dưới sẽ xanh vì tập rỗng " +
          "chứ không phải vì phán xử đúng, nên nó phải đỏ ở đây trước.",
      );
      // Sàn, không phải lời khai về fixture. Đo lặp 3 lần ra 9/9/6: ba nhãn đếm
      // tích ("4/4", "2/4", "1/4") lúc có lúc không, tuỳ phần tử nào đang được
      // vẽ ở tâm hộp của chúng sau khi bố cục chốt ở mức dưới điểm ảnh. Sáu hàng
      // món (3 tên + 3 giá) thì ổn định. Sàn 4 để một phép đo co lại gần hết vẫn
      // đỏ, thay vì lặng lẽ chỉ còn phủ một hàng.
      assert.ok(
        doDuoc.hang.length >= 4,
        `chỉ tìm thấy ${doDuoc.hang.length} hàng dưới mép (đo lặp trước đây: 6..9). ` +
          "Phép đo đang co lại — đọc lại `doHangDuoiMep` trước khi tin bảng xanh dưới.",
      );
    });

    /* --- 2. mọi lời tố dựng từ hình dạng đó phải được tha --- */

    test("mọi hàng dưới mép được loại trừ, và loại trừ vì ĐỌC ĐƯỢC", async () => {
      const con = [];
      const yeu = [];
      for (const h of doDuoc.hang) {
        const kq = await phanLoai(page, {
          snippet: `div "${h.chu}" is 100% covered by an opaque element (${h.tren})`,
        });
        console.log(
          `    ${h.chu.padEnd(26)} y=${String(h.y).padStart(4)}  ` +
            `${kq.verdict.padEnd(12)} ${laLoiThat(kq) ? "TÍNH LÀ LỖI" : "đã loại trừ"}  — ${kq.ly}`,
        );
        if (laLoiThat(kq)) con.push(`${h.chu} -> ${kq.verdict} (${kq.ly})`);
        // Không nhận lời tha suông. `che-chu.mjs` hứa rằng `to-cha` chỉ là NHÃN
        // dán lên một run đã đọc được, không bao giờ là lời tha; ca này đo lại
        // lời hứa đó tại chỗ thay vì tin nó. Nhãn `to-cha` ở đây tới từ lối tắt
        // class-siêu-tập mà chính file kia cảnh báo: react-native-web gộp style
        // giống nhau vào cùng một atomic class, nên selector detector in ra khớp
        // luôn cả tổ tiên của chữ.
        else if (!(kq.tyLeNhinThay >= 0.6)) {
          yeu.push(`${h.chu} -> ${kq.verdict} nhưng chỉ ${kq.diemNhinThay}/${kq.diemDo} điểm đọc được`);
        }
      }
      assert.deepEqual(
        con,
        [],
        "Hàng dưới đây nằm dưới mép vùng cuộn nhưng KHÔNG được phân xử là artefact:\n  " +
          con.join("\n  ") +
          "\n\nHoặc màn thật sự có chữ bị che, hoặc `tools/che-chu.mjs` đã đổi nghĩa. " +
          "Cả hai đều cần người đọc, không cần một dòng bị xoá ở đây.",
      );
      assert.deepEqual(
        yeu,
        [],
        "Có hàng được tha mà phần lớn điểm mẫu KHÔNG đọc được:\n  " +
          yeu.join("\n  ") +
          "\n\nĐó là lời tha tới từ nhãn chứ không tới từ phép nhìn — đúng lối tắt " +
          "`che-chu.mjs` đã gỡ bỏ một lần rồi.",
      );
    });

    /* --- 3. phép thử ngược: trên CHÍNH màn này, che thật vẫn bị kết tội --- */

    test(`đối chứng ÂM: "${SO_TIEN_DOC_DUOC}" chưa bị che thì được tha`, async () => {
      const kq = await phanLoai(page, {
        snippet: `div "${SO_TIEN_DOC_DUOC}" is 100% covered by an opaque element (div.khong-co-that)`,
      });
      assert.notEqual(
        kq.verdict,
        "khong-thay",
        `không tìm thấy "${SO_TIEN_DOC_DUOC}" trên màn — neo của đối chứng đã trượt, ` +
          "và một đối chứng trượt neo thì ca sau không chứng minh gì.",
      );
      assert.equal(
        laLoiThat(kq),
        false,
        `"${SO_TIEN_DOC_DUOC}" bị tính là lỗi khi CHƯA che gì: ${kq.verdict} — ${kq.ly}`,
      );
      console.log(
        `    trước khi che: ${kq.verdict} (${kq.diemNhinThay}/${kq.diemDo} điểm mẫu đọc được)`,
      );
    });

    test(`đối chứng DƯƠNG: phủ tấm đặc lên "${SO_TIEN_DOC_DUOC}" thì phải ra 'that'`, async () => {
      await page.evaluate(datTamChe);
      try {
        const kq = await phanLoai(page, {
          snippet: `div "${SO_TIEN_DOC_DUOC}" is 100% covered by an opaque element (div#__tam-che-thu)`,
        });
        console.log(`    sau khi che : ${kq.verdict} — ${kq.ly}`);
        assert.equal(
          kq.verdict,
          "that",
          `Phủ một tấm đặc lên "${SO_TIEN_DOC_DUOC}" mà phép phân xử vẫn tha ` +
            `('${kq.verdict}'). Nghĩa là nó đang tha MỌI thứ, và ca số 2 ở trên xanh ` +
            "vì lý do khác chứ không phải vì màn sạch.",
        );
        assert.equal(laLoiThat(kq), true);
      } finally {
        await page.evaluate(goTamChe);
      }
    });
  });
}
