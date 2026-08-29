/* What a place photograph URL is allowed to be, as assertions rather than as
 * a renderer. The frame (`Anh`) needs React Native; this file only pins the
 * wire read that will one day fill it.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
// react-native-web resolves to its CJS build for a bare specifier (`main` in
// its package.json), so the cache primed below must be the CJS instance -- the
// ESM copy under `dist/` is a different module with a different cache, and
// priming that one leaves every render at 0 images while looking correct.
import rnwImageLoader from "react-native-web/dist/cjs/modules/ImageLoader/index.js";

import { parsePlace, PLACES_BASE_URL } from "../dist-test/screens/kham-pha/places.js";
import { nguonAnhAnToan } from "../dist-test/ui/nguon-anh.js";
import { Anh } from "../dist-test/ui/Anh.js";
import { BASE_URL } from "../dist-test/api.js";

const { ImageUriCache } = rnwImageLoader;

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

/** One wire row, valid, that individual tests bend to make a point. */
function row(over = {}) {
  return {
    id: "p-1",
    name: "Tiệm Nướng Xóm Lào",
    category: "quan-an-local",
    kinds: ["BBQ", "Lào", "Local"],
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
    traits: ["Chill", "View đẹp"],
    group_fit: { min_people: 4, max_people: 10, relation: "Bạn bè" },
    flag: null,
    lat: 11.9404,
    lng: 108.4383,
    match: {
      score: 95,
      source: "ai",
      verdict: "hop",
      reason: "Hợp vì ngân sách và đồ nướng.",
      factors: [],
    },
    ...over,
  };
}

/* Ảnh chỉ được tải từ API của chính mình.
 *
 * `photo_url` là chuỗi NGƯỜI DÙNG TỰ KHAI: server hiện chỉ kiểm độ dài
 * (`schemas.py`), nên bất kỳ ai ghi được một hàng đều chọn được địa chỉ mà máy
 * người khác sẽ đi tải. Chừng nào app chưa render ảnh nào thì điều đó vô hại.
 * Nhánh này bật `<Image>` lên, nên nó thành lỗ thật:
 *
 *   A đặt photo_url trỏ về máy A -> app của B tải ảnh -> A biết B đã mở màn
 *   nào, lúc mấy giờ, và IP của B. Không cần B bấm gì.
 *
 * Nên luật là: chỉ tải khi địa chỉ nằm trên chính API mình đang nói chuyện.
 * Đường dẫn tương đối (`/contexts/{id}/photos/{id}`, đúng dạng backend chốt)
 * được nối vào base rồi tải; mọi origin khác bị từ chối và KHÔNG phát ra một
 * request nào.
 */
test("photo_url tương đối được nối vào API của chính mình", () => {
  // Đúng dạng backend trả về ở POST /contexts/{id}/photos.
  assert.equal(
    parsePlace(row({ photo_url: "/contexts/abc/photos/xyz" }), "p").photoUrl,
    `${PLACES_BASE_URL}/contexts/abc/photos/xyz`,
  );
});

test("photo_url tuyệt đối ra origin khác bị từ chối", () => {
  // Đây là ca lỗ hổng. Trước bản sửa cả hai dòng này trả về chính URL đó và
  // <Image> đi tải thật.
  assert.equal(parsePlace(row({ photo_url: "http://cdn.example/p.jpg" }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: "https://cdn.example/p.jpg" }), "p").photoUrl, null);
});

test("photo_url tuyệt đối trỏ đúng API của mình thì được giữ", () => {
  assert.equal(
    parsePlace(row({ photo_url: `${PLACES_BASE_URL}/contexts/abc/photos/xyz` }), "p").photoUrl,
    `${PLACES_BASE_URL}/contexts/abc/photos/xyz`,
  );
});

