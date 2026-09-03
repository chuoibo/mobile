/* Every screen App.tsx mounts has a named answer to "what measures this?".
 *
 * The demo path is chụp bill -> AI đọc món -> gán món -> AI chia -> VietQR, and
 * on 2026-08-30 not one of those screens had ever been through the detector.
 * Nothing said so, because both ways of finding out are blind here:
 *
 *   - The URL probe (`tools/tab-snapshots.mjs`) can only open what
 *     `navigation/lien-ket.ts` accepts, and that is four `vao=` destinations
 *     plus tab / dia-diem / ban-do. ChupBill, KetQuaNhanDien, GoiYChia and
 *     KetQuaThanhToan are reached by tapping through the app, so the probe
 *     cannot navigate to them at all.
 *   - Scanning the source file instead reports zero. Measured the same day, a
 *     fixture carrying 1.2:1 text, 1.3:1 text and an 18px tap target scored
 *     3 findings written as .html and 0 written as .tsx. The detector parses
 *     markup; RN style objects are not markup. So a .tsx file-scan returning
 *     zero says nothing about the screen.
 *
 * Both roads produce the same number a genuinely clean screen produces, which
 * is why nine screens sat unmeasured under a table of green rows.
 *
 * This file does not measure any screen. It forces the question to be answered
 * in writing, once per screen, and turns a new unanswered screen red on the
 * commit that adds it -- which is the only moment anybody would find out.
 *
 * What it proves: every mounted screen carries either a probe step or a stated
 * reason it has none. What it does NOT prove: that the probe steps were run,
 * that they passed, or that a screen listed as unmeasured is fine. A reason in
 * `SO_DO` is a disclosure, never a clearance.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const APP = join(MOBILE_ROOT, "App.tsx");
const PROBE = join(MOBILE_ROOT, "tools/tab-snapshots.mjs");

/**
 * Screen modules `App.tsx` imports, read out of App.tsx rather than listed here.
 *
 * A hand-written list cannot notice the screen somebody adds tomorrow, and that
 * is the exact defect this file exists to catch -- so the left-hand side is
 * derived and only the answers are written down.
 *
 * Only a PascalCase final segment counts. `chat/nhom` and `tai-khoan/kiem-tra`
 * are helper modules that render nothing, and holding them to a probe step
 * would teach nobody anything.
 */
function manDuocMount() {
  const src = readFileSync(APP, "utf8");
  const mods = [...src.matchAll(/from "\.\/src\/screens\/([A-Za-z0-9/-]+)"/g)].map((m) => m[1]);
  return [...new Set(mods)].filter((m) => /^[A-Z]/.test(m.split("/").pop())).sort();
}

/**
 * Step names the URL probe actually drives to, read out of the probe's own
 * source. Claiming coverage from a step the probe does not have is the same
 * lie as claiming it from no step at all, so the right-hand side is derived too.
 */
function buocCuaProbe() {
  const src = readFileSync(PROBE, "utf8");
  const steps = [...src.matchAll(/\bstep:\s*"([^"]+)"/g)].map((m) => m[1]);
  return new Set(steps);
}

/**
 * Scan-page parameters `App.tsx` really routes, read out of its own source.
 *
 * Same principle as `buocCuaProbe` above: a screen claiming an address it does
 * not have is the same lie as claiming coverage from no address at all, and it
 * is the easier of the two to write by accident -- rename the parameter in
 * `App.tsx` and every claim here keeps reading true.
 *
 * Two spellings, because `App.tsx` uses two. `manThamSo() === "x"` is an exact
 * destination; `manThamSo()?.startsWith("x")` covers a family (`doc-bill` and
 * `doc-bill-chuan-bi` are one screen at two moments).
 */
