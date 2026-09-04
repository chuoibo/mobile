/* Mọi id NGƯỜI client tự đúc phải là UUID chuẩn chữ thường.
 *
 * Vì sao cổng này tồn tại, và vì sao nó KHÔNG phải một quy ước đặt tên.
 *
 * bug-050923 được vá bốn lượt. Lượt thứ năm hỏi một câu khác: hai chỗ trong
 * `DeXuat` -- màn chốt tiền vào sổ -- đặt tên cho `advancerId` và cho từng id
 * trong `roundingGainers`, mà cả hai đều đến từ câu trả lời của máy chủ. Chúng
 * là rò rỉ THẬT hay chỉ khớp hình dạng?
 *
 * Câu đó được trả lời bằng phép đo trên máy chủ thật, không bằng đọc mã:
 * `tests/e2e/gainer-thuoc-bill.probe.mjs`. Kết quả 6/6 ca, và nó tách được hai
 * đường hỏng mà đọc mã gộp làm một:
 *
 *   TẬP HỢP  — máy chủ trả một id không có trong `participants` client gửi.
 *              SẠCH, kể cả ca người trả trước KHÔNG nằm trên bill.
 *   CHỮ VIẾT — client giữ id có chữ HOA, gửi đi, pydantic dựng `UUID` rồi in
 *              lại bằng chữ thường. VI PHẠM, và không chỉ một chỗ: cả ba khoá
 *              của `allocation.allocations` cũng lệch, nên
 *              `proposal.allocations[person.id]` ra `undefined` -- cột tiền,
 *              chứ không phải chỉ cái tên.
 *
 * Nên hai chỗ `DeXuat` hôm nay là hình dạng, không phải một lần bắt gặp lỗi
 * sống. Nhưng chúng an toàn vì MỘT sự trùng hợp về định dạng, không vì có một
 * phép kiểm nào: mọi đường đúc id trong client tình cờ đều ra chữ thường. Sự
 * trùng hợp thì không tự giữ mình. Cổng này biến nó thành một điều kiện.
 *
 * Bốn đối chứng, vì một cổng đọc mã nguồn chết trong im lặng:
 *
 *   - nhánh dự phòng (máy không có `crypto.randomUUID`) được ép chạy thật, chứ
 *     không chỉ nhánh may mắn
 *   - máy quét literal phải bắt được một UUID chữ hoa trong fixture
 *   - sàn số file và số literal đã soi, để một phép duyệt đi lạc không in ra 0
 *   - HẬU QUẢ được ghim bằng ca thật: lệch chữ hoa thì `labelInGroup` trượt và
 *     `allocations[id]` ra `undefined`. Không có ca này thì lời khai ở trên chỉ
 *     là một câu văn.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

import { makeIdFactory, labelInGroup } from "../dist-test/participants.js";
import { idNgauNhien } from "../dist-test/screens/vao-cua/danh-tinh.js";
import { idNguoi, khoaGhi } from "../dist-test/screens/chat/uuid5.js";
import { TEN_CHUA_BIET } from "../dist-test/screens/chat/tin-nhan.js";

const MOBILE = fileURLToPath(new URL("..", import.meta.url));
const SRC = join(MOBILE, "src");

/** Chuẩn RFC 4122 như máy chủ in ra: chữ thường, có gạch, đúng 36 ký tự. */
const CHUAN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
/** Dạng UUID bất kể hoa thường, để đi tìm literal. */
const DANG_UUID = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

function nguonTs(dir) {
  const ra = [];
  for (const muc of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, muc.name);
    if (muc.isDirectory()) ra.push(...nguonTs(p));
    else if (/\.tsx?$/.test(muc.name)) ra.push(p);
  }
  return ra;
}

const FILES = nguonTs(SRC);

/** Literal chuỗi có dạng UUID, kèm chỗ đứng.
 *
 * Đọc literal qua AST chứ không grep toàn văn, vì grep khớp cả comment: file
 * này và `mac-dinh-am-tham-id.test.mjs` đều nhắc UUID trong phần giải thích, và
 * một cổng đỏ vì lời giải thích của chính nó là một cổng không ai giữ.
 */
