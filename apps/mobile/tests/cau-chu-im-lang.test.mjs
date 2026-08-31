/* Mỗi lý do AI không trả lời có một câu riêng, và câu đó không nói dối.
 *
 * ## Vì sao file này tồn tại
 *
 * `/contexts/{id}/ai-turn` trả về tám tên `reason` phân biệt được (#420), cộng
 * một cửa nữa KHÔNG nằm trong `reason`: HTTP 429 `companion_turn_rate_limited`.
 * Trước bản vá đi kèm file này, client gộp chúng lại còn ba câu:
 *
 *   - `already_spoke_last` + `rate_limited` + `cooldown` dùng CHUNG một câu,
 *   - `unavailable` dùng chung câu vét với bất kỳ tên nào máy chủ mới đặt ra,
 *   - và 429 rơi vào đường `hong`, in ra màn "Máy chủ trả lỗi 429" kèm nguyên
 *     văn `detail` của máy chủ.
 *
 * Nên hai người chạm hai cái trần khác nhau đọc đúng một câu và không ai biết
 * làm gì tiếp, còn cái trạng thái DUY NHẤT nghĩa là "AI đang hỏng" thì viết
 * cùng giọng với cái nghĩa là "nhóm cứ nhắn tiếp đi".
 *
 * ## Cổng này đo cái gì mà đọc bảng câu chữ bằng mắt không đo được
 *
 * 1. **Trôi từ vựng.** Danh sách tên KHÔNG viết tay ở đây: nó đọc lại từ
 *    `REASONS` trong ca test của backend, chính cái tập mà cổng `ast` bên đó
 *    tự dựng lại từ `plan_turn`. Backend thêm một reason thứ chín thì file này
 *    đỏ, chứ không phải màn hình hiện ra khoảng trắng.
 * 2. **Trôi CON SỐ.** Câu chữ nhắc "90 giây", "3 lượt", "20 tin". Ba số đó là
 *    `DEFAULT_LIMITS` trong `app/domain/companion.py`. Đổi nhịp bên backend mà
 *    câu chữ vẫn đọc số cũ là nói dối người dùng một cách rất khó thấy, nên ba
 *    số ấy cũng đọc lại từ Python.
 * 3. **Phân biệt được thật.** Hai reason dùng chung một chuỗi làm cổng đỏ. Đây
 *    chính là hình dạng của bản cũ.
 * 4. **Không lộ chữ của máy.** Không câu nào được chứa tên reason, chữ "lỗi",
 *    hay mã trạng thái HTTP.
 *
 * ## Nó KHÔNG chứng minh
 *
 * Rằng câu chữ tới được màn hình (đo ở `cau-chu-im-lang-web.test.mjs`, bằng
 * một cú bấm thật trong Chrome), rằng máy chủ thật trả về đúng những tên này
 * (đo ở `services/api/tests/api/test_companion_silence_vocabulary.py`), hay
 * rằng người thật hiểu câu chữ.
 *
 * Chạy từ apps/mobile:
 *
 *     tsc -p tsconfig.test.json && node tools/fixup-esm.mjs
 *     node --test tests/cau-chu-im-lang.test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  CAU_LY_DO_LA,
  CAU_NHOM_CHUA_MO_XONG,
  CAU_THEO_LY_DO,
  LY_DO_TRAN_PHUT,
  cauKhongTraLoiDuoc,
  goiAiTurn,
} from "../dist-test/screens/chat/ai.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const GOC_REPO = join(HERE, "..", "..", "..");

const CTX = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const ACTOR = "46b55e67-932b-5415-a5ee-08fb2641a4ff";

/** `reason: "ok"` là lượt AI CÓ nói. Nó nằm trong từ vựng của máy chủ nhưng
 *  không bao giờ cần câu chữ, vì đường đi của nó là vẽ cái thẻ. */
const KHONG_CAN_CAU = new Set(["ok"]);

