/** Decide whether a `text-occlusion` finding is a defect or a measuring artifact.
 *
 * The detector's rule compares raw bounding boxes. That is correct for a badge
 * dropped on top of a heading, and wrong for every string that has simply
 * scrolled past the edge of its container: the box of a row sitting below the
 * clip edge still intersects the box of whatever is pinned down there, so the
 * rule reports "100% covered by an opaque element" about words the browser
 * never painted in the first place.
 *
 * This repo has now been burned by that three times. `do-hinh-hoc.mjs` was
 * written to print the boxes so a human could adjudicate one finding by hand;
 * this file makes the adjudication itself reproducible, so the scanners can
 * stop reporting clip artifacts as defects without anybody deciding case by
 * case which warnings to believe.
 *
 * ## Why box arithmetic is not enough to clear a finding
 *
 * The obvious fix -- "ignore the finding when the text lies outside its scroll
 * container" -- reproduces the original bug with the sign flipped. A heading
 * genuinely buried under a sticky header is also partly outside the visible
 * band, and that one is a real defect. Geometry alone cannot separate the two,
 * because both are "text whose box is not where the eye is".
 *
 * So the question is asked the way a user answers it: scroll the words into
 * view, then ask the browser what is painted on top of them.
 * `document.elementsFromPoint` returns the actual hit-test stack at a pixel --
 * paint order, stacking contexts, transforms and clipping all already resolved
 * by the engine that draws the page. If the topmost element at the middle of a
 * word is the word, a reader can read it. No box math can be wrong about that,
 * because there is no box math.
 *
 * ## What each verdict means
 *
 * - `that`      the words stay covered after being scrolled to. A real defect.
 * - `cuon-khuat` they were merely out of view; once scrolled to, nothing is on
 *                top. The finding is an artifact of the raw-box comparison.
 * - `to-cha`    the "occluder" is an ancestor of the text -- a card covering
 *                its own label, which is how the rule describes a normal
 *                parent with a background colour.
 * - `khong-thay` the string is not on the page at all. Reported, never
 *                silently dropped: it means the scan and this check disagree
 *                about what rendered, and that is worth a human.
 *
 * Only `that` is a defect. The rest are printed by the callers rather than
 * discarded, because a filter whose output nobody can see is indistinguishable
 * from a scanner that went blind.
 */

/** Pull the quoted text and the occluder's selector back out of a finding.
 *
 * The detector truncates the quoted run at 24 characters, so the needle this
 * returns is a PREFIX and every consumer below matches with `startsWith`.
 * Matching on equality here is what made an earlier draft of this file report
 * `khong-thay` for the one screen whose label was long enough to be cut.
 */
export function docSnippet(snippet) {
  const m = /^(.+?)\s+"(.*?)"\s+is\s+(\d+)%\s+covered by an opaque element\s+\((.+?)\)\s*$/.exec(
    snippet ?? "",
  );
  if (!m) return null;
  return { selector: m[1], chu: m[2], phanTram: Number(m[3]), tren: m[4] };
}

/**
 * The browser-side half. Serialized into the page, so it may not close over
 * anything from this module.
 *
 * Returns one record per element whose text starts with `chu`; the caller
 * folds them into a single verdict. Several elements can match when a list
 * repeats a label, and "one of them is buried" is still a defect.
 */
