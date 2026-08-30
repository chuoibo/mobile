/* Every screen on the hero walk is either scanned by the detector or excused in writing.
 *
 * `quet-man-sau-nut.test.mjs` closed this hole for screens a cold URL can open,
 * by asking the router what exists instead of keeping a list. The hole survived
 * one layer further in, on the screens you can only reach by pressing: those
 * have no fragment, so no router can enumerate them, and the walk that reaches
 * them is itself the only declaration of what exists.
 *
 * `quet-man-sau-tap.mjs` carried a `CHUA_QUET` map naming five screens it did
 * not scan, each with a reason -- and its own comment said
 * `tests/quet-man-sau-tap.test.mjs` required every name to be scanned or listed.
 * That file did not exist. Nothing read `CHUA_QUET`, nothing compared it to
 * anything, and five screens sat in it reading like a governed exclusion while
 * being an ungoverned one. A comment describing a gate is evidence of somebody's
 * intent; only a test is evidence of the gate.
 *
 * The five were `nhap`, `de-xuat`, `dot-thu`, `ket-qua-thanh-toan`, `chia-se` --
 * the back half of the hero path, the screens where the money is proposed,
 * collected, turned into a VietQR and shared. They had never been measured once.
 *
 * What this proves: the scan list and the walk cannot drift apart without a
 * failure here. What it does NOT prove: that a scan was run, that it ran on the
 * current bundle, or that it came back clean. Those are `imp detect` plus a
 * person reading the output -- ADR-0010 on why a digest is not evidence.
 *
 * ## Cùng một lỗ, một tầng sâu hơn: ai đứng ra bảo lãnh cho con số
 *
 * Ba ca đầu hỏi màn nào ĐƯỢC quét. Ba ca cuối hỏi con số của màn đó dựa vào
 * đâu. Canary lái từng chạy MỘT lần trên đúng một kịch bản ghim (`de-xuat`, 23
 * bước) rồi cả bảng thừa hưởng kết quả, với lý lẽ "chạy cái dài nhất thì đợi
 * được mọi cái ngắn hơn". `de-xuat` không phải dài nhất: `dot-thu` 25 bước,
 * `ket-qua-thanh-toan` 27, `chia-se` 29. Phép suy luận chạy ngược chiều với
 * đúng ba màn cuối của đường đi hero, nên ba dòng `findings= 0` ấy không có gì
 * đỡ. Lý do viết ra để bào chữa (ba kịch bản kia vượt hạn 30000ms) chưa từng
 * được đo; đo rồi thì cả chín về đích trong 2.6-3.4 giây.
 *
 * Điều ba ca cuối chứng minh: không màn nào còn mượn được canary của màn khác,
 * và công cụ còn đủ ba trạng thái để nói "chưa kết luận được". Điều chúng KHÔNG
 * chứng minh: rằng canary thật sự đỏ khi detector đo sớm. Đó là hành vi, và
 * bằng chứng cho nó là bảng đột biến chạy tay trong PR, không phải file này.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const WALK = join(MOBILE_ROOT, "tools/screen-snapshots.mjs");
const SCAN = join(MOBILE_ROOT, "tools/quet-man-sau-tap.mjs");

/**
 * Read as text rather than imported, for the same reason the sibling gate does:
 * both tools load puppeteer from an absolute path under `~/.claude`. Importing
 * either here would fail on any machine that keeps the browser somewhere else,
 * and fail in a way that reads like the scan list is wrong rather than the
 * import.
 */
function doc(file) {
  return readFileSync(file, "utf8");
}

/**
 * Strip comments before pulling quoted names out of a block.
 *
 * Both blocks below are heavily commented, and the comments quote screen names
 * and file paths. Without this, `"Bỏ qua"` and `tests/quet-du-tab.test.mjs`
 * from the prose inside `STEPS` parse as screen names, the list comes back
 * wrong, and the assertion either fails for a fictional reason or -- worse --
 * passes because the junk happened to cover a real gap.
 */
