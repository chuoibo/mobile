/** Read every (text colour, background colour) pair a screen actually writes, from the AST.
 *
 * ## Why this exists
 *
 * `thanh-tich` shipped a "Level N" chip painted `c.aiInk` on `c.aiSoft`. Both
 * are real tokens, both are spelled correctly, and the pair is white `#ffffff`
 * on near-white `#f5f1ff` -- 1.1:1, where AA asks 4.5:1. The words were on
 * screen and could not be read. In dark mode the same line is `#150a30` on
 * `#221046`, 1.3:1, so it is not a light-mode accident either.
 *
 * Nothing in `npm test` could see it. `renderToStaticMarkup` emits class names
 * and no stylesheet, so every existing render test computes contrast against
 * nothing -- `dong-binh-chon-the.test.mjs` says so in its own header. The one
 * thing that did catch it was a live `imp detect` over a served page, which
 * needs Chrome, a built bundle and about four minutes. That is a fine weekly
 * sweep and a bad gate.
 *
 * ## Why the AST rather than a render
 *
 * The defect is not a layout accident, it is a token-pairing mistake, and the
 * pairing is written literally in the source: a `backgroundColor:` on one
 * element and a `color:` on a descendant. That is readable statically, for
 * every screen at once, in under a second and with no browser. It also reaches
 * screens a render cannot: `ThanhTich` loads its numbers in `useEffect`, so a
 * static render only ever shows the spinner -- the chip does not exist in the
 * markup at all.
 *
 * ## Correlated ternaries, which is where the naive version falls over
 *
 * The same file, forty lines further down, writes:
 *
 *     backgroundColor: mo ? c.accent : "transparent",
 *     color:           mo ? c.accentInk : c.inkFaint,
 *
 * Crossing every colour against every background flags `accentInk` on the card
 * white and calls a correct chip a bug. The two ternaries are guarded by the
 * same `mo`, so the branches are correlated: `mo` true paints white on accent,
 * `mo` false paints faint ink on the inherited surface. Neither crossing
 * happens at runtime. So when the condition texts match, this pairs branch to
 * branch; only when they differ does it fall back to the cross product.
 *
 * ## What this does NOT prove
 *
 * It reads inline `style={{...}}` object literals, which is how this codebase
 * writes colour. A colour arriving through a prop, a helper function, a
 * variable, or a `StyleSheet.create` handle is NOT resolved -- those land in
 * `boQua` and are counted, so a clean run reports its own blind spots rather
 * than implying it read everything. It says nothing about opacity, gradients,
 * images behind text, or whether the element is on screen at all. A pair it
 * approves is a pair whose two tokens are far enough apart; it is not a promise
 * the text is visible.
 *
 * Usage:
 *   node tools/cap-mau-tinh.mjs [duong-dan...]     # mac dinh: toan bo src/
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const HERE = dirname(fileURLToPath(import.meta.url));
export const GOC = resolve(HERE, "..");

const tokens = JSON.parse(
  readFileSync(resolve(GOC, "../../packages/shared/tokens.json"), "utf8"),
);

/** Both palettes are checked. A pair that is legible in light and illegible in
 *  dark is still a defect, and `usePalette()` picks between them at runtime. */
export const BANG_MAU = { sang: tokens.color.light, toi: tokens.color.dark };

/** Font size per `type.X` step, so the WCAG large-text allowance can be applied
 *  where it genuinely applies rather than everywhere or nowhere. */
const CO_CHU = Object.fromEntries(
  Object.entries(tokens.type)
    .filter(([, v]) => v && typeof v === "object")
    .map(([k, v]) => [k, { size: v.size, weight: String(v.weight) }]),
);
// The app names two steps of its own on top of the shared scale.
CO_CHU.amount = { size: tokens.type.display.size, weight: String(tokens.type.display.weight) };
CO_CHU.amountSmall = { size: 17, weight: "600" };

