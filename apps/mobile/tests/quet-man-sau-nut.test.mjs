/* Every screen a cold URL can open is a screen the detector has actually seen.
 *
 * `quet-du-tab.test.mjs` closed this hole for the four tabs, and the hole
 * immediately reappeared one layer down. A screen put behind a button is not a
 * tab, so that file never looked at it, and the scan loop walked `#tab=` only:
 * Kỷ niệm shipped, was scanned zero times, and nothing anywhere said so. The
 * report listed four clean screens and was true about four of the eight.
 *
 * The lesson is not "add Kỷ niệm to a list". It is that the list of screens and
 * the list of scanned screens were two hand-maintained things that agreed only
 * while somebody remembered. So this file does not keep a list. It asks the
 * router which destinations open cold, and requires a scan row for each one.
 * `KetBan.tsx` -- 632 lines, arriving in #226 well after the scan loop was
 * written -- is exactly the case that would otherwise be found by nobody.
 *
 * There are no excused screens, and the first draft of this file learned why
 * the hard way. It excused `dang-ky` on the strength of `lien-ket.ts` saying
 * so -- "`vao=dang-ky` is deliberately NOT enough ... a link could put a person
 * straight into a form that writes to `people`" -- and probed the router with
 * `#vao=dang-ky&nguoi=minh` to confirm it. Both halves were wrong:
 *
 *   - `boQuaMoDau: false` does not stop that screen rendering. It stops entry
 *     to the SHELL. `AppRoot` checks `dangDangKy` *inside* its `!daVao` branch,
 *     so a bare `#vao=dang-ky` lands on the registration form -- the exact
 *     destination the comment says is prevented.
 *   - adding `&nguoi=minh` sets `boQuaMoDau` through a different clause
 *     entirely, so that probe skipped the form and measured the shell.
 *
 * So every name in the union gets a row, and the fragment each row uses is
 * checked against the router rather than assumed to be uniform. A comment
 * describing a protection is evidence of somebody's intent; only the decode
 * below is evidence of the behaviour.
 *
 * What this proves: the scan list covers every cold-openable screen. What it
 * does not prove: that a scan was run, that it ran on the current bundle, or
 * that it found nothing. Those are `imp detect` plus a person reading it --
 * ADR-0010 on why a digest is not evidence.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { docDiemDen } from "../dist-test/navigation/lien-ket.js";

const MOBILE_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const TOOL = join(MOBILE_ROOT, "tools/tab-snapshots.mjs");
const ROUTER = join(MOBILE_ROOT, "src/navigation/lien-ket.ts");

/**
 * The `frag` strings of `MAN_KHAC`, read out of the tool's source.
 *
 * Read as text rather than imported: `tab-snapshots.mjs` pulls in
 * `screen-snapshots.mjs`, which loads puppeteer from an absolute path under
 * `~/.claude`. Importing it here would make a unit test fail on any machine
 * that keeps the browser somewhere else, and fail in a way that reads like the
 * scan list is wrong rather than the import.
 */