function boChuThich(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

function khoi(src, mo, dong, ten, file) {
  const i = src.indexOf(mo);
  assert.notEqual(i, -1, `không tìm thấy khai báo ${ten} trong ${file}`);
  const j = src.indexOf(dong, i + mo.length);
  assert.notEqual(j, -1, `khối ${ten} trong ${file} không có chỗ đóng`);
  return src.slice(i + mo.length, j);
}

/** The walk's own declaration of which screens it visits, in order. */
function manTrenDuongDi() {
  const src = doc(WALK);
  const block = boChuThich(khoi(src, "export const STEPS = [", "];", "STEPS", WALK));
  const names = [...block.matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  // A pattern that matches nothing makes every assertion below vacuously true,
  // which is the exact failure this file exists to catch. So the shape of the
  // block is itself an assertion.
  assert.ok(names.length > 0, "STEPS không có tên màn nào");
  return names;
}

/** The screens the detector is actually pointed at. */
function manDaQuet() {
  const src = doc(SCAN);
  const block = boChuThich(khoi(src, "export const MAN_SAU_TAP = [", "\n];", "MAN_SAU_TAP", SCAN));
  const names = [...block.matchAll(/\bstep:\s*"([^"]+)"/g)].map((m) => m[1]);
  assert.ok(names.length > 0, "MAN_SAU_TAP không có dòng nào");
  return names;
}

/** The screens excused from scanning, mapped to the reason given. */
function manDuocThaBong() {
  const src = doc(SCAN);
  const block = boChuThich(khoi(src, "export const CHUA_QUET = {", "};", "CHUA_QUET", SCAN));
  const rows = [...block.matchAll(/["']?([\w-]+)["']?\s*:\s*"([^"]*)"/g)];
  return new Map(rows.map((m) => [m[1], m[2]]));
}

test("mọi màn trên đường đi đều được quét, hoặc được tha bổng có lý do", () => {
  const duongDi = manTrenDuongDi();
  const daQuet = new Set(manDaQuet());
  const thaBong = manDuocThaBong();

  // Named one by one rather than as a set difference: a failure here should say
  // which screen nobody has ever looked at, not just that a count disagrees.
  for (const man of duongDi) {
    const co = daQuet.has(man) || thaBong.has(man);
    assert.ok(
      co,
      `màn "${man}" nằm trên đường đi nhưng không được quét và cũng không có ` +
        `dòng nào trong CHUA_QUET nói vì sao. Một màn chưa ai đo bao giờ phải ` +
        `tốn của ai đó một câu giải thích.`,
    );
  }
});

test("không màn nào vừa được quét vừa bị liệt là chưa quét", () => {
  const daQuet = new Set(manDaQuet());
  for (const [man] of manDuocThaBong()) {
    assert.ok(
      !daQuet.has(man),
      `màn "${man}" vừa nằm trong MAN_SAU_TAP vừa nằm trong CHUA_QUET. Hai câu ` +
        `trả lời trái nhau cho cùng một màn: người đọc sẽ tin câu tiện hơn.`,
    );
  }
});

test("mỗi màn được tha bổng phải kèm lý do đọc được", () => {
  for (const [man, lyDo] of manDuocThaBong()) {
    assert.ok(
      lyDo.trim().length >= 20,
      `màn "${man}" bị liệt là chưa quét nhưng lý do chỉ có "${lyDo}". ` +
        `Một chuỗi rỗng biến CHUA_QUET thành chỗ giấu việc.`,
    );
  }
});

test("màn được quét nào cũng phải nằm trên đường đi", () => {
  const duongDi = new Set(manTrenDuongDi());
  for (const man of manDaQuet()) {
    assert.ok(
      duongDi.has(man),
      `MAN_SAU_TAP quét "${man}" nhưng STEPS không có màn đó. Hoặc tên gõ sai, ` +
        `hoặc đường đi đã đổi mà danh sách quét không đổi theo.`,
    );
  }
});

test("trang canary lái sinh theo từng màn, không phải một trang ghim", () => {
  const src = boChuThich(doc(SCAN));

  // Tên trang canary phải nội suy tên màn. Một tên hằng như `__canary-lai.html`
  // chỉ có thể phục vụ một màn, và mọi màn còn lại sẽ đi mượn kết quả của nó.
  assert.match(
    src,
    /__canary-lai-\$\{step\}\.html/,
    "không thấy trang canary lái nào mang tên theo màn. Nếu canary chạy trên một " +
      "trang cố định thì mọi màn khác đang mượn bằng chứng của màn đó.",
  );
  assert.ok(
    !/["'`]__canary-lai\.html["'`]/.test(src),
    "còn trang canary lái ghim cứng `__canary-lai.html`. Đó là dạng cũ: một màn " +
      "chứng minh, cả bảng hưởng.",
  );
});

test("không kịch bản nào được ghim làm canary cho cả bảng", () => {
  const src = boChuThich(doc(SCAN));
  // Ghim bằng tên màn là cách cũ, và nó hỏng vì tên được chọn (`de-xuat`) không
  // phải kịch bản dài nhất. Hỏi theo DANH SÁCH màn chứ không theo một tên, để ca
  // này còn bắt được cả khi người sau ghim nhầm sang màn khác.
  for (const man of manDaQuet()) {
    const ghim = new RegExp(`KICH_BAN_CANARY\\s*=\\s*["']${man}["']`);
    assert.ok(
      !ghim.test(src),
      `canary lái bị ghim vào riêng màn "${man}". Số bước không phải thời gian, ` +
        `và một kịch bản 9 bước vẫn có thể chứa một bước chậm, nên không màn nào ` +
        `bảo lãnh được cho màn khác.`,
    );
  }
});

test("công cụ có ba trạng thái, không phải hai", () => {
  const src = boChuThich(doc(SCAN));
  const dong = src.match(/process\.exitCode\s*=\s*([^;]+);/);
  assert.ok(dong, "không tìm thấy chỗ đặt process.exitCode trong công cụ quét");

  // Ba mã, và mã thứ ba phải đến từ một biến KHÁC `bad`. Nếu nó cũng đọc `bad`
  // thì "không biết" và "sạch" vẫn đang chung một ô, chỉ đổi tên.
  const bieuThuc = dong[1];
  for (const ma of ["0", "2", "4"]) {
    assert.match(
      bieuThuc,
      new RegExp(`\\b${ma}\\b`),
      `mã thoát không có trạng thái ${ma}. Cổng hai trạng thái đang giấu trạng ` +
        `thái thứ ba ở đâu đó: thường là nhập "chưa kết luận được" vào "đạt".`,
    );
  }
  assert.match(
    bieuThuc,
    /khongKetLuan/,
    "mã thoát không đọc số màn chưa kết luận được, nên một màn bị đo sớm vẫn ra " +
      "cùng mã thoát với một màn sạch.",
  );
});
