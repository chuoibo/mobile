/* Nothing that was thrown reaches a screen as machine text -- on any screen, not just the two that were photographed.
 *
 * rd-qa-37 photographed `[object HTMLCanvasElement]` on the bill flow, and the
 * fix for it (bug-010822, #212) introduced `moTaLoi` and routed `App.tsx`'s two
 * catch sites through it. That closed the two sites somebody had a photograph
 * of. It did not close the class.
 *
 * Sixteen more sites spelled the same read as `(e as Error).message`. A cast is
 * not a check: TypeScript believes it and the runtime does not, and each of
 * those values flows into a `detail` field that four Khám phá dead ends, the
 * chat AI line, and the group-loading card interpolate straight into body text.
 * Measured on the code as it stood, one `throw` produced three different
 * failures:
 *
 *     thrown value                     what the screen got
 *     Error("that")                    Chi tiết: that                  <- fine
 *     "chuỗi" / {} / a canvas          Chi tiết: undefined
 *     null / undefined                 TypeError, INSIDE the catch
 *     Error with .message = a canvas   Chi tiết: [object HTMLCanvasElement]
 *
 * The middle row is the one worth pausing on: the error handler is the second
 * thing to fail, so the screen shows neither the failure nor the explanation.
 * The last row is bug-010822 itself, alive on screens its fix never touched.
 *
 * WHAT THIS FILE PROVES. Every entry point that owns one of those sites is run
 * with a transport that throws each of seven shapes, and the string that comes
 * back out is checked for being a string at all, for `[object `, and for the
 * word `undefined`. Then the two Khám phá cards are rendered through
 * react-native-web -- the same substitution Expo's web build performs -- and
 * the emitted markup is read, because a `detail` that is clean in a return
 * value can still be interpolated badly by a template one line later. That is
 * the failure this repo has already had to learn twice, and the reason the
 * render half is here rather than trusted to the unit half.
 *
 * WHAT IT DOES NOT PROVE. That the sentences are the right sentences, that iOS
 * and Android draw them, or that a person reading one knows what to do next.
 * The first is `imp detect` and a person; the second is a different bridge.
 *
 * The last test is a source read and is written as a gate with a self-check,
 * because a source read is weaker than a render and this repo has shipped
 * "green because it matched a comment" three times in one day. It is narrow on
 * purpose: `strict` already makes a bare `e.message` a compile error (TS18046),
 * so an explicit cast is the only remaining way to reach `.message` on a caught
 * value without checking it. The gate looks for the cast, and `tsc` covers the
 * rest.
 *
 * Run from apps/mobile:
 *     npx tsc -p tsconfig.test.json && node tools/fixup-esm.mjs && node --test tests/loi-la-lung.test.mjs
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import ts from "typescript";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CAU_KHONG_RO, chiTietLoi, moTaLoi } from "../dist-test/ui/loi-tren-man.js";
import { themChiTiet } from "../dist-test/ui/loi-may-chu.js";
import { fetchPlaces } from "../dist-test/screens/kham-pha/places.js";
import { askSearch } from "../dist-test/screens/kham-pha/tim-kiem.js";
import { goiAiTurn } from "../dist-test/screens/chat/ai.js";
import { khoiDongNhom } from "../dist-test/screens/chat/nhom.js";
import {
  guiTheAi,
  guiTinNhan,
  napTinCuHon,
  napTinMoiHon,
  napTinNhan,
} from "../dist-test/screens/chat/tin-nhan.js";
import { ChuaCoDuLieu } from "../dist-test/screens/kham-pha/KhamPha.js";
import { TimKhongDuoc } from "../dist-test/screens/kham-pha/CauAiHieu.js";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

/* -------------------------------------------------------------------------
 * The values libraries really throw
 * ---------------------------------------------------------------------- */

/** What `expo-image-manipulator` rejects with on web when a file will not decode.
 *
 * A real `HTMLCanvasElement` cannot exist under bare node, and importing a DOM
 * to get one would test jsdom's `toString` rather than ours. The single
 * property that produced the bug is that `String()` of it is
 * `[object HTMLCanvasElement]`, and `Symbol.toStringTag` reproduces exactly
 * that. Same construction as `anh-hong.test.mjs`, deliberately: if the two
 * files disagreed about what the thrown value looks like, one of them would be
 * testing something the app never sees.
 */
