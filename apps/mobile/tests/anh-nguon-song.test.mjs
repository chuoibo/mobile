/* Cổng nguồn ảnh, đo bằng CÁI ĐƯỢC RENDER chứ không bằng chữ trong file nguồn.
 *
 * `nguonAnhAnToan` là thứ đứng giữa mỗi người đọc và một địa chỉ do THÀNH VIÊN
 * KHÁC tự khai: `image_url` trên kỷ niệm và trên tin nhắn, `photo_url` trên địa
 * điểm. Máy chủ chỉ kiểm độ dài (`schemas.py`), nên ai ghi được một hàng thì
 * chọn được cái host mà điện thoại người khác sẽ đi tải. Cái rò rỉ là REQUEST,
 * không phải pixel: A đặt địa chỉ về máy A, B mở màn, A biết B đã mở lúc mấy
 * giờ và từ IP nào — B không bấm gì cả.
 *
 * Cây `main` hôm nay làm ĐÚNG. Cái file này gác là **cổng**, không phải sản
 * phẩm: trước nó, toàn bộ chứng cứ cho biên đó là hai phép grep văn bản nguồn
 * trong `anh.test.mjs`:
 *
 *     assert.match(src, /nguonAnhAnToan/)
 *     assert.doesNotMatch(src, /source=\{\{\s*uri:\s*uri\b/)
 *
 * Đột biến đo được (rd-qa-tt-0012), mỗi cái một mình, chạy `npm test` đủ bộ:
 *
 *   | đột biến trên src/                                   | npm test |
 *   |------------------------------------------------------|----------|
 *   | X1  `s.includes(base+"/")` thay cho `startsWith`      | 554/554 XANH |
 *   | X2a `Anh`: gate trả null thì rơi về `uri` thô         | 554/554 XANH |
 *   | X2b `Anh`: thôi gọi gate, giữ nguyên dòng import      | 554/554 XANH |
 *
 * X2b là cái tệ nhất: cổng bảo vệ IP của mọi người đọc BIẾN MẤT khỏi đường
 * chạy, và không một ca nào kêu, vì chuỗi `nguonAnhAnToan` vẫn còn nằm trong
 * file. Cùng loại với thứ rd-qa-35 đã ghi ở #198 cho `{veAnh ? (`; lần đó cổng
 * ở lại trong probe kèm PR chứ không vào `npm test`, nên `main` vẫn hở.
 *
 * ## Phép đo ở đây, và vì sao nó là phép đo này
 *
 * react-native-web 0.21 render `<Image>` thành một `<div>` mang
 * `background-image` trong CLASS sinh ra, nên **URL không có mặt trong HTML
 * tĩnh**. Vì vậy `assert.ok(!html.includes("evil.example"))` sẽ xanh một cách
 * rỗng tuếch — nó cũng xanh khi URL được tải thật. Không dùng nó.
 *
 * Cái phân biệt được là CÓ HAY KHÔNG có khung ảnh trong cây:
 *
 *   - địa chỉ trên API của mình  -> markup KHÁC markup lúc không có ảnh
 *   - địa chỉ của người khác     -> markup GIỐNG HỆT lúc không có ảnh
 *
 * Nên ca khẳng định cái CÓ chạy trước: không có nó thì mọi dòng phủ định bên
 * dưới đúng theo kiểu một trang trắng cũng đúng.
 *
 * ## Không chứng minh
 *
 * `renderToStaticMarkup` không chạy `useEffect`, nên không đo `onTrangThai`.
 * Không đo iOS/Android — RN-web là một bản render, không phải cái điện thoại
 * cầm trên tay. Và không đo tầng máy chủ: `image_url` vẫn là chuỗi client tự
 * khai, cổng này là lớp thứ hai chứ không phải lớp thứ nhất.
 */
import assert from "node:assert/strict";
import test from "node:test";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Anh } from "../dist-test/ui/Anh.js";
import { BASE_URL } from "../dist-test/api.js";
import { nguonAnhAnToan } from "../dist-test/ui/nguon-anh.js";
import { parsePlace, PLACES_BASE_URL } from "../dist-test/screens/kham-pha/places.js";

/** Chỗ chờ, đủ để nhận ra trong markup và không mang theo ý nghĩa nào khác. */
const CHO = React.createElement("div", { "data-cho": "1" });

/** Một hàng địa điểm hợp lệ; ca nào cần thì bẻ đúng trường của ca đó. Giữ
 *  riêng ở đây thay vì import từ `anh.test.mjs` vì hai file phải đỏ độc lập. */