/** Hai khoá client tự đặt, cố ý không có trong từ vựng 200 của máy chủ:
 *  `no_content` là thân rỗng / 204, `companion_turn_rate_limited` là mã của
 *  thân 429. Liệt kê ra để phép kiểm ngược (khoá thừa) vẫn cắn được. */
const KHOA_CUA_CLIENT = new Set(["no_content", LY_DO_TRAN_PHUT]);

/* ------------------------------------------------ đọc lại từ backend ----- */

function docFile(duong) {
  const day = join(GOC_REPO, duong);
  try {
    return readFileSync(day, "utf8");
  } catch (e) {
    // Fail loud. Một file backend bị đổi chỗ mà cổng này lặng lẽ bỏ qua thì nó
    // thành cổng chỉ chấm điểm chính mình.
    assert.fail(`không đọc được ${duong} để lấy từ vựng gốc: ${e.message}`);
  }
}

/** Tập tên `reason` mà backend tự ghim, đọc từ literal `REASONS = {...}`. */
function tuVungCuaMayChu() {
  const nguon = docFile("services/api/tests/api/test_companion_silence_vocabulary.py");
  const khoi = /^REASONS\s*=\s*\{([^}]*)\}/m.exec(nguon);
  assert.ok(khoi, "không tìm thấy literal REASONS trong ca test từ vựng của backend");
  const ten = [...khoi[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.ok(ten.length >= 8, `đọc được ${ten.length} tên trong REASONS, chờ ít nhất 8`);
  return new Set(ten);
}

/** `DEFAULT_LIMITS` của `plan_turn`, đọc từ chính module domain. */
function nhipCuaMayChu() {
  const nguon = docFile("services/api/app/domain/companion.py");
  const khoi = /^DEFAULT_LIMITS\s*=\s*\{([^}]*)\}/m.exec(nguon);
  assert.ok(khoi, "không tìm thấy DEFAULT_LIMITS trong app/domain/companion.py");
  const doc = (khoa) => {
    const m = new RegExp(`"${khoa}"\\s*:\\s*(\\d+)`).exec(khoi[1]);
    assert.ok(m, `DEFAULT_LIMITS không còn khoá ${khoa}`);
    return Number(m[1]);
  };
  return {
    tin: doc("window_messages"),
    luot: doc("max_ai_messages_per_window"),
    giay: doc("cooldown_seconds"),
  };
}

/** Cửa sổ giây của trần 429 trên chính route này. */
function cuaSoTran429() {
  const nguon = docFile("services/api/app/api/search_rate_limit.py");
  const m = /^RECEIPT_SCAN_WINDOW_SECONDS\s*=\s*(\d+)/m.exec(nguon);
  assert.ok(m, "không đọc được RECEIPT_SCAN_WINDOW_SECONDS");
  return Number(m[1]);
}

/* ------------------------------------------------ 1. đủ tên -------------- */

test("mọi reason của máy chủ đều có câu chữ ở client", () => {
  const tuVung = tuVungCuaMayChu();
  const thieu = [...tuVung].filter((r) => !KHONG_CAN_CAU.has(r) && !(r in CAU_THEO_LY_DO));
  assert.deepEqual(
    thieu,
    [],
    `máy chủ trả về ${thieu.join(", ")} mà client không có câu nào. Thêm vào ` +
      `CAU_THEO_LY_DO trong src/screens/chat/ai.ts, đừng để nó rơi vào câu vét.`,
  );
  console.log(`  từ vựng máy chủ: ${tuVung.size} tên, client có câu cho ${Object.keys(CAU_THEO_LY_DO).length}`);
});

test("không có khoá thừa: mỗi câu chữ ứng với một tên máy chủ thật sự dùng", () => {
  const tuVung = tuVungCuaMayChu();
  const thua = Object.keys(CAU_THEO_LY_DO).filter(
    (k) => !tuVung.has(k) && !KHOA_CUA_CLIENT.has(k),
  );
  // Một tên bị backend đổi để lại câu chữ chết ở đây, và câu chết thì trông y
  // hệt câu sống cho tới lúc có người đọc nó trên màn.
  assert.deepEqual(thua, [], `câu chữ cho tên máy chủ không còn dùng: ${thua.join(", ")}`);
});

