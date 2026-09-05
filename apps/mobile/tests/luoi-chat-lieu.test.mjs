/**
 * The material grid of `ui/Grain.tsx`: covers its box, stays under the view
 * budget, and draws nothing for a box that has not been laid out yet.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { luoiChatLieu } from "../dist-test/rudi/ui/luoi-chat-lieu.js";

test("phone 411x914 @2.625 (emulator): tile is the PNG at device pixels, 50 tiles cover the box", () => {
  const g = luoiChatLieu(411, 914, 2.625);
  assert.ok(Math.abs(g.tile - 256 / 2.625) < 1e-9);
  assert.deepEqual([g.cols, g.rows], [5, 10]);
  assert.ok(g.cols * g.tile >= 411 && g.rows * g.tile >= 914, "grid must cover the box");
});

test("tablet 800x1280 @2 grows the tile so the layer stays under 60 views, and still covers", () => {
  const g = luoiChatLieu(800, 1280, 2);
  assert.ok(g.cols * g.rows <= 60, `${g.cols * g.rows} views`);
  assert.ok(g.cols * g.tile >= 800 && g.rows * g.tile >= 1280);
  assert.equal(g.tile, 256);
});

test("budget holds for any box up to 4k dp on any density", () => {
  for (const ratio of [1, 1.5, 2, 2.625, 3, 3.5]) {
    for (const [w, h] of [[56, 320], [360, 640], [411, 914], [800, 1280], [1600, 2560], [4000, 4000]]) {
      const g = luoiChatLieu(w, h, ratio);
      assert.ok(g.cols * g.rows <= 60, `${w}x${h}@${ratio}: ${g.cols * g.rows}`);
      assert.ok(g.cols * g.tile >= w && g.rows * g.tile >= h, `${w}x${h}@${ratio} not covered`);
    }
  }
});

test("no size yet (or a bad ratio) draws nothing rather than NaN tiles", () => {
  assert.deepEqual(luoiChatLieu(0, 0, 2.625), { tile: 0, cols: 0, rows: 0 });
  assert.deepEqual(luoiChatLieu(0, 900, 2.625), { tile: 0, cols: 0, rows: 0 });
  assert.deepEqual(luoiChatLieu(NaN, 900, 2.625), { tile: 0, cols: 0, rows: 0 });
  const g = luoiChatLieu(360, 640, 0);
  assert.equal(g.tile, 256, "ratio below 1 clamps to 1");
});