function literalUuid(ma, ten) {
  const nguon = ts.createSourceFile(
    ten,
    ma,
    ts.ScriptTarget.Latest,
    true,
    ten.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const thay = [];
  const di = (node) => {
    if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
      DANG_UUID.test(node.text)
    ) {
      thay.push({ file: ten, text: node.text });
    }
    ts.forEachChild(node, di);
  };
  di(nguon);
  return thay;
}

const literalTrongFile = (file) =>
  literalUuid(readFileSync(file, "utf8"), relative(MOBILE, file));

test("hàm đúc id người trả về UUID chuẩn chữ thường", () => {
  const nextId = makeIdFactory();
  const mau = [];
  // Nhiều lượt vì lỗi hoa/thường chỉ hiện khi rơi vào chữ cái a..f. Một lượt
  // duy nhất có thể ra toàn chữ số và không nói gì.
  for (let i = 0; i < 400; i++) mau.push(nextId(), idNgauNhien());
  for (const slug of ["minh", "trang", "ngoc", "hai", "an", "bao", "chi"]) {
    mau.push(idNguoi(slug), khoaGhi(slug));
  }
  const lech = mau.filter((id) => !CHUAN.test(id));
  assert.deepEqual(lech, [], `id không chuẩn: ${JSON.stringify(lech.slice(0, 5))}`);
  assert.ok(
    mau.some((id) => /[a-f]/.test(id)),
    "không mẫu nào chứa chữ a..f, nên phép kiểm hoa/thường chưa hề được thử",
  );
});

test("nhánh dự phòng (máy không có crypto.randomUUID) cũng ra chữ thường", () => {
  const that = globalThis.crypto;
  // Nhánh này là nhánh KHÔNG chạy trên Node 22 và trên trình duyệt, tức là
  // nhánh không ai nhìn thấy cho tới lúc nó chạy trên một máy khác.
  try {
    Object.defineProperty(globalThis, "crypto", {
      value: { getRandomValues: that.getRandomValues.bind(that) },
      configurable: true,
    });
    const nextId = makeIdFactory();
    const mau = [];
    for (let i = 0; i < 400; i++) mau.push(nextId(), idNgauNhien());
    const lech = mau.filter((id) => !CHUAN.test(id));
    assert.deepEqual(lech, [], `dự phòng ra id không chuẩn: ${JSON.stringify(lech.slice(0, 5))}`);
    assert.ok(
      mau.some((id) => /[a-f]/.test(id)),
      "nhánh dự phòng không sinh chữ a..f nào — chưa thử được điều cần thử",
    );
  } finally {
    Object.defineProperty(globalThis, "crypto", { value: that, configurable: true });
  }
});

test("không literal UUID nào trong client viết hoa", () => {
  const tatCa = FILES.flatMap(literalTrongFile);
  const hoa = tatCa.filter((l) => /[A-F]/.test(l.text));
  assert.deepEqual(
    hoa.map((l) => `${l.file}: ${l.text}`),
    [],
    "một id ghi sẵn bằng chữ hoa sẽ không bao giờ khớp id máy chủ in ra",
  );
  // Sàn: một phép duyệt đi lạc (glob đổi, parse ném vào catch) cũng in ra 0.
  // Sàn hạ ngày 04/09 khi App B rời cây (còn ~80 file, 12 literal); mục đích vẫn là bắt số 0.
  assert.ok(FILES.length >= 50, `chỉ soi ${FILES.length} file — phép duyệt đi lạc`);
  assert.ok(tatCa.length >= 8, `chỉ thấy ${tatCa.length} literal UUID — phép duyệt đi lạc`);
});

test("ĐỐI CHỨNG: máy quét literal bắt được UUID chữ hoa", () => {
  // Dựng trong bộ nhớ, không đặt thành file trong cây: một file nháp mang id
  // chữ hoa nằm dưới `src/` sẽ làm chính ca ở trên đỏ, và làm nó đỏ vì fixture
  // của mình chứ không vì sản phẩm.
  const fixture = [
    'const dungChuan = "3c4db728-229c-4510-8227-d4b5e3108bb4";',
    'const vietHoa = "3C4DB728-229C-4510-8227-D4B5E3108BB4";',
    'const nuaNua = `386e198c-E2AD-4cc0-8a90-8abfd5135726`;',
    'const khongPhaiUuid = "3c4db728-229c-4510-8227";',
  ].join("\n");
  const thay = literalUuid(fixture, "fixture.ts");
  assert.equal(thay.length, 3, `fixture có 3 literal UUID, quét ra ${thay.length}`);
  const hoa = thay.filter((l) => /[A-F]/.test(l.text));
  assert.equal(hoa.length, 2, `fixture có 2 cái viết hoa, quét ra ${hoa.length}`);
});