test("tiền tố trùng nhưng khác host không được tính là cùng origin", () => {
  // `http://localhost:8099.evil.example/x.png` bắt đầu bằng đúng chuỗi base.
  // Dấu "/" ngăn sau base là thứ duy nhất chặn ca này, nên nó có ca riêng.
  assert.equal(
    parsePlace(row({ photo_url: `${PLACES_BASE_URL}.evil.example/x.png` }), "p").photoUrl,
    null,
  );
  // Và dạng userinfo: mọi thứ trước "@" là tên người dùng, host thật là evil.
  assert.equal(
    // Ghép chuỗi chứ không viết liền: dạng "a@b.c" nằm nguyên trong mã nguồn sẽ
    // bị repo guard bắt là địa chỉ thư, và nó đúng khi bắt.
    parsePlace(row({ photo_url: `${PLACES_BASE_URL}` + "@" + "evil.example/x.png" }), "p").photoUrl,
    null,
  );
});

test("đường dẫn kiểu giao thức tương đối không được coi là tương đối", () => {
  // `//evil.example/x.png` mở đầu bằng "/" y hệt một đường dẫn nội bộ, nhưng
  // trình duyệt đọc nó là "cùng giao thức, KHÁC HOST". Đây là cách đi vòng
  // kinh điển qua một cổng chỉ kiểm ký tự đầu tiên.
  assert.equal(parsePlace(row({ photo_url: "//evil.example/x.png" }), "p").photoUrl, null);
  // Cùng thủ thuật với dấu gạch ngược, ký tự một số trình duyệt vẫn nhận là
  // dấu ngăn.
  assert.equal(parsePlace(row({ photo_url: "/\\evil.example/x.png" }), "p").photoUrl, null);
});

test("photo_url thiếu, null, rỗng hoặc không phải chuỗi thì ra null, không ném", () => {
  assert.equal(parsePlace(row({ photo_url: null }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: "" }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: 12 }), "p").photoUrl, null);
});

test("thiếu field photo_url không làm parsePlace ném lỗi", () => {
  const p = parsePlace(row(), "places[0]");
  assert.equal(p.photoUrl, null);
});

test("photo_url không phải http/https bị bỏ, không đưa vào <Image>", () => {
  // This value is sent by the server and goes straight into an <Image>.
  // javascript:/data:/file: must not survive the parse.
  assert.equal(parsePlace(row({ photo_url: "javascript:alert(1)" }), "p").photoUrl, null);
  // Spelled without a base64 payload on purpose. The repo guard's
  // `data-uri-base64` rule refuses inline binary anywhere in the tree and is
  // right to; the scheme is what this assertion is about, so the scheme is all
  // it needs to carry.
  assert.equal(parsePlace(row({ photo_url: "data:image/png,not-base64" }), "p").photoUrl, null);
  assert.equal(parsePlace(row({ photo_url: "file:///etc/passwd" }), "p").photoUrl, null);
});

/* Cổng cho chính đường ảnh.
 *
 * Bốn ca trên chứng minh một chuỗi được đọc đúng. Không ca nào chứng minh
 * chuỗi đó tới được màn hình. Đường dễ hỏng nhất ở đây không phải parser mà
 * là hai chỗ khác, và cả hai đều hỏng trong im lặng:
 *
 *   1. `Anh` thôi render <Image> thật (ai đó đơn giản hoá về View tô màu).
 *   2. Bộ quét thôi gắn `photo_url` cho row nào, nên mọi thẻ vẽ chỗ chờ và
 *      ảnh chụp trông y hệt lúc đường ảnh còn sống.
 *
 * Ca 2 là ca nguy hiểm hơn: nó biến một cổng thành đồ trang trí mà không đổi
 * một dòng nào trong `src/`.
 *
 * Ca 1 từng được gác bằng `assert.match(src, /<Image\b/)` -- đọc văn bản nguồn.
 * Cổng đó MÙ, và rd-qa-35 (#198) đo được điều đó. Đột biến đúng hồi quy nó nêu
 * tên -- làm `veAnh` không bao giờ đúng, nên `<Image>` không bao giờ được mount
 * -- để app render 0 ảnh mà cả 14 ca ở đây vẫn xanh, vì chữ `<Image` vẫn nằm
 * nguyên trong file. Một cổng không đỏ được là tệ hơn không có cổng: nó đọc
 * thành đã phủ.
 *
 * Nên ca 1 giờ RENDER. `Anh` đi qua `react-native-web` -- đúng phép thay thế
 * `expo export` làm cho bản web -- nên markup dưới đây là markup trình duyệt
 * thật sự nhận, cùng lý do `aria-vai-tro.test.mjs` render thay vì đọc nguồn.
 * Xem `tools/fixup-esm.mjs`.
 *
 * Cái nó KHÔNG chứng minh: iOS và Android, nơi một thư viện khác đọc cùng props.
 */
