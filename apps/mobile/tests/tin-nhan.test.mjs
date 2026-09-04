/* What the group-chat logic is allowed to get wrong, as assertions rather than as taps.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/tin-nhan.test.mjs
 *
 * Layout is not checkable here. What is checkable, and what this file exists
 * for, is the set of traps that look fine on a phone and are wrong: a uuid5
 * that does not match the seed, a cursor used in the wrong direction, a
 * duplicate bubble, a card that draws `undefined`, a canned AI itinerary, an
 * em-dash in Vietnamese copy, a hex colour that bypasses the palette.
 */
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { DIRECTION_CONTRACT_NHOM_CHAT } from "../dist-test/ui/direction.js";
import { AI_WORK_ITEM, cauAiChuaNoiDuoc, goiAiTurn } from "../dist-test/screens/chat/ai.js";
import {
  dinhDangTienVnd,
  keHoachTuCard,
  khoangGia,
  theTuCard,
} from "../dist-test/screens/chat/ke-hoach.js";
import { khoiDongNhom, thanNhuSeed } from "../dist-test/screens/chat/nhom.js";
import {
  cursorCuNhat,
  cursorMoiNhat,
  messagesUrl,
  napTinCuHon,
  napTinMoiHon,
  napTinNhan,
  noiTinCuHon,
  noiTinMoiHon,
  tinHienThiLanDau,
} from "../dist-test/screens/chat/tin-nhan.js";
import { KHONG_GIAN_DEMO, KHONG_GIAN_DNS, khoaGhi, uuid5 } from "../dist-test/screens/chat/uuid5.js";

const CTX = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";

test("tên có dấu tiếng Việt băm UTF-8, không phải latin-1", () => {
  assert.equal(uuid5(KHONG_GIAN_DEMO, "person:Đức Ngọc"), "5ade38f8-8e92-5c36-b444-f4c39c203d55");
});

test("URL lần đầu không mang before hay after", () => {
  const url = messagesUrl("http://api/", CTX, { limit: 50 });
  assert.match(url, /^http:\/\/api\/contexts\/.*\/messages\?/);
  assert.match(url, /limit=50/);
  assert.doesNotMatch(url, /before=/);
  assert.doesNotMatch(url, /after=/);
});

test("định dạng tiền 17500000 thành 17.500.000đ, không float", () => {
  assert.equal(dinhDangTienVnd(17500000), "17.500.000đ");
  assert.equal(dinhDangTienVnd(0), "0đ");
  assert.equal(dinhDangTienVnd(999), "999đ");
  assert.ok(!dinhDangTienVnd(17500000).includes(","));
});

/* The server fingerprints an idempotent write over RAW BODY BYTES
 * (`app/api/idempotency.py`, `request_fingerprint`), so replaying the seed's
 * `POST /contexts` requires reproducing the seed's bytes, not its meaning.
 * The expectations below are not hand-typed: they are what
 * `python3 -c "import json; json.dumps(...)"` actually printed. If Python
 * ever changes its default separators or `ensure_ascii`, this goes red here
 * rather than as a 422 on a demo machine. */
test("thanNhuSeed dựng đúng byte mà json.dumps của Python in ra", () => {
  assert.equal(
    thanNhuSeed({ display_name: "Team Đà Lạt" }),
    '{"display_name": "Team \\u0110\\u00e0 L\\u1ea1t"}',
  );
  // A space after the colon and after the comma; JSON.stringify writes neither.
  assert.equal(thanNhuSeed({ a: "x", b: "ý" }), '{"a": "x", "b": "\\u00fd"}');
  // Quotes and backslashes keep the escaping both encoders already agree on.
  assert.equal(
    thanNhuSeed({ display_name: 'Ngọc "quoted" \\ back' }),
    '{"display_name": "Ng\\u1ecdc \\"quoted\\" \\\\ back"}',
  );
  // Pure ASCII is the case that hid this defect: both encoders agree except
  // for the separators, so a name like "Minh" replays and "Ngọc" does not.
  assert.equal(thanNhuSeed({ display_name: "Minh" }), '{"display_name": "Minh"}');
});

/* ------------------------------------------------ copy + palette -------- */

const VIET = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]/;