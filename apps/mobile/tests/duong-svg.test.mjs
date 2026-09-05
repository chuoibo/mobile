/**
 * Path grammar of the kit's SVG shapes, parsed the way react-native-svg's Java
 * `PathParser` parses it: explicit commands, fixed arity, plain decimals.
 *
 * Why a node test and not the emulator: a malformed `d` throws at mount inside
 * Fabric and kills the app on its first frame; the board then goes red on all
 * ten flows at once and says nothing about which shape did it. The 2026-09-05
 * board did exactly that for a tape edge ending in `L Z`. The web export is
 * blind (browsers draw a truncated path) and so is tsc (it is a string).
 */
import assert from "node:assert/strict";
import test from "node:test";

import { duongCongS, duongVachSang, duongWashiXeMep } from "../dist-test/rudi/ui/duong-svg.js";

const ARITY = { M: 2, L: 2, C: 6, Z: 0 };
const SO = /^-?\d+(\.\d+)?$/;

/** Parse like the Java side: throw on anything it would refuse. */
function phanTich(d) {
  const tokens = d.trim().split(/[\s,]+/);
  const cmds = [];
  let i = 0;
  while (i < tokens.length) {
    const c = tokens[i++];
    assert.ok(c in ARITY, `lệnh lạ «${c}» trong: ${d}`);
    const args = [];
    for (let k = 0; k < ARITY[c]; k++) {
      const t = tokens[i++];
      assert.ok(t !== undefined && SO.test(t), `lệnh ${c} thiếu/sai số «${t}» tại token ${i - 1} trong: ${d}`);
      args.push(Number(t));
    }
    cmds.push({ c, args });
  }
  return cmds;
}

test("washi xé mép: đường hợp lệ ở mọi cỡ, kín, nằm trong hộp, và hai mép thật sự răng cưa", () => {
  for (const w of [120, 121, 200, 333, 1000]) {
    for (const h of [30, 39.5, 40, 44]) {
      const d = duongWashiXeMep(w, h);
      const cmds = phanTich(d);
      assert.equal(cmds[0].c, "M", d.slice(0, 40));
      assert.equal(cmds.at(-1).c, "Z");
      // The bug: an `L` right before `Z` with no numbers. Arity parsing above
      // would throw; this makes the claim explicit for the reader.
      assert.ok(!/L\s+Z/.test(d) && !/L\s*$/.test(d.replace(/Z$/, "").trim()), d.slice(-40));
      const xs = cmds.filter((k) => k.args.length === 2).map((k) => k.args[0]);
      const ys = cmds.filter((k) => k.args.length === 2).map((k) => k.args[1]);
      assert.ok(Math.min(...xs) >= 0 && Math.max(...xs) <= w, `x ngoài hộp ${w}: ${Math.min(...xs)}..${Math.max(...xs)}`);
      assert.ok(Math.min(...ys) >= 0 && Math.max(...ys) <= h, `y ngoài hộp ${h}: ${Math.min(...ys)}..${Math.max(...ys)}`);
      const traiX = new Set(xs.filter((x) => x < w / 2));
      const phaiX = new Set(xs.filter((x) => x >= w / 2));
      assert.ok(traiX.size >= 2 && phaiX.size >= 2, `mép phải răng cưa: trái ${traiX.size} giá trị, phải ${phaiX.size}`);
    }
  }
});

test("washi: cùng cỡ thì cùng đường (không nhấp nháy khi re-layout), khác bề rộng thì xé khác", () => {
  assert.equal(duongWashiXeMep(200, 40), duongWashiXeMep(200, 40));
  assert.notEqual(duongWashiXeMep(200, 40), duongWashiXeMep(201, 40));
});

test("đường cong S: một M và một C, số thập phân thường, điểm đầu/cuối khớp d", () => {
  for (const [w, h] of [[300, 220], [88, 60], [1, 1], [1233, 731]]) {
    for (const dir of ["down", "up"]) {
      const { d, diem } = duongCongS(w, h, dir);
      const cmds = phanTich(d);
      assert.deepEqual(cmds.map((k) => k.c), ["M", "C"], d);
      const dau = diem(0), cuoi = diem(1);
      assert.ok(Math.abs(dau.x - cmds[0].args[0]) < 0.01 && Math.abs(dau.y - cmds[0].args[1]) < 0.01);
      assert.ok(Math.abs(cuoi.x - cmds[1].args[4]) < 0.01 && Math.abs(cuoi.y - cmds[1].args[5]) < 0.01);
      for (const t of [0.25, 0.5, 0.75]) {
        const q = diem(t);
        assert.ok(q.x >= 0 && q.x <= w && q.y >= 0 && q.y <= h, `điểm ngoài hộp tại t=${t}`);
      }
    }
  }
});

test("vạch sáng: M + L, không số mũ ngay cả với bề rộng lẻ", () => {
  for (const w of [17, 120.4, 999.99]) {
    const cmds = phanTich(duongVachSang(w));
    assert.deepEqual(cmds.map((k) => k.c), ["M", "L"]);
  }
  assert.ok(!/e/i.test(duongVachSang(1e-7)));
});