/* ------------------------------------------------ 2. phân biệt được ------ */

test("không hai lý do nào dùng chung một câu", () => {
  const theoCau = new Map();
  for (const [ly, cau] of Object.entries(CAU_THEO_LY_DO)) {
    theoCau.set(cau, [...(theoCau.get(cau) ?? []), ly]);
  }
  const dungChung = [...theoCau.values()].filter((ds) => ds.length > 1);
  assert.deepEqual(
    dungChung,
    [],
    `những lý do này đọc ra cùng một câu: ${JSON.stringify(dungChung)}. Đây đúng ` +
      `là hình dạng của bản cũ, nơi ba lý do nhịp dùng chung một chuỗi.`,
  );
  // Câu vét cũng phải khác mọi câu có tên. Nếu nó trùng, thì một reason lạ và
  // một reason đã biết in ra cùng chữ, và cổng trên không thấy được.
  assert.equal(
    Object.values(CAU_THEO_LY_DO).includes(CAU_LY_DO_LA),
    false,
    "câu vét trùng với một câu có tên",
  );
  // "Nhóm chưa mở xong" là một sự kiện của client, không phải một reason. Nó
  // trùng câu với một reason nào đó thì hai nguyên nhân khác hẳn nhau lại đọc
  // giống nhau, đúng cái file này tồn tại để chặn.
  assert.equal(
    [...Object.values(CAU_THEO_LY_DO), CAU_LY_DO_LA].includes(CAU_NHOM_CHUA_MO_XONG),
    false,
    "câu nhóm-chưa-mở-xong trùng với một câu của máy chủ",
  );
});

/* ------------------------------------------------ 3. số phải khớp -------- */

test("con số trong câu chữ khớp DEFAULT_LIMITS của backend", () => {
  const nhip = nhipCuaMayChu();
  console.log(`  DEFAULT_LIMITS đọc từ Python: ${JSON.stringify(nhip)}`);

  // Bản đầu của ca này chỉ hỏi "số đúng có xuất hiện không", và một đột biến
  // đổi "chưa tới 90 giây" thành "chưa tới 60 giây" đi lọt: câu còn nhắc 90
  // giây một lần nữa ở vế sau, nên phép match vẫn xanh. Nên luật ở đây là
  // MỌI con số đi kèm đơn vị đều phải bằng hằng số của backend, không phải là
  // có ít nhất một chỗ đúng.
  const DON_VI = { giây: nhip.giay, lượt: nhip.luot, tin: nhip.tin };
  for (const [ly, cau] of Object.entries(CAU_THEO_LY_DO)) {
    for (const [donVi, dung] of Object.entries(DON_VI)) {
      for (const m of cau.matchAll(new RegExp(`(\\d+)\\s+${donVi}\\b`, "g"))) {
        assert.equal(
          Number(m[1]),
          dung,
          `${ly} nói "${m[0]}" nhưng backend để ${dung} ${donVi}: ${cau}`,
        );
      }
    }
  }

  // Và ba chỗ PHẢI nói ra con số, để một bản viết lại mơ hồ ("một lát", "vài
  // giây") không lặng lẽ qua được vòng trên bằng cách không có số nào cả.
  assert.match(CAU_THEO_LY_DO.cooldown, new RegExp(`${nhip.giay}\\s+giây`), "cooldown mất số giây");
  for (const ly of ["rate_limited", "asked_too_often"]) {
    assert.match(CAU_THEO_LY_DO[ly], new RegExp(`${nhip.luot}\\s+lượt`), `${ly}: mất số lượt`);
    assert.match(CAU_THEO_LY_DO[ly], new RegExp(`${nhip.tin}\\s+tin`), `${ly}: mất cỡ cửa sổ`);
  }
});