function canvasGiaVo() {
  return { [Symbol.toStringTag]: "HTMLCanvasElement" };
}

/** A label for a thrown value, for use in an assertion message.
 *
 * `String(x)` is not total: `Object.create(null)` has no `toString` and no
 * `Symbol.toPrimitive`, so converting it raises `TypeError: Cannot convert
 * object to primitive value` -- and node builds assertion messages EAGERLY, on
 * every iteration, pass or fail. An unconvertible label therefore does not
 * merely read badly, it throws out of the loop and silently drops every case
 * queued behind it. `anh-hong.test.mjs` learned this the expensive way; the
 * total form is `Object.prototype.toString.call`, which also honours
 * `Symbol.toStringTag` and so labels the fake canvas with the exact string
 * this file exists to keep off the screen.
 */
function nhan(thu) {
  return Object.prototype.toString.call(thu);
}

/** Every shape rd-fe-26 names, plus the two that actually carry `[object ` through.
 *
 * `Error` with a DOM node for a `.message` is not a hypothetical: `.message` is
 * a string only by convention, nothing enforces it, and an `instanceof Error`
 * guard on its own lets it straight through to `.trim()`. It is the one shape
 * that defeats the obvious fix, which is why it is in the list.
 */
const NEM = [
  ["Error có câu", new Error("Không kết nối được tới máy chủ 10.0.0.4:8000.")],
  ["Error rỗng", new Error("")],
  ["chuỗi trần", "hỏng rồi"],
  ["object trần", {}],
  ["object không prototype", Object.create(null)],
  ["HTMLCanvasElement", canvasGiaVo()],
  ["null", null],
  ["undefined", undefined],
  ["số", 500],
  ["Error .message là canvas", Object.assign(new Error("x"), { message: canvasGiaVo() })],
];

/** The check every screen-facing string has to pass, whatever was thrown. */
function khongPhaiChuMay(cau, canh) {
  assert.equal(typeof cau, "string", `${canh}: không trả về chuỗi (${nhan(cau)})`);
  assert.ok(!cau.includes("[object "), `${canh}: lọt "[object " lên màn -> ${cau}`);
  assert.ok(!/\bundefined\b/.test(cau), `${canh}: lọt "undefined" lên màn -> ${cau}`);
  assert.ok(!/\bnull\b/.test(cau), `${canh}: lọt "null" lên màn -> ${cau}`);
}

/* -------------------------------------------------------------------------
 * The normaliser itself
 * ---------------------------------------------------------------------- */

test("chiTietLoi không bao giờ ném, và không bao giờ trả về chữ của máy", () => {
  for (const [ten, thu] of NEM) {
    let ra;
    assert.doesNotThrow(() => {
      ra = chiTietLoi(thu);
    }, `chiTietLoi ném khi gặp ${ten} (${nhan(thu)})`);
    khongPhaiChuMay(ra, `chiTietLoi(${ten})`);
  }
});

test("moTaLoi luôn là một câu tiếng Việt, không bao giờ rỗng", () => {
  for (const [ten, thu] of NEM) {
    let ra;
    assert.doesNotThrow(() => {
      ra = moTaLoi(thu);
    }, `moTaLoi ném khi gặp ${ten} (${nhan(thu)})`);
    khongPhaiChuMay(ra, `moTaLoi(${ten})`);
    assert.notEqual(ra.trim(), "", `moTaLoi(${ten}) trả về chuỗi rỗng`);
  }
});

test("một Error thật vẫn nói bằng câu của chính nó", () => {
  // The `instanceof Error` half was never the bug and must not be collateral
  // damage: every sentence this app authors travels inside an `Error`.
  const that = new Error("Không kết nối được tới máy chủ 10.0.0.4:8000.");
  assert.equal(chiTietLoi(that), "Không kết nối được tới máy chủ 10.0.0.4:8000.");
  assert.equal(moTaLoi(that), "Không kết nối được tới máy chủ 10.0.0.4:8000.");
});