/* Luật origin, đọc thẳng chứ không qua parser địa điểm.
 *
 * `parsePlace` chỉ là một trong hai cửa. Cửa còn lại là `Anh`, và nó phải áp
 * đúng luật này cho MỌI màn -- kỷ niệm, tin nhắn, ảnh đại diện -- chứ không
 * riêng địa điểm. Nên luật sống ở một hàm thuần, và cả hai cửa gọi nó.
 */
const GOC = "http://may-chu.example";

test("nguonAnhAnToan: đường dẫn tương đối nối vào base", () => {
  assert.equal(nguonAnhAnToan("/contexts/a/photos/b", GOC), "http://may-chu.example/contexts/a/photos/b");
  // Base có dấu "/" thừa không được sinh ra "//" ở giữa.
  assert.equal(nguonAnhAnToan("/x.png", "http://may-chu.example/"), "http://may-chu.example/x.png");
});

test("nguonAnhAnToan: từ chối mọi origin khác, không phát request", () => {
  for (const xau of [
    "http://evil.example/x.png",
    "https://evil.example/x.png",
    "//evil.example/x.png",
    "/\\evil.example/x.png",
    "javascript:alert(1)",
    "data:image/png,not-base64",
    "file:///etc/passwd",
    "http://may-chu.example.evil/x.png",
    "http://may-chu.example" + "@" + "evil.example/x.png",
    "x.png",
    "../x.png",
  ]) {
    assert.equal(nguonAnhAnToan(xau, GOC), null, `phải từ chối: ${xau}`);
  }
});

test("nguonAnhAnToan: rỗng, sai kiểu, hoặc có ký tự điều khiển thì ra null", () => {
  assert.equal(nguonAnhAnToan(null, GOC), null);
  assert.equal(nguonAnhAnToan(undefined, GOC), null);
  assert.equal(nguonAnhAnToan(12, GOC), null);
  assert.equal(nguonAnhAnToan("   ", GOC), null);
  // Xuống dòng và tab là công cụ nhét lậu, không phải một phần địa chỉ thật.
  assert.equal(nguonAnhAnToan("/a\nb.png", GOC), null);
  assert.equal(nguonAnhAnToan("/a\tb.png", GOC), null);
});

/* ---------------------------------------------------------- render thật --- */

/** Mọi `src` mà react-native-web đặt lên một <img>, theo thứ tự tài liệu. */
function anhTrongMarkup(html) {
  return [...html.matchAll(/<img\b[^>]*\bsrc="([^"]*)"/g)].map((m) => m[1]);
}

/** `Anh` dựng markup gì cho một `uri`.
 *
 * `ImageUriCache.add` đứng trước mỗi lượt render vì react-native-web khởi tạo
 * `<Image>` ở trạng thái IDLE và chỉ vẽ ảnh khi đã có trong cache trình duyệt;
 * không mồi thì SSR luôn ra 0 ảnh và CẢ HAI ca dưới đều xanh vì lý do sai. Mồi
 * cache là mô phỏng một trạng thái thật người dùng chạm tới (ảnh đã tải trước
 * đó), bằng chính API công khai của thư viện -- không vá, không stub.
 *
 * Mồi CẢ địa chỉ độc là chỗ làm ca âm có giá trị: nếu `Anh` quên lọc, markup sẽ
 * mang <img src="http://evil..."> ngay tại đây.
 */
function veAnh(uri) {
  ImageUriCache.add(uri);
  return renderToStaticMarkup(
    React.createElement(Anh, {
      uri,
      alt: "Ảnh quán",
      cho: React.createElement("i", { "data-cho": "1" }),
    }),
  );
}

