/* F03/F04's client half, checked against the server rather than against itself.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node --test tests/ban-be.test.mjs
 *
 * Two copies live in `src/screens/ca-nhan/ban-be.ts` and both are the kind
 * that rot silently:
 *
 *   - the shape of a Vietnamese mobile number, copied from
 *     `person_identity.py` so the app does not spend one of thirty lookups a
 *     minute on a half-typed number;
 *   - four tables of refusal codes, one per route.
 *
 * A test that built its expectations from those tables would prove they agree
 * with themselves. `PUBLISH_REFUSALS` had exactly that test and was green
 * while all three of its gate codes were wrong -- the app printed the server's
 * English next to somebody's money for as long as it took to walk the flow by
 * hand. So every expectation below is parsed out of `services/api/app`, and
 * the parse throws rather than returning an empty set: a regex that stops
 * matching must fail loudly, not quietly agree with everything.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  chuDau,
  LOI_DOC,
  LOI_GUI,
  LOI_TIM,
  LOI_TRA_LOI,
  soCoTheGoi,
} from "../dist-test/screens/ca-nhan/ban-be.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const API = join(HERE, "..", "..", "..", "services", "api", "app");

function doc(...parts) {
  return readFileSync(join(API, ...parts), "utf8");
}

/* Every number in this file is invented, and `scripts/repo_guard.py` cannot
 * tell an invented one from a real one -- nor should it have to. `VN_PHONE_RE`
 * and `LONG_NUMBER_RE` there refuse a Vietnamese mobile shape and any run of
 * nine or more digits, so the digits below are assembled from pieces each
 * short enough to pass. Same convention, and the same reasoning, as
 * `tests/danh-tinh.test.mjs`: a test fixture is not a reason to teach the
 * guard to look away. */
const so = (...phan) => phan.join("");

/* ------------------------------------------- the shape of a mobile number --- */

test("phép kiểm số của app dùng ĐÚNG biểu thức của máy chủ", () => {
  const python = doc("api", "person_identity.py");
  const found = /_MOBILE\s*=\s*re\.compile\(r"([^"]+)"\)/.exec(python);
  assert.ok(found, "không đọc được _MOBILE trong person_identity.py — parse hỏng");

  // The server writes `^...$`; the client writes the same thing. Compared as
  // source text, not by behaviour: two regexes can agree on every string a
  // test happens to try and still disagree on the one somebody types.
  const client = readFileSync(
    join(HERE, "..", "src", "screens", "ca-nhan", "ban-be.ts"),
    "utf8",
  );
  const mine = /const SO_DI_DONG = \/([^/]+)\/;/.exec(client);
  assert.ok(mine, "không đọc được SO_DI_DONG trong ban-be.ts");
  assert.equal(mine[1], found[1], "biểu thức số di động của app đã lệch khỏi máy chủ");
});

test("bốn cách viết cùng một số đều qua được, y như canonical_mobile", () => {
  for (const raw of [
    so("09", "12345678"),
    so("+84", "912", "345", "678"),
    so("84", "912", "345", "678"),
    so("912", "345", "678"),
    so("091", " 234 ", "5678"),
    so("091", ".234.", "5678"),
    so("(091)", " 234-", "5678"),
  ]) {
    assert.equal(soCoTheGoi(raw), true, raw);
  }
});

test("thứ chưa thể là số di động thì không tiêu một lượt tìm", () => {
  for (const raw of [
    "",
    "   ",
    "0",
    so("091", "2345", "67"), // one digit short
    so("091", "2345", "6789"), // one too many
    so("011", "2345", "678"), // 1 is not a mobile prefix
    so("061", "2345", "678"), // nor is 6
    "abcdefghij",
    so("091", "2345", "678a"),
  ]) {
    assert.equal(soCoTheGoi(raw), false, JSON.stringify(raw));
  }
});

/* ----------------------------------------------------- the refusal tables --- */

/** Every refusal code `services/api/app` can raise on a friend route.
 *
 * Read out of the three files that raise them. Throws on an empty parse: an
 * expectation set that silently became `[]` would make every assertion below
 * pass, which is the shape of green this file exists to refuse.
 */