test("Error rỗng và Error có .message không phải chuỗi đều rơi về câu không rõ", () => {
  assert.equal(moTaLoi(new Error("   ")), CAU_KHONG_RO);
  assert.equal(moTaLoi(Object.assign(new Error("x"), { message: canvasGiaVo() })), CAU_KHONG_RO);
});

test("themChiTiet bỏ hẳn nhãn khi không còn gì để nói", () => {
  // This is the half `chiTietLoi` returning "" creates. Without it the screen
  // reads "Không mở được máy chủ. Chi tiết:" and then the edge of the card,
  // which looks like a sentence that got cut off rather than a refusal.
  assert.equal(themChiTiet("Không mở được máy chủ.", ""), "Không mở được máy chủ.");
  assert.equal(themChiTiet("Không mở được máy chủ.", "   "), "Không mở được máy chủ.");
  assert.equal(themChiTiet("Hỏng.", "ECONNREFUSED"), "Hỏng. Chi tiết: ECONNREFUSED");
});

/* -------------------------------------------------------------------------
 * Every entry point that owned one of the sixteen sites
 * ---------------------------------------------------------------------- */

/** A transport that rejects, which is the network half of every pair. */
function nemKhiGoi(thu) {
  return async () => {
    throw thu;
  };
}

/** A transport that answers 200 and then throws while the body is read.
 *
 * This is the parse half. It matters separately because the two catches sit on
 * opposite sides of the status checks and a fix applied to one is invisible to
 * the other -- which is exactly how #212 closed two sites and left sixteen.
 */
function noiRoiNemKhiDoc(thu) {
  return async () => ({
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    async json() {
      throw thu;
    },
    async text() {
      throw thu;
    },
  });
}

/** Pull every string a state object would put in front of a person. */
function chuoiTrongTrangThai(state) {
  const ra = [];
  const di = (v) => {
    if (typeof v === "string") ra.push(v);
    else if (v && typeof v === "object") for (const x of Object.values(v)) di(x);
  };
  di(state);
  return ra;
}

/** Drive one entry point through both transports and every thrown shape. */
async function quetMotCua(ten, goi) {
  for (const [tenNem, thu] of NEM) {
    for (const [tenVanChuyen, vanChuyen] of [
      ["ném khi gọi", nemKhiGoi(thu)],
      ["ném khi đọc body", noiRoiNemKhiDoc(thu)],
    ]) {
      let state;
      try {
        state = await goi(vanChuyen);
      } catch (boom) {
        assert.fail(
          `${ten} (${tenVanChuyen}, ${tenNem}): chính chỗ bắt lỗi lại ném ra ${nhan(boom)} -- ` +
            `màn hình mất cả lỗi lẫn lời giải thích`,
        );
      }
      for (const cau of chuoiTrongTrangThai(state)) {
        khongPhaiChuMay(cau, `${ten} (${tenVanChuyen}, ${tenNem})`);
      }
    }
  }
}

/** Swap the global transport for the modules that do not take one. */
async function voiFetch(vanChuyen, chay) {
  const cu = globalThis.fetch;
  globalThis.fetch = vanChuyen;
  try {
    return await chay();
  } finally {
    globalThis.fetch = cu;
  }
}

const BASE = "http://api.test.invalid";

test("fetchPlaces: không thứ gì bị ném thành chữ máy", async () => {
  await quetMotCua("fetchPlaces", (f) => fetchPlaces({ base: BASE, fetchImpl: f }));
});

test("askSearch: không thứ gì bị ném thành chữ máy", async () => {
  await quetMotCua("askSearch", (f) =>
    askSearch("quán nướng gần đây", { base: BASE, fetchImpl: f, actorId: "nguoi-1" }),
  );
});

test("goiAiTurn: không thứ gì bị ném thành chữ máy", async () => {
  await quetMotCua("goiAiTurn", (f) =>
    voiFetch(f, () => goiAiTurn({ contextId: "ctx-1", actorId: "nguoi-1", base: BASE })),
  );
});