test("trần theo phút nói ra thời gian, trần theo lượt nói ra số lượt", () => {
  // Yêu cầu của Lead: rate_limited/429 phải kèm thời gian, không nói chung
  // chung. Có một chỗ phải nói khác: cái trần 3-trong-20 KHÔNG phải đồng hồ.
  // Chờ thêm phút nào cũng không gỡ được nó, chỉ tin mới đẩy lượt cũ ra khỏi
  // cửa sổ. Nên "thử lại sau N phút" ở đó là một cái đồng hồ không tồn tại, và
  // ca này ghim đúng ranh giới ấy: cửa nào là đồng hồ thì phải có đơn vị thời
  // gian, cửa nào là phép đếm thì phải có số đếm.
  assert.equal(cuaSoTran429(), 60, "cửa sổ 429 không còn là 60 giây, câu chữ phải sửa theo");
  assert.match(CAU_THEO_LY_DO[LY_DO_TRAN_PHUT], /phút/, "câu 429 không nói ra thời gian chờ");
  assert.match(CAU_THEO_LY_DO.cooldown, /giây/, "câu cooldown không nói ra thời gian chờ");
  assert.match(CAU_THEO_LY_DO.unavailable, /phút/, "câu unavailable không nói ra thời gian chờ");

  for (const ly of ["rate_limited", "asked_too_often"]) {
    assert.doesNotMatch(
      CAU_THEO_LY_DO[ly],
      /sau\s+\S*\s*phút/,
      `${ly} hứa một cái đồng hồ không tồn tại: trần này tính theo TIN, không theo phút`,
    );
    assert.match(CAU_THEO_LY_DO[ly], /nhắn thêm/, `${ly} không nói ra cách gỡ chặn`);
  }
});

/* ------------------------------------------------ 4. giọng người --------- */

test("không câu nào lộ chữ của máy hay viết như báo lỗi", () => {
  const moiCau = [...Object.values(CAU_THEO_LY_DO), CAU_LY_DO_LA, CAU_NHOM_CHUA_MO_XONG];
  const tenMay = [...Object.keys(CAU_THEO_LY_DO), "ok", "spoke", "reason"];
  for (const cau of moiCau) {
    for (const ten of tenMay) {
      assert.equal(cau.includes(ten), false, `câu chữ lộ tên máy "${ten}": ${cau}`);
    }
    assert.doesNotMatch(cau, /lỗi/i, `câu viết như báo lỗi: ${cau}`);
    // Mã trạng thái HTTP. 429 là cái duy nhất từng lọt ra màn qua đường `hong`.
    assert.doesNotMatch(cau, /\b(4\d\d|5\d\d)\b/, `câu in mã trạng thái HTTP: ${cau}`);
    assert.doesNotMatch(cau, /HTTP/i, `câu nhắc HTTP: ${cau}`);
    // Gạch dài có ca riêng cho cả cây (dau-gach-dai.test.mjs); nhắc lại ở đây
    // vì file này là nơi câu chữ mới được viết ra.
    assert.doesNotMatch(cau, /[—–]/, `câu dùng gạch dài: ${cau}`);
    assert.ok(cau.trim().length > 20, `câu quá ngắn để nói được việc gì: ${cau}`);
  }
});

test("không câu nào nói ra vì sao mô hình hỏng", () => {
  // `unavailable` gộp bốn nguyên nhân, và máy chủ vứt khác biệt đi CÓ CHỦ Ý vì
  // văn bản lỗi của provider mang theo cả API key lẫn nguyên văn lời nhóm
  // (#420). Client không được đoán bù phần đó.
  for (const tu of ["Gemini", "API key", "quota", "timeout", "JSON", "key"]) {
    assert.equal(
      CAU_THEO_LY_DO.unavailable.includes(tu),
      false,
      `câu unavailable đoán bù nguyên nhân bằng "${tu}", cái mà máy chủ cố ý không nói`,
    );
  }
});

/* ------------------------------------------------ 5. 429 trên dây -------- */

function res(body, { status = 200 } = {}) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => (typeof body === "string" ? (body ? JSON.parse(body) : null) : body),
    text: async () => text,
  };
}

