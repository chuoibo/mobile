/* Một chỗ quyết định một request nói nó là ai.
 *
 * ## Lỗ này đã có thật, và nó im lặng
 *
 * Trước ADR-0014 danh tính LÀ cái header, nên chín module tự dựng
 * `X-Actor-ID` của riêng chúng là chuyện vô hại — `screens/chat/tin-nhan.ts`,
 * `screens/ca-nhan/tai-chinh.ts`, `screens/album/album-api.ts` và sáu cái nữa,
 * mỗi cái một hàm `headers()` riêng, có cái vì nó có trước `callAsActor`, có
 * cái vì nó cần hình dạng `callAsActor` không có (multipart, query, cursor).
 *
 * Sau ADR-0014 thì không còn vô hại: máy chủ `prod` lờ `X-Actor-*` và đọc
 * `Authorization`. Đo trên một máy chủ prod ngày 2026-09-03, request chỉ mang
 * bộ ba header:
 *
 *     GET /people/{id}/finance      -> 401
 *     GET /contexts/{id}/recap      -> 401
 *     GET /contexts/{id}/messages   -> 401
 *
 * Tức là màn Tài chính và màn Quyết toán — hai màn vừa được nối vào «dữ liệu
 * thật» — hỏng trên host thật. Đúng một trong chín module (`chat/nhom.ts`) tự
 * gắn bearer, kèm comment nói thẳng rằng module tự dựng header thì phải làm
 * thế. Nó đúng, và nó là bản sao duy nhất.
 *
 * Tệ nhất là kiểu hỏng: `doc-live.ts` nuốt 401 của recap thành «không có tổng»,
 * nên màn in *«máy chủ chưa có tổng cho nhóm này»* — một câu SAI, trên đúng cái
 * màn mà cả nhánh này dựng lên để thôi nói dối.
 *
 * ## Cổng này đo cái gì
 *
 * Không phải «có gọi `headerNguoiGoi` không» — đó là đo cách viết. Nó đo cái
 * duy nhất quan trọng: **không file nào ngoài `src/api.ts` được tự tay dựng
 * header danh tính.** Một `headers()` riêng thứ mười sẽ đỏ ngay, kể cả khi
 * người viết nhớ gắn bearer, vì bản sao thứ hai của một quyết định là cách nó
 * lệch nhau lần sau.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

/** `src/api.ts` là nơi được phép — nó LÀ chỗ dựng. */
const CHU_NHA = "api.ts";

// Cố ý rộng: chỉ cần NHẮC tới tên header là phạm. Bản hẹp đầu tiên viết
// `/"Authorization"\s*:/` và mù ngay với chính `src/api.ts`, nơi bearer được
// gắn bằng `headers["Authorization"] = ...`. Một cổng chỉ bắt được một CÁCH VIẾT
// là cổng bắt được cách viết, không bắt được hành vi.
const HEADER_DANH_TINH = /\bX-Actor-(ID|Roles|Contexts)\b/;
const BEARER = /\bAuthorization\b/;

function nguon(dir) {
  const ra = [];
  for (const muc of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, muc.name);
    if (muc.isDirectory()) ra.push(...nguon(p));
    else if (/\.tsx?$/.test(muc.name)) ra.push(p);
  }
  return ra.sort();
}

/** Bỏ comment: một comment nhắc tới header không phải một header. */
function boComment(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[^\n]*?\/\/[^\n]*$/gm, "");
}

test("chỉ src/api.ts được dựng header danh tính", () => {
  const pham = [];
  for (const duong of nguon(SRC)) {
    const ten = relative(SRC, duong);
    if (ten === CHU_NHA) continue;
    const than = boComment(readFileSync(duong, "utf8"));
    if (HEADER_DANH_TINH.test(than)) pham.push(ten);
  }
  assert.deepEqual(
    pham,
    [],
    "những file này tự dựng header danh tính thay vì gọi `headerNguoiGoi` từ " +
      "src/api.ts, nên chúng sẽ KHÔNG mang bearer và ăn 401 trên host prod:\n  " +
      pham.join("\n  "),
  );
});

test("chỉ src/api.ts được tự gắn Authorization", () => {
  // Chiều còn lại. Một module nhớ gắn bearer bằng tay vẫn là bản sao thứ hai
  // của quyết định «request này nói nó là ai», và bản sao thứ hai là cách hai
  // bên lệch nhau ở lần đổi kế tiếp.
  const pham = [];
  for (const duong of nguon(SRC)) {
    const ten = relative(SRC, duong);
    if (ten === CHU_NHA) continue;
    const than = boComment(readFileSync(duong, "utf8"));
    if (BEARER.test(than)) pham.push(ten);
  }
  assert.deepEqual(pham, [], `tự gắn Authorization ngoài api.ts:\n  ${pham.join("\n  ")}`);
});

test("phép quét thật sự đọc được cây nguồn", () => {
  // Ca giữ hai ca trên cho khỏi chết âm thầm: một glob hỏng hay một regex trôi
  // sẽ quét được 0 file và cả hai ca trên xanh vì so rỗng với rỗng — đúng hình
  // dạng «xanh vì chẳng chạy gì» mà repo này viết cổng để chặn.
  const tep = nguon(SRC);
  assert.equal(tep.length > 100, true, `chỉ đọc được ${tep.length} file nguồn`);
  const api = tep.filter((d) => relative(SRC, d) === CHU_NHA);
  assert.equal(api.length, 1, "không thấy src/api.ts");
  // Và chỗ được phép thì thật sự có header — nếu không, regex đã trôi.
  assert.equal(HEADER_DANH_TINH.test(boComment(readFileSync(api[0], "utf8"))), true);
  assert.equal(BEARER.test(boComment(readFileSync(api[0], "utf8"))), true);
});