/* Một người có thật, không phải một slug.
 *
 * Dòng này từng là `khoiDongNhom("an", ...)`, và "an" không phải một trong bảy
 * người của `nhom-demo.ts`. Bản cũ tra bảng rồi trả `hong` ngay ở dòng đầu, nên
 * transport hay ném ở đây KHÔNG BAO GIỜ ĐƯỢC GỌI: phép quét chạy 1 lần cho mỗi
 * tổ hợp và đo đúng một nhánh không đi qua mạng. Đường lỗi của cả năm request
 * chưa từng bị soi. Sửa cùng bug-223337, vì chính bản vá làm cho lời gọi này đi
 * ra tới transport được. */
const NGUOI_THAT = {
  id: "980ebea7-0f5e-4f7c-9a3f-1c2d3e4f5a6b",
  personId: "980ebea7-0f5e-4f7c-9a3f-1c2d3e4f5a6b",
  name: "Bảo",
  initials: "B",
};

test("khoiDongNhom: không thứ gì bị ném thành chữ máy", async () => {
  await quetMotCua("khoiDongNhom", (f) =>
    voiFetch(f, () => khoiDongNhom(NGUOI_THAT, { base: BASE })),
  );
});

test("napTinNhan và hai bản phân trang: không thứ gì bị ném thành chữ máy", async () => {
  const chung = { contextId: "ctx-1", actorId: "nguoi-1", base: BASE };
  await quetMotCua("napTinNhan", (f) => voiFetch(f, () => napTinNhan({ ...chung })));
  await quetMotCua("napTinCuHon", (f) =>
    voiFetch(f, () => napTinCuHon({ ...chung, dangGiu: [] })),
  );
  await quetMotCua("napTinMoiHon", (f) =>
    voiFetch(f, () => napTinMoiHon({ ...chung, dangGiu: [] })),
  );
});

test("guiTinNhan và guiTheAi: không thứ gì bị ném thành chữ máy", async () => {
  const chung = { contextId: "ctx-1", actorId: "nguoi-1", base: BASE, idempotencyKey: "k-1" };
  await quetMotCua("guiTinNhan", (f) =>
    voiFetch(f, () => guiTinNhan({ ...chung, body: "đi ăn không" })),
  );
  await quetMotCua("guiTheAi", (f) => voiFetch(f, () => guiTheAi({ ...chung })));
});

/* -------------------------------------------------------------------------
 * And what the markup actually says
 * ---------------------------------------------------------------------- */