async function withFetch(impl, fn) {
  const truoc = globalThis.fetch;
  globalThis.fetch = impl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = truoc;
  }
}

/** Thân 429 thật của `FixedWindowLimiter`: có `code` (chữ máy) và `detail`. */
const THAN_429 = {
  code: "companion_turn_rate_limited",
  detail: "Quá nhiều lượt hỏi trợ lý nhóm; tối đa 30 lượt mỗi 60 giây. Thử lại sau ít phút.",
};

test("429 lúc HỎI THẲNG ra câu có thời gian, không ra mã máy", async () => {
  const s = await withFetch(
    async () => res(THAN_429, { status: 429 }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x", hoiThang: true }),
  );
  console.log(`  429 + hoiThang -> ${s.kind} / ${s.reason} / "${s.cau}"`);
  assert.equal(s.kind, "khong-tra-loi-duoc");
  assert.equal(s.reason, LY_DO_TRAN_PHUT);
  assert.equal(s.cau, CAU_THEO_LY_DO[LY_DO_TRAN_PHUT]);
  // Trước bản vá, đây là "Máy chủ trả lỗi 429. companion_turn_rate_limited"
  // (docLoi đọc detail rồi code). Không chuỗi nào trong hai cái đó được có mặt
  // trong `cau`, và `cau` là thứ DUY NHẤT `xuLyAi` đưa lên màn.
  assert.equal(s.cau.includes("companion_turn_rate_limited"), false, "mã máy lọt ra câu chữ");
  assert.equal(s.cau.includes("429"), false, "mã trạng thái lọt ra câu chữ");
  // `reason` thì cố ý vẫn giữ tên máy: nó là khoá tra cứu và là thứ probe e2e
  // in ra, không phải thứ được render. Cái phải kiểm là nguyên văn của máy chủ
  // không đi theo trạng thái đi đâu cả.
  assert.equal(JSON.stringify(s).includes(THAN_429.detail), false, "nguyên văn detail của máy chủ lọt ra");
});

test("429 lúc AI TỰ lên tiếng thì vẽ ra không gì cả", async () => {
  // Cùng lớp với `rate_limited`: một cái trần, và không ai đang đợi câu trả
  // lời. Vẽ một dòng cảnh báo cho lượt không ai hỏi là tiếng ồn.
  const s = await withFetch(
    async () => res(THAN_429, { status: 429 }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x" }),
  );
  assert.equal(s.kind, "im-lang");
  assert.equal(s.reason, LY_DO_TRAN_PHUT);
  assert.equal("cau" in s, false);
});

test("mỗi tên trong từ vựng đi qua goiAiTurn ra đúng câu của nó", async () => {
  const tuVung = [...tuVungCuaMayChu()].filter((r) => !KHONG_CAN_CAU.has(r));
  const daThay = new Set();
  for (const reason of tuVung) {
    const s = await withFetch(
      async () => res({ context_id: CTX, spoke: false, reason, message: null }),
      () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x", hoiThang: true }),
    );
    assert.equal(s.kind, "khong-tra-loi-duoc", `${reason} không ra câu nào`);
    assert.equal(s.cau, CAU_THEO_LY_DO[reason], `${reason} ra câu sai`);
    assert.equal(daThay.has(s.cau), false, `${reason} lặp lại câu của một lý do khác`);
    daThay.add(s.cau);
    console.log(`  ${reason.padEnd(20)} -> "${s.cau.slice(0, 58)}…"`);
  }
});

test("một reason chưa từng thấy rơi vào câu vét, không rơi vào khoảng trắng", async () => {
  const s = await withFetch(
    async () => res({ context_id: CTX, spoke: false, reason: "quiet_hours", message: null }),
    () => goiAiTurn({ contextId: CTX, actorId: ACTOR, base: "http://x", hoiThang: true }),
  );
  assert.equal(s.kind, "khong-tra-loi-duoc");
  assert.equal(s.cau, CAU_LY_DO_LA);
  assert.equal(cauKhongTraLoiDuoc("quiet_hours"), CAU_LY_DO_LA);
});