function kenh(v) {
  const x = v / 255;
  return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
}

/** Relative luminance, sRGB, per WCAG 2.x. */
export function doSang(hex) {
  const h = hex.replace("#", "");
  const n = h.length === 3 ? h.split("").map((ch) => ch + ch) : h.match(/../g);
  const [r, g, b] = n.map((p) => parseInt(p, 16));
  return 0.2126 * kenh(r) + 0.7152 * kenh(g) + 0.0722 * kenh(b);
}

export function tuongPhan(a, b) {
  const [hi, lo] = [doSang(a), doSang(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** WCAG large text: >= 24px, or >= 18.66px when bold. Anything unknown is held
 *  to the stricter body threshold rather than given the benefit of the doubt. */
export function nguong(co) {
  if (!co) return 4.5;
  const dam = Number(co.weight) >= 700;
  if (co.size >= 24 || (dam && co.size >= 18.66)) return 3;
  return 4.5;
}

/* ------------------------------------------------------------------ *
 * Reading one style object out of the AST.
 * ------------------------------------------------------------------ */

/** One resolved alternative for a style value.
 *
 *  `dk` is the set of conditions that must hold for this alternative to be the
 *  one painted: the source text of each guarding ternary, plus which branch.
 *  They come from two places and both matter. A ternary inside the style object
 *  (`chon ? c.split : "transparent"`) contributes one; so does a ternary that
 *  decides whether the element is rendered at all (`{chon ? <Text/> : null}`).
 *
 *  Without the second kind this reader calls three correct tick-boxes broken.
 *  `MonCuaToi`, `BinhChon` and `MoBinhChon` all draw a 22px box whose fill is
 *  `chon ? c.split : "transparent"` and put the tick INSIDE `{chon ? ... :
 *  null}`. The tick is unconditional where it stands, so pairing it against
 *  every branch of the ancestor walks it up past the filled box onto the card
 *  and reports white-on-white -- a state that cannot exist, because when the
 *  tick exists the box behind it is filled. */
function nhanh(token, dk) {
  return { token, dk };
}

/** Add one guard to a set of alternatives. */
function them(ds, key, veTrai) {
  return ds.map((n) => ({ ...n, dk: [...n.dk, { key, veTrai }] }));
}

/** Resolve a style value expression to the list of alternatives it can take.
 *  Returns `null` when the shape is not one this reader understands, which is
 *  reported rather than silently treated as absent. */
function docGiaTri(node) {
  // c.aiInk  ->  "aiInk"
  if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression)) {
    if (node.expression.text === "c") return [nhanh(node.name.text, [])];
    return null;
  }
  // "transparent" / "#fff"
  if (ts.isStringLiteral(node)) {
    const v = node.text.trim().toLowerCase();
    if (v === "transparent") return [nhanh("__trong", [])];
    if (/^#[0-9a-f]{3}$|^#[0-9a-f]{6}$/.test(v)) return [nhanh(`__hex:${v}`, [])];
    return null;
  }
  // on ? A : B  -- both branches, tagged with the condition that selects them
  if (ts.isConditionalExpression(node)) {
    const khoa = node.condition.getText();
    const a = docGiaTri(node.whenTrue);
    const b = docGiaTri(node.whenFalse);
    if (!a || !b) return null;
    return [...them(a, khoa, true), ...them(b, khoa, false)];
  }
  if (ts.isParenthesizedExpression(node)) return docGiaTri(node.expression);
  return null;
}

/** Pull `color`, `backgroundColor` and the `...type.X` size out of one object
 *  literal. Later properties win, matching JS object semantics. */
function docObject(obj, ra) {
  for (const p of obj.properties) {
    if (ts.isSpreadAssignment(p)) {
      const e = p.expression;
      if (ts.isPropertyAccessExpression(e) && ts.isIdentifier(e.expression) && e.expression.text === "type") {
        ra.co = CO_CHU[e.name.text] ?? ra.co;
      }
      continue;
    }
    if (!ts.isPropertyAssignment(p)) continue;
    const ten = ts.isIdentifier(p.name) || ts.isStringLiteral(p.name) ? p.name.text : null;
    if (ten !== "color" && ten !== "backgroundColor" && ten !== "fontWeight") continue;
    if (ten === "fontWeight") {
      if (ts.isStringLiteral(p.initializer) && ra.co) {
        ra.co = { ...ra.co, weight: p.initializer.text };
      }
      continue;
    }
    const gt = docGiaTri(p.initializer);
    if (ten === "color") ra.chu = gt ?? "__khong-doc-duoc";
    else ra.nen = gt ?? "__khong-doc-duoc";
  }
}

/** Walk whatever shape the `style` prop takes and collect what it sets. */
function docStyle(expr, ra) {
  if (!expr) return;
  if (ts.isParenthesizedExpression(expr)) return docStyle(expr.expression, ra);
  if (ts.isObjectLiteralExpression(expr)) return docObject(expr, ra);
  // style={[a, b]}
  if (ts.isArrayLiteralExpression(expr)) {
    for (const el of expr.elements) docStyle(el, ra);
    return;
  }
  // style={({ pressed }) => ({ ... })}
  if (ts.isArrowFunction(expr)) return docStyle(expr.body, ra);
  if (ts.isConditionalExpression(expr)) {
    docStyle(expr.whenTrue, ra);
    docStyle(expr.whenFalse, ra);
  }
}

function doiThuocTinh(el) {
  const tags = ts.isJsxElement(el) ? el.openingElement : el;
  const ra = { chu: null, nen: null, co: null, ten: tags.tagName.getText() };
  for (const a of tags.attributes.properties) {
    if (!ts.isJsxAttribute(a) || a.name.getText() !== "style") continue;
    const init = a.initializer;
    if (init && ts.isJsxExpression(init)) docStyle(init.expression, ra);
  }
  return ra;
}

/* ------------------------------------------------------------------ *
 * Pairing text against the surface it lands on.
 * ------------------------------------------------------------------ */

/** True when these two alternatives cannot both be live at the same time:
 *  some condition guards both, and they need it to go opposite ways. */
function loaiTruNhau(a, b) {
  return a.dk.some((x) => b.dk.some((y) => x.key === y.key && x.veTrai !== y.veTrai));
}

/** Every (text, surface) pair the source can actually paint, for one element. */
function ghepCap(chu, nenStack) {
  const cap = [];
  for (const t of chu) {
    // Nearest ancestor that paints something this branch can land on.
    for (let i = nenStack.length - 1; i >= 0; i--) {
      const lop = nenStack[i];
      const ungVien = lop.filter((n) => !loaiTruNhau(t, n));
      if (ungVien.length === 0) continue;
      const dac = ungVien.filter((n) => n.token !== "__trong");
      if (dac.length === 0) continue; // fully transparent here, keep going up
      for (const n of dac) cap.push([t, n]);
      // Only the nearest painting ancestor matters for this branch.
      if (dac.length === ungVien.length) break;
    }
  }
  return cap;
}

function giaiToken(token, bang) {
  if (token.startsWith("__hex:")) return token.slice(6);
  return bang[token] ?? null;
}

/** Scan one file. Returns findings and the reader's own blind spots. */
export function quetFile(duongDan) {
  const src = ts.createSourceFile(
    duongDan,
    readFileSync(duongDan, "utf8"),
    ts.ScriptTarget.ESNext,
    true,
    ts.ScriptKind.TSX,
  );
  const loi = [];
  const boQua = [];
  const ten = relative(GOC, duongDan);
  // Counted so a run can prove it read something. A parser that quietly returns
  // nothing scores zero findings and is indistinguishable from a clean tree.
  let soCap = 0;

  const di = (node, nenStack, boiCanh) => {
    let stack = nenStack;

    // `{cond ? <A/> : <B/>}` and `{cond && <A/>}` decide whether a subtree is
    // rendered at all. Carry that down as a guard, so a colour written inside
    // one branch is only ever paired with surfaces that branch can land on.
    if (ts.isConditionalExpression(node)) {
      const khoa = node.condition.getText();
      di(node.whenTrue, stack, [...boiCanh, { key: khoa, veTrai: true }]);
      di(node.whenFalse, stack, [...boiCanh, { key: khoa, veTrai: false }]);
      di(node.condition, stack, boiCanh);
      return;
    }
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken
    ) {
      di(node.left, stack, boiCanh);
      di(node.right, stack, [...boiCanh, { key: node.left.getText(), veTrai: true }]);
      return;
    }

    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const s = doiThuocTinh(node);
      const dong = src.getLineAndCharacterOfPosition(node.getStart()).line + 1;

      if (s.nen === "__khong-doc-duoc") {
        boQua.push({ file: ten, dong, ly: "nen khong doc duoc tinh" });
        // An unreadable background must not let descendants be graded against a
        // grandparent surface they never touch.
        stack = [...stack, [nhanh("__mo", boiCanh)]];
      } else if (s.nen) {
        stack = [...stack, s.nen.map((n) => ({ ...n, dk: [...boiCanh, ...n.dk] }))];
      }

      if (s.chu === "__khong-doc-duoc") {
        boQua.push({ file: ten, dong, ly: "mau chu khong doc duoc tinh" });
      } else if (s.chu) {
        const chu = s.chu.map((t) => ({ ...t, dk: [...boiCanh, ...t.dk] }));
        for (const [t, n] of ghepCap(chu, stack)) {
          if (n.token === "__mo") {
            boQua.push({ file: ten, dong, ly: "nen gan nhat khong doc duoc" });
            continue;
          }
          for (const [chuDe, bang] of Object.entries(BANG_MAU)) {
            const mauChu = giaiToken(t.token, bang);
            const mauNen = giaiToken(n.token, bang);
            if (!mauChu || !mauNen) {
              boQua.push({ file: ten, dong, ly: `token la: ${t.token}/${n.token}` });
              continue;
            }
            soCap += 1;
            const ty = tuongPhan(mauChu, mauNen);
            const can = nguong(s.co);
            if (ty < can) {
              loi.push({
                file: ten,
                dong,
                the: s.ten,
                chuDe,
                chu: t.token,
                nen: n.token,
                mauChu,
                mauNen,
                ty: Number(ty.toFixed(2)),
                can,
              });
            }
          }
        }
      }
    }
    node.forEachChild((con) => di(con, stack, boiCanh));
  };

  di(src, [], []);
  return { loi, boQua, soCap };
}

export function timTsx(goc) {
  const ra = [];
  const di = (d) => {
    for (const e of readdirSync(d)) {
      const p = join(d, e);
      if (statSync(p).isDirectory()) di(p);
      else if (p.endsWith(".tsx")) ra.push(p);
    }
  };
  di(goc);
  return ra.sort();
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const files = args.length ? args.map((a) => resolve(a)) : timTsx(resolve(GOC, "src"));
  let loi = [];
  let boQua = [];
  for (const f of files) {
    const r = quetFile(f);
    loi.push(...r.loi);
    boQua.push(...r.boQua);
  }
  for (const l of loi) {
    console.log(
      `${l.file}:${l.dong} [${l.chuDe}] ${l.the}  ${l.chu}(${l.mauChu}) tren ${l.nen}(${l.mauNen})` +
        `  = ${l.ty}:1, can ${l.can}:1`,
    );
  }
  console.log(`\n${files.length} file  ${loi.length} cap hong  ${boQua.length} cho khong doc duoc`);
  process.exit(loi.length ? 1 : 0);
}