/** Markup with tags stripped, which is what a person actually reads. */
function chuTrenMan(el) {
  return renderToStaticMarkup(el)
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

test("hai thẻ dead-end của Khám phá: markup không mang chữ máy, và không có nhãn cụt", () => {
  // A clean `detail` in a return value can still be interpolated badly one line
  // later, and a source read cannot tell the difference. This renders.
  const trangThai = [
    { kind: "khong-noi-duoc", url: BASE, detail: "" },
    { kind: "du-lieu-sai", url: BASE, detail: "" },
    { kind: "khong-noi-duoc", url: BASE, detail: "ECONNREFUSED" },
    { kind: "may-chu-loi", url: BASE, status: 502, detail: "" },
  ];
  for (const state of trangThai) {
    for (const [ten, El] of [
      ["ChuaCoDuLieu", ChuaCoDuLieu],
      ["TimKhongDuoc", TimKhongDuoc],
    ]) {
      const chu = chuTrenMan(React.createElement(El, { state, onThuLai: () => {} }));
      khongPhaiChuMay(chu, `${ten} (${state.kind}, detail=${JSON.stringify(state.detail)})`);
      assert.ok(
        !/Chi tiết:\s*$/.test(chu) && !/Chi tiết:\s+[A-ZĐ]/.test(chu.replace(/Chi tiết: \S/, "")),
        `${ten} (${state.kind}): còn nhãn "Chi tiết:" mà phía sau không có gì -> ${chu}`,
      );
      if (state.detail === "") {
        assert.ok(
          !chu.includes("Chi tiết:"),
          `${ten} (${state.kind}): detail rỗng mà vẫn in nhãn "Chi tiết:" -> ${chu}`,
        );
      }
    }
  }
});

/* -------------------------------------------------------------------------
 * The gate, with its self-check
 * ---------------------------------------------------------------------- */

/**
 * Lines where a value caught by `catch` is read through a TYPE CAST.
 *
 * Narrow on purpose. Under `strict`, `e.message` on a catch binding is a
 * compile error (TS18046: 'e' is of type 'unknown'), so `tsc` already refuses
 * the unchecked read -- and an `instanceof Error` narrowing is the checked form
 * this file is not trying to ban. What is left, and what all sixteen sites
 * were, is `(e as Error)`: an assertion the compiler believes and the runtime
 * does not.
 *
 * Parsed rather than grepped. Two comments in this very change set contain the
 * string `(e as Error).message` while discussing it, and a text match cannot
 * tell code from commentary -- a mistake this repo made three times in one day.
 */
function epKieuBienBat(text, fileName) {
  const sf = ts.createSourceFile(fileName, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const dong = [];

  const walk = (node, bat) => {
    let trong = bat;
    if (ts.isCatchClause(node) && node.variableDeclaration) {
      const ten = node.variableDeclaration.name;
      if (ts.isIdentifier(ten)) trong = new Set([...bat, ten.text]);
    }
    if ((ts.isAsExpression(node) || ts.isTypeAssertionExpression?.(node)) && ts.isIdentifier(node.expression)) {
      if (trong.has(node.expression.text)) {
        dong.push(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1);
      }
    }
    ts.forEachChild(node, (con) => walk(con, trong));
  };

  walk(sf, new Set());
  return dong.sort((a, b) => a - b);
}

test("cổng tự kiểm: nó thấy đúng chỗ ép kiểu, và bỏ qua lời bàn về ép kiểu", () => {
  // Written the way the mistakes really look. If this fixture stops failing,
  // the gate below is decoration.
  const nhuCu = [
    "function a() {", //                                     1
    "  try { g(); } catch (e) {", //                          2
    "    return { detail: (e as Error).message };", //        3  <- bắt
    "  }", //                                                 4
    "}", //                                                   5
    "function b() {", //                                      6
    "  try { g(); } catch (problem) {", //                    7
    "    return (problem as any).message;", //                8  <- bắt
    "  }", //                                                 9
    "}", //                                                  10
    "// một comment nhắc tới (e as Error).message thì không phải mã", // 11
    "/* (loi as Error).message trong khối chú thích cũng vậy */", //     12
    "function c() {", //                                     13
    "  try { g(); } catch (e) {", //                         14
    "    return e instanceof Error ? e.message : 'x';", //    15  <- an toàn, đã kiểm
    "  }", //                                                16
    "}", //                                                  17
    "const khac = (thu as Error).message;", //               18  <- không phải biến bắt được
  ].join("\n");

  assert.deepEqual(epKieuBienBat(nhuCu, "fixture.tsx"), [3, 8]);
});

test("không file nào trong src/ còn ép kiểu thứ bị bắt trong catch", () => {
  const files = [];
  const di = (thuMuc) => {
    for (const ten of readdirSync(thuMuc)) {
      const p = join(thuMuc, ten);
      if (statSync(p).isDirectory()) di(p);
      else if (/\.tsx?$/.test(ten)) files.push(p);
    }
  };
  di(SRC);
  assert.ok(files.length > 40, `chỉ quét được ${files.length} file, nghi cổng quét hụt`);

  const banA = [];
  for (const p of files) {
    const dong = epKieuBienBat(readFileSync(p, "utf8"), p);
    if (dong.length) banA.push(`${p.slice(SRC.length + 1)}:${dong.join(",")}`);
  }
  assert.deepEqual(
    banA,
    [],
    `còn ép kiểu giá trị bắt được ở:\n  ${banA.join("\n  ")}\n` +
      `dùng chiTietLoi()/moTaLoi() trong ui/loi-tren-man.ts thay cho nó`,
  );
});