function hang(over = {}) {
  return {
    id: "p-1",
    name: "Tiệm Nướng Xóm Lào",
    category: "quan-an-local",
    kinds: ["BBQ"],
    rating: 4.7,
    rating_count: 128,
    distance_km: 1.2,
    price_min_vnd: 200000,
    price_max_vnd: 250000,
    address: "27/1 Yersin, P.10, TP. Đà Lạt",
    open_now: true,
    open_hours: "10:00 – 22:30",
    travel_minutes: 25,
    photo_count: 18,
    traits: ["Chill"],
    group_fit: { min_people: 4, max_people: 10, relation: "Bạn bè" },
    flag: null,
    lat: 11.9404,
    lng: 108.4383,
    match: null,
    ...over,
  };
}

function ve(uri) {
  return renderToStaticMarkup(
    React.createElement(Anh, { uri, alt: "ảnh thử", cho: CHO }),
  );
}

/** Markup của đúng cái khung ấy khi KHÔNG có ảnh nào. Mọi địa chỉ bị từ chối
 *  phải ra đúng chuỗi này: không thẻ ảnh, nên không request. */
const KHONG_ANH = ve(null);

/* Địa chỉ trên chính API của app. Ca này phải chạy trước và phải ĐẠT, nếu
 * không thì mọi ca từ chối bên dưới xanh một cách rỗng. */
test("Anh: địa chỉ trên API của mình thì dựng khung ảnh thật", () => {
  const html = ve(BASE_URL + "/contexts/c-1/photos/p-1");
  assert.notEqual(
    html,
    KHONG_ANH,
    "khung ảnh không được dựng cho địa chỉ hợp lệ — mọi ca từ chối bên dưới thành vô nghĩa",
  );
  // Và chỗ chờ vẫn nằm dưới ảnh, đúng như `Anh` tự khai (ghi chú 1 của file đó).
  assert.match(html, /data-cho="1"/);
});

/* Cùng một vi phạm viết bằng nhiều hình dạng: mỗi dòng là một cách một địa chỉ
 * của người khác có thể đi vào `<Image>`. */
test("Anh: không địa chỉ nào ngoài API của mình dựng được khung ảnh", () => {
  const ngoai = [
    "http://evil.example/x.png",
    "https://evil.example/x.png",
    "//evil.example/x.png",
    "/\\evil.example/x.png",
    "data:image/png,not-base64",
    "file:///etc/passwd",
    // Origin dài hơn base nhưng bắt đầu bằng base — host thật là evil.
    BASE_URL + ".evil.example/x.png",
    // Mọi thứ trước "@" là userinfo, host thật vẫn là evil.
    BASE_URL + "@" + "evil.example/x.png",
    // Base nằm TRONG chuỗi nhưng không ở đầu: cái mà `includes` cho lọt còn
    // `startsWith` thì không. Đây là hình dạng đột biến X1 đi qua.
    "http://evil.example/?next=" + BASE_URL + "/x.png",
    "http://evil.example/" + BASE_URL + "/x.png",
    "http://evil.example/#" + BASE_URL + "/x.png",
  ];
  for (const uri of ngoai) {
    assert.equal(
      ve(uri),
      KHONG_ANH,
      `dựng khung ảnh cho địa chỉ ngoài API — điện thoại người đọc sẽ gọi tới đó: ${uri}`,
    );
  }
});

/* Cùng ba hình dạng ấy ở tầng hàm thuần, để khi cổng đỏ thì biết đỏ ở đâu. */
test("nguonAnhAnToan: base nằm trong chuỗi không phải là base ở đầu chuỗi", () => {
  const GOC = "http://may-chu.example";
  for (const xau of [
    "http://evil.example/?next=" + GOC + "/x.png",
    "http://evil.example/" + GOC + "/x.png",
    "http://evil.example/#" + GOC + "/x.png",
    "http://evil.example/x.png?u=" + GOC + "/y.png",
  ]) {
    assert.equal(nguonAnhAnToan(xau, GOC), null, `phải từ chối: ${xau}`);
  }
});

/* Cửa thứ hai. `parsePlace` gọi cùng hàm ấy với base của riêng nó, nên một
 * trong hai cửa hở là đủ. */
test("parsePlace: photo_url mang base ở giữa chuỗi vẫn bị bỏ", () => {
  for (const xau of [
    "http://evil.example/?next=" + PLACES_BASE_URL + "/x.png",
    "http://evil.example/" + PLACES_BASE_URL + "/x.png",
    "http://evil.example/#" + PLACES_BASE_URL + "/x.png",
  ]) {
    assert.equal(parsePlace(hang({ photo_url: xau }), "p").photoUrl, null, xau);
  }
});