test("HẬU QUẢ: lệch hoa/thường làm trượt cả tên lẫn cột tiền", () => {
  // Đúng cặp mà máy chủ tạo ra: client giữ chữ hoa, máy chủ in lại chữ thường.
  const giu = "3C4DB728-229C-4510-8227-D4B5E3108BB4";
  const mayChuInRa = giu.toLowerCase();
  const roster = { participants: [{ id: giu, name: "Ngọc" }], advancerId: giu };

  assert.equal(
    labelInGroup(roster, [], mayChuInRa),
    TEN_CHUA_BIET,
    "cùng một người, và client vẫn không đặt tên được",
  );
  const allocations = { [mayChuInRa]: 34 };
  assert.equal(
    allocations[giu],
    undefined,
    "cột tiền của người ấy ra undefined, không phải một con số",
  );

  // Đối chứng dương: khi hai bên cùng chữ thường thì cả hai đều tra được, nên
  // ca trên đỏ vì chữ viết chứ không vì `labelInGroup` hỏng sẵn.
  const thuong = { participants: [{ id: mayChuInRa, name: "Ngọc" }], advancerId: mayChuInRa };
  assert.equal(labelInGroup(thuong, [], mayChuInRa), "Ngọc");
  assert.equal(allocations[mayChuInRa], 34);
});

test("kiểm đếm nguồn đúc id: không có nguồn nào mọc thêm mà cổng không biết", () => {
  // Không liệt kê bằng tay. Danh sách viết tay không tự biết mình thiếu, và
  // đó đúng là cách bốn lượt vá trước bỏ sót chỗ thứ năm.
  const coDuc = FILES.filter((file) => {
    const nguon = readFileSync(file, "utf8");
    // `randomUUID` là dấu hiệu chung của mọi nguồn đúc trong client; `uuid5.ts`
    // đúc theo cách khác nên được nêu đích danh.
    return /\brandomUUID\b/.test(nguon) || file.endsWith(join("chat", "uuid5.ts"));
  }).map((file) => relative(MOBILE, file));

  /* Nguồn đã biết, và cái nào được thử BẰNG CÁCH GỌI THẬT ở trên.
   *
   * `TinNhan.tsx` không gọi được: `taoKhoa` là hàm private, y hệt
   * `nameOf`/`nameFrom` trong `api.ts` -- vùng mà phép duyệt theo tên hàm không
   * có đường vào. Nó nằm đây kèm lý do vì sao KHÔNG cần gọi, chứ không bị bỏ ra
   * ngoài danh sách: đầu ra của nó là `Idempotency-Key`, không bao giờ bị đem
   * so với một roster, nên nó không nằm trên đường hỏng mà file này gác. Ngày
   * nào nó cấp id cho một người, dòng này phải đổi. */
  const daBiet = {
    "src/participants.ts": "gọi thật (makeIdFactory)",
    "src/screens/vao-cua/danh-tinh.ts": "gọi thật (idNgauNhien)",
    "src/screens/chat/uuid5.ts": "gọi thật (idNguoi, khoaGhi)",
  };

  const moi = coDuc.filter((f) => !(f in daBiet));
  assert.deepEqual(
    moi,
    [],
    `nguồn đúc id mới: ${JSON.stringify(moi)}. Gọi nó ở ca đầu file này, hoặc ` +
      `ghi vào bảng kèm lý do vì sao đầu ra của nó không bị đem so với id máy chủ.`,
  );
  const mat = Object.keys(daBiet).filter((f) => !coDuc.includes(f));
  assert.deepEqual(mat, [], `bảng còn tên file không còn đúc id nữa: ${JSON.stringify(mat)}`);
});
