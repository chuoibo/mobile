/* Không thân trả lời 5xx nào của máy chủ được đứng làm câu nói với người dùng.
 *
 * bug-185426. Bảy ô lỗi của Khám phá được đi bộ bằng trình duyệt thật ở
 * rd-qa-20; sáu ô có câu tiếng Việt bọc ngoài, một ô thì không:
 *
 *     500 -> "Máy chủ trả lỗi 500" / "Internal Server Error"
 *     502 -> "Máy chủ trả lỗi 502" / "<html>502 Bad Gateway</html>"
 *     429 -> "Máy chủ trả lỗi 429" / '{"detail":"rate limited"}'
 *
 * Cả hai thẻ lỗi của màn này đều gán `than = state.detail`, tức dán nguyên thân
 * trả lời vào đúng chỗ câu giải thích. Ba nhánh còn lại (`khong-noi-duoc`,
 * `du-lieu-sai`, `chua-co-endpoint`) đều bọc, nên đây là nhánh thứ tư đi theo
 * cùng khuôn chứ không phải một quy ước mới.
 *
 * Vì sao đáng một file test riêng chứ không phải một dòng trong
 * `hieu-cau-web.test.mjs`: thân 5xx là chuỗi DUY NHẤT trên màn này mà app không
 * tự viết ra. Bật debug ở FastAPI hoặc chen một proxy vào là nó mang theo
 * traceback, tên host nội bộ, hoặc câu SQL. Nên phép kiểm ở đây có hai vế, và
 * vế thứ hai mới là vế khó bỏ đi: CÓ câu tiếng Việt, VÀ thân thô bị cắt chứ
 * không chảy nguyên vẹn ra màn.
 *
 * Chứng minh được: chuỗi nào tới được markup, trên renderer web mà bản Expo
 * web dùng. Không chứng minh được: iOS/Android vẽ ra sao (cầu khác), và trang
 * có đọc được ở kích thước thật không (việc của `imp detect`, chạy trên
 * `tools/loi-may-chu-harness.mjs`).
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { TimKhongDuoc } from "../dist-test/screens/kham-pha/CauAiHieu.js";
import { ChuaCoDuLieu } from "../dist-test/screens/kham-pha/KhamPha.js";
import { cauMayChuLoi, thanLoiMayChu, trichThanLoi } from "../dist-test/ui/loi-may-chu.js";

/** Markup với thẻ bị bóc, tức đúng phần một người thật sự đọc. */
function words(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

/** Ba thân trả lời đã đo được thật ở rd-qa-20, nguyên văn. */
const THAN_THAT = {
  500: "Internal Server Error",
  502: "<html>502 Bad Gateway</html>",
  429: '{"detail":"rate limited"}',
};

function oTimKiem(status) {
  return words(
    React.createElement(TimKhongDuoc, {
      state: {
        kind: "may-chu-loi",
        url: "http://api.test.invalid/places/search",
        status,
        detail: THAN_THAT[status],
      },
      baseUrl: "http://api.test.invalid",
    }),
  );
}

function oDanhMuc(status) {
  return words(
    React.createElement(ChuaCoDuLieu, {
      state: {
        kind: "may-chu-loi",
        url: "http://api.test.invalid/places",
        status,
        detail: THAN_THAT[status],
      },
    }),
  );
}

/* ------------------------------------------------- câu tiếng Việt bọc ngoài */

for (const status of [500, 502, 429]) {
  test(`ô tìm kiếm ${status} nói một câu tiếng Việt, không mở đầu bằng thân trả lời`, () => {
    const html = oTimKiem(status);
    // Tiêu đề đã có sẵn từ trước và không phải thứ đang sửa; phần thân mới là
    // chỗ thân trả lời thô đang đứng.
    assert.match(html, /Máy chủ trả lỗi/);
    assert.match(html, new RegExp(cauMayChuLoi(status).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  });

  test(`ô danh mục ${status} nói một câu tiếng Việt, không mở đầu bằng thân trả lời`, () => {
    const html = oDanhMuc(status);
    assert.match(html, /Máy chủ trả lỗi/);
    assert.match(html, new RegExp(cauMayChuLoi(status).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  });
}

test("429 nói chuyện chờ, 500 nói chuyện sự cố — hai câu khác nhau", () => {
  // Gộp hai cái này thành một câu "Lỗi máy chủ" là bảo người dùng chờ một sự
  // cố không tự hết, hoặc bảo họ báo lỗi một cái throttle đang làm đúng việc.
  assert.notEqual(cauMayChuLoi(429), cauMayChuLoi(500));
  assert.match(cauMayChuLoi(429), /Chờ một lát/);
  assert.match(cauMayChuLoi(503), /sự cố phía máy chủ/);
  // 4xx khác không phải sự cố, cũng không phải throttle.
  assert.match(cauMayChuLoi(418), /từ chối yêu cầu/);
});

/* ------------------------------------------- thân thô không chảy ra màn ---- */

test("thân 502 lên màn dưới nhãn Chi tiết, không còn nguyên thẻ HTML", () => {
  for (const html of [oTimKiem(502), oDanhMuc(502)]) {
    assert.match(html, /Chi tiết:/);
    // `words()` đã giải mã entity, nên nếu thẻ tới được markup thì nó hiện ở
    // đây. Người cầm điện thoại không đọc `<html>`.
    assert.equal(/<html>/.test(html), false, `thẻ HTML thô còn trên màn: ${html}`);
    assert.match(html, /502 Bad Gateway/);
  }
});

test("thân 429 dạng JSON không còn ngoặc nhọn của máy đứng làm câu", () => {
  for (const html of [oTimKiem(429), oDanhMuc(429)]) {
    // Bản thân chuỗi JSON vẫn được phép nằm sau "Chi tiết:" — nó là manh mối
    // thật. Cái không được phép là nó đứng MỘT MÌNH làm lời giải thích.
    const truocChiTiet = html.split("Chi tiết:")[0];
    assert.equal(/rate limited/.test(truocChiTiet), false, `thân thô đứng trước nhãn: ${html}`);
    assert.match(truocChiTiet, /Chờ một lát/);
  }
});

test("thân dài bị cắt, không đổ cả traceback ra màn", () => {
  // Đây là vế đáng lo, không phải vế đẹp: `places.ts` và `tim-kiem.ts` cắt
  // thân ở 200 ký tự, đủ để một dòng traceback hoặc một câu SQL đi lọt.
  const traceback =
    'Traceback (most recent call last): File "/srv/api-internal-7/app/db/repository.py", line 412, in doc' +
    ' cur.execute("SELECT token, phone FROM people WHERE id=%s", (pid,)) psycopg.OperationalError';
  const html = words(
    React.createElement(TimKhongDuoc, {
      state: {
        kind: "may-chu-loi",
        url: "http://api.test.invalid/places/search",
        status: 500,
        detail: traceback.slice(0, 200),
      },
      baseUrl: "http://api.test.invalid",
    }),
  );
  assert.equal(/SELECT token, phone/.test(html), false, `câu SQL lên màn: ${html}`);
  assert.equal(/psycopg/.test(html), false);
  assert.match(html, /…/);
});

/* ------------------------- ba cửa chặn không mượn lời máy chủ (bug-191433) - */

test("cửa chặn actor và cửa đếm lượt nói bằng tiếng Việt, không mượn thân máy chủ", () => {
  const truong = [
    { state: { kind: "chua-biet-la-ai" }, phai: /Chưa biết bạn là ai/ },
    {
      state: { kind: "bi-tu-choi", url: "http://api.test.invalid/places/search" },
      phai: /Máy chủ chưa nhận ra bạn/,
    },
    { state: { kind: "qua-nhieu-lan", query: "lẩu bò" }, phai: /Bạn vừa tìm hơi nhiều/ },
  ];

  for (const { state, phai } of truong) {
    const html = words(
      React.createElement(TimKhongDuoc, { state, baseUrl: "http://api.test.invalid" }),
    );
    assert.match(html, phai);
    // Không có nhãn "Chi tiết:" vì không có thân nào để trích. Đây là điểm khác
    // hẳn nhánh `may-chu-loi`: ba trạng thái này app tự viết từ đầu tới cuối.
    assert.equal(/Chi tiết/.test(html), false, `nhãn trích rỗng: ${html}`);
    // Và không chữ máy nào của máy chủ đi lọt.
    for (const may of ["authentication_required", "search_rate_limited", "Too many searches"]) {
      assert.equal(html.includes(may), false, `mã máy lên màn: ${may} trong ${html}`);
    }
  }
});

test("hai trạng thái không gọi mạng thì không in địa chỉ đã thử", () => {
  // "Đã thử: <url>" dưới một thẻ chưa hề gửi request nào là chỉ sai đường: nó
  // đẩy người ta đi kiểm một máy chủ chưa ai hỏi.
  for (const state of [{ kind: "chua-biet-la-ai" }, { kind: "qua-nhieu-lan", query: "q" }]) {
    const html = words(
      React.createElement(TimKhongDuoc, { state, baseUrl: "http://api.test.invalid" }),
    );
    assert.equal(/Đã thử/.test(html), false, `địa chỉ thừa: ${html}`);
    assert.equal(html.includes("api.test.invalid"), false, `địa chỉ thừa: ${html}`);
  }

  // Còn 401/403 thì CÓ, vì lượt gọi đó có thật và địa chỉ là manh mối lệch bản.
  const tuChoi = words(
    React.createElement(TimKhongDuoc, {
      state: { kind: "bi-tu-choi", url: "http://api.test.invalid/places/search" },
      baseUrl: "http://api.test.invalid",
    }),
  );
  assert.match(tuChoi, /Đã thử/);
});

/* ----------------------------------------------------- phép cắt, trực tiếp - */

test("trichThanLoi bóc thẻ, gộp khoảng trắng, và cắt có dấu ba chấm", () => {
  assert.equal(trichThanLoi("<html>502 Bad Gateway</html>"), "502 Bad Gateway");
  // Thẻ thành khoảng trắng chứ không thành rỗng: nếu không, hai từ dính lại
  // thành một từ không ai viết.
  assert.equal(trichThanLoi("<p>502</p><p>Bad Gateway</p>"), "502 Bad Gateway");
  assert.equal(trichThanLoi("  nhiều   khoảng \n trắng "), "nhiều khoảng trắng");
  assert.equal(trichThanLoi("<html></html>"), "");
  assert.equal(trichThanLoi("abcdef", 3), "abc…");
});

test("thân rỗng thì không hiện nhãn Chi tiết trống", () => {
  // "Chi tiết:" theo sau bởi không có gì là một dòng nhiễu, không phải manh mối.
  assert.equal(/Chi tiết/.test(thanLoiMayChu(500, "<html></html>")), false);
  assert.match(thanLoiMayChu(500, "boom"), /Chi tiết: boom$/);
});