function doTrongTrang(chu, selectorTren) {
  const ketQua = [];
  const la = (el) => el.children.length === 0 && (el.textContent ?? "").trim().length > 0;
  const ungVien = [...document.querySelectorAll("div,span,p,h1,h2,h3,h4,li,a,button")].filter(
    (el) => la(el) && (el.textContent ?? "").trim().startsWith(chu),
  );

  for (const el of ungVien) {
    // Bring the words to the middle of the viewport before judging them. An
    // `instant` scroll so the measurement below does not race a smooth
    // animation that is still travelling.
    try {
      el.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" });
    } catch {
      el.scrollIntoView(true);
    }

    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) {
      ketQua.push({ verdict: "khong-ve", ly: "hop rong sau khi cuon" });
      continue;
    }

    // Still off-screen after asking to be centred means something pins it
    // there -- a container that cannot scroll, or a fixed layer. Do not clear
    // that; hand it back for a human.
    const trongKhung =
      r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
    if (!trongKhung) {
      ketQua.push({
        verdict: "khong-cuon-toi",
        ly: `sau scrollIntoView van ngoai khung (top=${Math.round(r.top)} bottom=${Math.round(r.bottom)})`,
      });
      continue;
    }

    // Sample along the text's own middle line rather than its corners: a
    // rounded card clips its corners, and a corner miss would read as
    // occlusion on a perfectly readable label.
    const y = r.top + r.height / 2;
    const diem = [0.1, 0.3, 0.5, 0.7, 0.9].map((f) => ({ x: r.left + r.width * f, y }));

    let nhinThay = 0;
    let chan = null;
    for (const p of diem) {
      if (p.x < 0 || p.x >= innerWidth || p.y < 0 || p.y >= innerHeight) continue;
      const stack = document.elementsFromPoint(p.x, p.y);
      if (!stack.length) continue;
      const tren = stack[0];
      // The hit can land on the text node's own element, on a descendant, or
      // on an ancestor that carries the text's box. All three mean the words
      // are the thing being drawn at that pixel.
      if (tren === el || el.contains(tren) || tren.contains(el)) nhinThay++;
      else if (!chan) chan = tren.tagName.toLowerCase() + (tren.className ? `.${String(tren.className).trim().split(/\s+/).join(".")}` : "");
    }

    const tong = diem.filter((p) => p.x >= 0 && p.x < innerWidth && p.y >= 0 && p.y < innerHeight).length;
    if (tong === 0) {
      ketQua.push({ verdict: "khong-cuon-toi", ly: "khong diem mau nao nam trong khung" });
      continue;
    }

    const tyLe = nhinThay / tong;
    // An ancestor sitting on top of its own child is the rule describing a
    // normal card, not a defect. Checked against the selector the finding
    // named, so this cannot excuse an unrelated overlay.
    let cha = false;
    if (selectorTren) {
      try {
        for (const c of document.querySelectorAll(selectorTren)) {
          if (c.contains(el)) { cha = true; break; }
        }
      } catch { /* selector the detector printed may not parse; fall through */ }
    }

    ketQua.push({
      verdict: tyLe >= 0.6 ? (cha ? "to-cha" : "cuon-khuat") : cha ? "to-cha" : "that",
      tyLeNhinThay: Number(tyLe.toFixed(2)),
      diemNhinThay: nhinThay,
      diemDo: tong,
      chan,
      ly:
        tyLe >= 0.6
          ? `sau khi cuon toi, ${nhinThay}/${tong} diem mau co chinh chu o tren cung`
          : `sau khi cuon toi, chi ${nhinThay}/${tong} diem mau doc duoc; tren cung la ${chan ?? "?"}`,
    });
  }
  return ketQua;
}

/**
 * Classify one finding on an already-loaded Puppeteer page.
 *
 * The page is left scrolled where the check left it. Callers that scan several
 * findings on one page get that for free; callers that then measure something
 * else must reload.
 */
export async function phanLoai(page, finding) {
  const d = docSnippet(finding.snippet);
  if (!d) return { verdict: "khong-doc-duoc", ly: `snippet la lung: ${finding.snippet}` };

  const els = await page.evaluate(doTrongTrang, d.chu, d.tren);
  if (!els.length) {
    return { ...d, verdict: "khong-thay", ly: `khong phan tu nao co chu bat dau bang "${d.chu}"` };
  }
  // Worst verdict wins: one buried copy in a repeating list is still a defect.
  const hang = { that: 0, "khong-cuon-toi": 1, "khong-ve": 1, "to-cha": 2, "cuon-khuat": 3 };
  els.sort((a, b) => (hang[a.verdict] ?? 9) - (hang[b.verdict] ?? 9));
  return { ...d, ...els[0], soPhanTu: els.length };
}

/**
 * True when the finding must still count against the gate.
 *
 * Written as a whitelist of the two verdicts that positively clear a finding,
 * not as a list of the ones that condemn it. The difference decides what an
 * unfamiliar answer does: a `khong-thay` from a screen that changed, a
 * `khong-doc-duoc` from a detector that reworded its snippet, or a verdict
 * added here later all keep the warning instead of erasing it. A filter whose
 * default is "clear" turns every one of its own bugs into a green scan.
 */
const DA_LOAI_TRU = new Set(["cuon-khuat", "to-cha"]);

export function laLoiThat(kq) {
  return !DA_LOAI_TRU.has(kq?.verdict);
}