function thamSoQuetCuaApp() {
  const src = readFileSync(APP, "utf8");
  return {
    dung: new Set([...src.matchAll(/manThamSo\(\)\s*===\s*"([^"]+)"/g)].map((m) => m[1])),
    dau: [...src.matchAll(/manThamSo\(\)\?\.startsWith\("([^"]+)"\)/g)].map((m) => m[1]),
  };
}

/**
 * The answer for each mounted screen. Three kinds of answer, and the
 * difference between them is what somebody reading a green row is entitled to
 * believe:
 *
 *   `do`    -- the URL probe walks it, so a screenshot and a needle exist.
 *   `quet`  -- `App.tsx` routes a `?man=` scan page that mounts the real
 *              component with a frozen fixture. Reachable by a detector, a
 *              screenshot pass and an accessibility sweep, all of which load a
 *              URL cold. NOT walked by the probe, so no needle guards it.
 *   `chuaDo`-- nothing can open it. State the reason in words.
 *
 * `quet` is a weaker claim than `do` on purpose and must not be read as one.
 * It says an address exists and the real component renders at it; it does not
 * say anybody ran anything, and it cannot say the screen behaves the same on
 * the live flow, because a fixture is not a server. What it does buy is the
 * thing the ten `chuaDo` rows below cost: the screen stops being invisible to
 * every tool this repo owns.
 *
 * Reducing this list means giving a screen a real way in -- a `vao=`
 * destination plus a probe row, or a `?man=` scan page -- not deleting a line.
 */
const SO_DO = {
  // rd-fe. The bill-reading wait, at both of its stages.
  ChupBill: { quet: "doc-bill" },
  // The two middle screens of the demo path. Until frontend-tt-0016 these were
  // the last two on it that no machine could open at all.
  KetQuaNhanDien: { quet: "nhan-dien" },
  GoiYChia: { quet: "goi-y-chia" },
  KetQuaThanhToan: { quet: "ket-qua-thanh-toan" },
  // The first and third steps of the money walk. Both read `chuaDo` until
  // frontend-tt-0003 -- "only reachable from inside a group", "only after there
  // are obligations to gather" -- which was true and was still an unmeasured
  // screen. `quet` and not `do`: each address mounts the real component over a
  // frozen fixture, so a detector and a screenshot pass can open them cold,
  // and no probe row walks either against a server.
  NhapKhoanChi: { quet: "nhap-khoan-chi" },
  // Two addresses behind one key, same as the vote. `?man=dot-thu` is the board
  // before publishing, carrying the gate card and the refusal copy; `dot-thu-da-phat`
  // is after, which drops that card, swaps the footer and grows a button on
  // every unsettled row. Neither state can be pressed into the other without a
  // server, so one address would have left half the screen unmeasured.
  DotThu: { quet: "dot-thu" },
  // Added by #312 (F26) and caught by this gate the first time the branch was
  // rebased onto it -- twenty minutes after that PR merged, before anybody had
  // scanned the screen. This is the case the file was written for.
  KetQuaQuetAnh: { chuaDo: "F26; chỉ tới được sau khi chọn ảnh chụp màn hình để quét, không có vao=" },
  ChiaSe: { chuaDo: "mở bằng share sheet của hệ điều hành, không phải một URL" },
  DeXuat: { chuaDo: "render trong luồng chat, không phải một đích điều hướng riêng" },
  // F17 and F22, added with the screens that pay off six routes nobody could
  // reach. `quet` and not `do`: each has a `?man=` address that mounts the real
  // component over a frozen fixture, and no probe row, so a detector and a
  // screenshot pass can load them cold but nothing walks them against a server.
  //
  // The vote has two addresses behind one key. `?man=binh-chon` is the open
  // ballot; `?man=binh-chon-hoa` is the closed TIE, which is the state the
  // surface exists for and the one no amount of pressing can reach from the
  // other. A single address here would have left the screen's whole reason for
  // being unmeasured while this row read green.
  "binh-chon/BinhChon": { quet: "binh-chon" },
  "bill/MonCuaToi": { quet: "mon-cua-toi" },
  // The step wrapper around the screen above. It renders no pixels of its own
  // -- `?man=mon-cua-toi` scans the same `MonCuaToi` markup -- so the detector
  // question is already answered on that row. What this wrapper adds is the
  // bill, the identity and the write, and those are measured by pressing them:
  // `duong-vao-mon-cua-toi.test.mjs` walks the hero path in Chrome, opens it
  // from `goi-y`, unticks two dishes, saves, and reopens to see what the server
  // kept. A detector pass would say nothing about any of that.
  "bill/BuocMonCuaToi": { chuaDo: "vỏ bọc bước, không vẽ gì riêng — đo bằng duong-vao-mon-cua-toi.test.mjs" },
  "nhan-mat/NhanMatTrenAnh": { quet: "nhan-mat" },
  // F14. Inside the app this screen sits three taps deep -- a group, a trip in
  // it, and a roster read -- so nothing that loads a URL cold could reach it.
  // `quet` and not `do`: the address mounts the real component over a frozen
  // fixture carrying all four row states, and no probe row walks it against a
  // server.
  "len-plan/MoiVaoChuyen": { quet: "moi-vao-chuyen" },
};

test("mọi màn App.tsx mount đều có câu trả lời cho 'cái gì đo màn này'", () => {
  const mounted = manDuocMount();

  // A regex that matched nothing would make every assertion below vacuously
  // true -- the failure this file exists to catch, wearing this file's own
  // clothes. So the derivation is itself an assertion.
  assert.ok(mounted.length > 0, `không đọc được màn nào từ ${APP}`);

  const khai = Object.keys(SO_DO).sort();

  // Named one by one rather than as a set difference: a failure should say
  // which screen nobody has answered for, not that two lists differ.
  const thieu = mounted.filter((m) => !(m in SO_DO));
  assert.deepEqual(
    thieu,
    [],
    `màn được mount nhưng chưa ai nói cái gì đo nó:\n  ${thieu.join("\n  ")}\n` +
      "Thêm một dòng vào SO_DO: do:'<step>' nếu probe mở được, chuaDo:'<lý do>' nếu không.",
  );

  const thua = khai.filter((m) => !mounted.includes(m));
  assert.deepEqual(
    thua,
    [],
    `SO_DO khai màn mà App.tsx không còn mount:\n  ${thua.join("\n  ")}`,
  );
});

test("màn khai là đã đo phải trỏ vào một step probe có thật", () => {
  const steps = buocCuaProbe();
  assert.ok(steps.size > 0, `không đọc được step nào từ ${PROBE}`);

  const ma = [];
  for (const [man, o] of Object.entries(SO_DO)) {
    if (o.do && !steps.has(o.do)) ma.push(`${man}: step "${o.do}" không có trong probe`);
  }
  assert.deepEqual(ma, [], `khai đã đo bằng một step không tồn tại:\n  ${ma.join("\n  ")}`);
});

test("màn khai có trang quét phải trỏ vào một ?man= App.tsx thật sự định tuyến", () => {
  const { dung, dau } = thamSoQuetCuaApp();

  // The derivation is itself an assertion, for the same reason as above: a
  // regex that matched nothing would wave every `quet` row through.
  assert.ok(
    dung.size > 0,
    `không đọc được tham số quét nào từ ${APP} -- regex hỏng, mọi hàng quet sẽ tự xanh`,
  );

  const ma = [];
  for (const [man, o] of Object.entries(SO_DO)) {
    if (!o.quet) continue;
    const co = dung.has(o.quet) || dau.some((p) => o.quet.startsWith(p));
    if (!co) ma.push(`${man}: ?man=${o.quet} không được App.tsx định tuyến`);
  }
  assert.deepEqual(ma, [], `khai có trang quét bằng một địa chỉ không tồn tại:\n  ${ma.join("\n  ")}`);
});

test("mỗi màn chưa đo được phải kèm lý do bằng chữ, không để trống", () => {
  const rong = Object.entries(SO_DO)
    .filter(
      ([, o]) => !o.do && !o.quet && (typeof o.chuaDo !== "string" || o.chuaDo.trim().length < 10),
    )
    .map(([man]) => man);
  assert.deepEqual(
    rong,
    [],
    `chưa đo được mà không nói vì sao:\n  ${rong.join("\n  ")}`,
  );

  // Printed rather than asserted against a fixed number on purpose. A ratchet
  // here would go red the day somebody adds a screen honestly, and the point
  // is to keep the count visible, not to freeze it. Nine of nine unmeasured is
  // the number this file was written to stop being invisible; the split below
  // is what stops "reachable by a scan page" being read as "walked by the
  // probe", which is a strictly weaker claim.
  const tong = Object.keys(SO_DO).length;
  const quaProbe = Object.values(SO_DO).filter((o) => o.do).length;
  const quaTrangQuet = Object.values(SO_DO).filter((o) => !o.do && o.quet).length;
  const chuaDo = Object.values(SO_DO).filter((o) => !o.do && !o.quet).length;
  console.log(
    `# màn App.tsx mount: ${tong}, probe đi qua: ${quaProbe}, ` +
      `có địa chỉ quét: ${quaTrangQuet}, chưa máy nào đo được: ${chuaDo}`,
  );
});