function fragsDuocQuet() {
  const src = readFileSync(TOOL, "utf8");
  const block = /const MAN_KHAC = \[(.*?)\];/s.exec(src);
  // A regex that matches nothing makes every assertion below vacuously true,
  // which is the exact failure this file exists to catch. So the shape of the
  // block is itself an assertion.
  assert.ok(block, `không tìm thấy khối MAN_KHAC trong ${TOOL}`);

  // Both quote styles. The rows that name a person are template literals so
  // they can interpolate `NGUOI`; the `dang-ky` row must not name one, so it is
  // an ordinary string. A backtick-only pattern reads that row as absent and
  // reports the screen as unscanned while it is sitting right there -- which is
  // how this regex failed the first time it was run.
  const rows = [...block[1].matchAll(/\bfrag:\s*[`"]([^`"]+)[`"]/g)].map((m) => m[1]);
  assert.ok(rows.length > 0, "khối MAN_KHAC không có dòng nào");
  // Every row in the block has a frag, so a count that disagrees with the
  // number of `step:` keys means the pattern silently skipped one.
  const steps = [...block[1].matchAll(/\bstep:\s*"/g)].length;
  assert.equal(rows.length, steps, `đọc được ${rows.length} frag cho ${steps} dòng MAN_KHAC`);
  return rows;
}

/**
 * The entry-door screen names, read off the `ManVaoCua` union.
 *
 * That union is the file's own declaration of what exists, and it is what
 * `MAN_VAO_CUA` is built from one line below it. Reading the union rather than
 * the array means a name added to the type but forgotten in the array is still
 * demanded here -- the two drifting apart is its own bug.
 */
function manVaoCua() {
  const src = readFileSync(ROUTER, "utf8");
  const block = /export type ManVaoCua =([^;]+);/.exec(src);
  assert.ok(block, `không tìm thấy khai báo ManVaoCua trong ${ROUTER}`);

  const names = [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  assert.ok(names.length > 0, "union ManVaoCua không có tên nào");
  return names;
}

/** The `vao=` destination a fragment decodes to, or undefined. */
function vaoCua(frag) {
  return /(?:^|&)vao=([^&]+)/.exec(frag)?.[1];
}

test("mọi màn sau nút đều nằm trong danh sách quét", () => {
  const frags = fragsDuocQuet();
  const daQuet = new Set(frags.map(vaoCua).filter((v) => v !== undefined));

  // Named one by one rather than as a set difference: a failure here should
  // say which screen nobody has ever looked at.
  const thieu = manVaoCua().filter((vao) => !daQuet.has(vao));
  assert.deepEqual(
    thieu,
    [],
    `màn mở được bằng link nhưng chưa bao giờ được quét: ${thieu.join(", ")}`,
  );
});

test("fragment của mỗi dòng thật sự mở đúng màn nó đặt tên", () => {
  // The half that the first draft got wrong, so it is asserted rather than
  // trusted. A row whose fragment lands somewhere else still writes a file,
  // still gets a row in the report, and reports on the wrong screen under the
  // right name -- the quietest way a scan lies.
  for (const frag of fragsDuocQuet()) {
    const vao = vaoCua(frag);
    if (vao === undefined) continue;
    const diem = docDiemDen(`#${frag}`);

    assert.equal(diem.vao, vao, `#${frag}: router không nhận điểm đến "${vao}"`);

    // `dang-ky` renders from `AppRoot`'s pre-shell branch and the other three
    // render inside the shell, so the two want OPPOSITE answers here. Entering
    // the shell is what makes `#vao=dang-ky` miss the form entirely.
    const truocVo = vao === "dang-ky";
    assert.equal(
      diem.boQuaMoDau,
      !truocVo,
      truocVo
        ? `#${frag} vào thẳng vỏ tab nên đi vòng qua màn đăng ký, quét sẽ chụp nhầm tab`
        : `#${frag} không vào được vỏ tab nên quét sẽ chụp màn mở đầu`,
    );
  }
});

test("thẻ chi tiết địa điểm, mở bằng dia-diem=, cũng được quét", () => {
  // Not a `ManVaoCua`, so the loop above cannot see it, but the same hole in
  // the same shape: `docDiemDen` enters the shell on `dia-diem=` alone, which
  // makes the detail card a screen a URL names and a detector can reach.
  // Asserted separately rather than folded in, because a check that quietly
  // covers two mechanisms is a check that stops covering one of them.
  const frags = fragsDuocQuet().filter((f) => f.includes("dia-diem="));
  assert.ok(
    frags.length > 0,
    "thẻ chi tiết địa điểm mở được bằng link nhưng chưa bao giờ được quét",
  );

  for (const frag of frags) {
    const diem = docDiemDen(`#${frag}`);
    assert.ok(diem.boQuaMoDau, `${frag} không vào được thẳng, quét sẽ chụp màn mở đầu`);
    assert.equal(diem.tab, "kham-pha", `${frag} phải mở trên tab Khám phá`);
  }
});