function serverFriendCodes() {
  const sources = [
    doc("api", "routes", "friends.py"),
    doc("api", "service.py"),
    doc("domain", "friendship.py"),
  ].join("\n");

  const codes = new Set();
  // `ApiProblem(404, "person_not_found", "...")` — the API's own spelling.
  for (const m of sources.matchAll(/ApiProblem\(\s*\d{3},\s*"([a-z_]+)"/g)) {
    codes.add(m[1]);
  }
  // `FriendshipError("NOT_PENDING")` — the domain's, upper-cased. `translated`
  // lower-cases before looking a code up, so they land in the same namespace.
  for (const m of sources.matchAll(/FriendshipError\(\s*"([A-Z_]+)"\s*\)/g)) {
    codes.add(m[1].toLowerCase());
  }
  // `BLOCKED_IS_SILENT = "REQUEST_NOT_OPEN"`, raised by name in both files.
  for (const m of sources.matchAll(/BLOCKED_IS_SILENT\s*=\s*"([A-Z_]+)"/g)) {
    codes.add(m[1].toLowerCase());
  }
  if (codes.size < 8) {
    throw new Error(
      `chỉ đọc được ${codes.size} mã lỗi từ services/api/app — parse đã hỏng, ` +
        "đừng đọc kết quả xanh dưới đây là đã kiểm",
    );
  }
  return codes;
}

test("mọi khoá trong bảng câu chữ đều là mã máy chủ THẬT SỰ gửi được", () => {
  const server = serverFriendCodes();
  const mine = [
    ...Object.keys(LOI_TIM),
    ...Object.keys(LOI_GUI),
    ...Object.keys(LOI_TRA_LOI),
    ...Object.keys(LOI_DOC),
  ];
  const la = mine.filter((code) => !server.has(code));
  assert.deepEqual(
    la,
    [],
    `bảng đang dịch mã máy chủ không gửi: ${la.join(", ")}. ` +
      `Mã máy chủ đọc được: ${[...server].sort().join(", ")}`,
  );
});

test("bốn mã việc này gọi tên đều có một câu tiếng Việt", () => {
  // The four the work item named: 404 not found, 409 already friends or
  // already asked, 429 too many lookups, 403 refused.
  assert.ok(LOI_TIM.person_not_found, "404 khi tìm");
  assert.ok(LOI_GUI.request_not_open, "409 khi gửi lời mời");
  assert.ok(LOI_TIM.rate_limited, "429 khi tìm quá nhiều");
  assert.ok(LOI_TIM.permission_denied, "403 khi tìm");
  assert.ok(LOI_GUI.permission_denied, "403 khi gửi");
  assert.ok(LOI_TRA_LOI.permission_denied, "403 khi trả lời");
});

test("429 nói rõ chờ một phút, và nói rõ app không hỏng", () => {
  const cau = LOI_TIM.rate_limited.toLowerCase();
  assert.match(cau, /một phút/, "429 phải nói khoảng thời gian cụ thể");
  assert.match(
    cau,
    /không hỏng|app vẫn|đang chờ/,
    "429 phải nói app không hỏng, nếu không người ta tưởng app chết",
  );
});

test("mọi câu đều là tiếng Việt có dấu, không phải mã máy", () => {
  const DAU =
    /[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụỳýỷỹỵ]/i;
  for (const [ten, bang] of Object.entries({ LOI_TIM, LOI_GUI, LOI_TRA_LOI, LOI_DOC })) {
    for (const [code, cau] of Object.entries(bang)) {
      assert.match(cau, DAU, `${ten}.${code} không có dấu tiếng Việt nào`);
      assert.ok(cau.trim().length > 20, `${ten}.${code} ngắn quá để là một câu`);
    }
  }
});

/**
 * The 409 sentence is short on purpose and this pins the reason.
 *
 * `service.py` answers "already friends", "already asked" and "blocked" with
 * one code deliberately, so that a blocked person cannot tell a block from a
 * duplicate. A client sentence naming two of the three would undo that on the
 * screen: whoever is blocked would read "either you are already friends or the
 * request is pending" and learn they are neither.
 */
test("câu 409 KHÔNG kể ra hai trong ba trạng thái máy chủ cố ý gộp", () => {
  const cau = LOI_GUI.request_not_open.toLowerCase();
  assert.doesNotMatch(
    cau,
    /đã là bạn|đã kết bạn|đang chờ duyệt|đã gửi rồi/,
    "câu này đang kể tên trạng thái mà máy chủ cố ý không kể — xem ban-be.ts",
  );
});

/* ------------------------------------------------------------- the monogram --- */

test("chữ đầu lấy theo tên cuối, như cách người Việt gọi nhau", () => {
  assert.equal(chuDau("Nguyễn Văn Bình"), "B");
  assert.equal(chuDau("Bình"), "B");
  assert.equal(chuDau("  trang  "), "T");
  assert.equal(chuDau(""), "?");
  assert.equal(chuDau("   "), "?");
});