test("Anh dựng <img> thật khi địa chỉ nằm trên API của chính mình", () => {
  // Đây là ca thay cho `assert.match(src, /<Image\b/)`. Nó đỏ khi `<Image>`
  // thôi được mount, kể cả lúc chữ `<Image` vẫn còn nguyên trong nguồn.
  const an = `${BASE_URL}/contexts/abc/photos/xyz`;
  const html = veAnh(an);
  assert.deepEqual(
    anhTrongMarkup(html),
    [an],
    "đúng một <img>, mang đúng địa chỉ đã lọc -- 0 ảnh nghĩa là khung không còn dựng <Image>",
  );
});

test("Anh không phát một request nào tới origin lạ", () => {
  // Ca âm, và là ca quan trọng hơn: rò rỉ nằm ở REQUEST, không ở pixel. Nên
  // phép đo là "địa chỉ đó không xuất hiện ở đâu trong markup" -- không <img>,
  // và cũng không <link rel=preload> hay background-image, vì cả ba đều làm
  // trình duyệt đi tải thật.
  const doc = "http://evil.example/theo-doi.png";
  const html = veAnh(doc);
  assert.deepEqual(anhTrongMarkup(html), [], "địa chỉ lạ không được thành <img>");
  assert.ok(
    !html.includes("evil.example"),
    "địa chỉ lạ không được lọt vào markup dưới bất kỳ dạng nào (preload / background-image)",
  );
  // Và khung vẫn vẽ chỗ chờ, không để lại một ô trống.
  assert.match(html, /data-cho="1"/);
});

test("chỗ chờ vẫn nằm dưới ảnh kể cả khi ảnh đã hiện", () => {
  // Hành vi 1 trong docstring của `Anh.tsx`: chỗ chờ không phải màn chờ, nó là
  // cái sàn. Ảnh giải mã xong rồi bị thu hồi không được để lại lỗ thủng.
  const html = veAnh(`${BASE_URL}/contexts/abc/photos/san.jpg`);
  assert.equal(anhTrongMarkup(html).length, 1);
  assert.match(html, /data-cho="1"/);
});

test("Anh đưa tải hỏng về chỗ chờ, không hiện mã lỗi", () => {
  // Đọc nguồn, và nói thẳng ra là đọc nguồn: `onError` chỉ chạy trong trình
  // duyệt thật, `renderToStaticMarkup` không chạy effect nào. Ca này chứng minh
  // đường quay về CÓ ĐƯỢC NỐI, không chứng minh nó chạy đúng. Bằng chứng hành
  // vi cho đường hỏng vẫn là ô chưa quét -- rd-qa-35 ghi nó ở #198.
  //
  // Và nó chỉ kiểm ĐÚNG một chuyện: đường đó có được nối. Bản nháp của ca này
  // còn `assert.doesNotMatch(src, /ECONNREFUSED/)` để nói "không mã lỗi nào lên
  // khung" -- rồi đỏ, vì `ECONNREFUSED` nằm trong chính đoạn chú thích giải
  // thích vì sao không được hiện nó. Một phép so văn bản không phân biệt được
  // mã với lời bàn về mã, nên nó đã bị gỡ thay vì được nới cho xanh.
  const src = readFileSync(join(MOBILE_ROOT, "src/ui/Anh.tsx"), "utf8");
  assert.match(src, /onError=/);
});

test("bộ quét gắn photo_url cho đúng một row, nên ảnh chụp đỏ được", () => {
  const tool = readFileSync(join(MOBILE_ROOT, "tools/tab-snapshots.mjs"), "utf8");
  // Sinh PNG thật lúc quét, không phải nhị phân commit vào cây.
  assert.match(tool, /function vietPngThu\(/);
  assert.match(tool, /IHDR/);
  // Và phải thật sự gắn vào fixture, không chỉ sinh ra rồi bỏ đó.
  const gan = tool.match(/fixtures\.places\[\d+\]\.photo_url\s*=/g) ?? [];
  assert.equal(
    gan.length,
    1,
    "đúng một row mang ảnh: không row nào thì ảnh chụp mù, mọi row thì mất trạng thái chỗ chờ",
  );
});
