"""QA evidence that claims to be reproducible must reproduce somewhere else.

Every verdict under `docs/claude/` points at a script in `tests/qa/` and invites
the reader to re-run it. The repository is public now, so "the reader" is no
longer only the four processes on this laptop.

## The measurement that produced this file

Run on 2026-08-30 against `origin/main` at 03b69dc: of the files tracked under
`tests/qa/`, **17 named an absolute path into one particular user's home
directory**. Three separate shapes, three separate failure modes:

    import puppeteer from "file:///home/lakiet/.claude/node_modules/..."   (7 files)
        ERR_MODULE_NOT_FOUND at load, before any assertion runs. No override,
        no fallback, nothing to read but a stack trace.

    const CHROME = process.env.X ?? "/home/lakiet/.cache/ms-playwright/..."  (9 files)
        Degrades if the env var is set, dies confusingly if it is not. Three
        different build numbers are hard-coded across the tree (1187, 1194,
        1234) because three different days installed three different browsers,
        which is the tell that nobody could have chosen this on purpose.

    createRequire("/home/lakiet/agent-harness/wt/qa/tests/qa/rd-qa-02/...")  (5 files)
        Points into a *sibling lane's worktree*. Broken on this machine too, the
        moment that worktree is re-created somewhere else.

## What this checks, and what it deliberately does not

It checks one property: no file tracked under `tests/qa/` contains a string
naming an absolute path inside a user's home directory. That is a shape check on
text. It is not a proof that the scripts run.

It does **not** prove: that puppeteer-core resolves, that a browser is installed,
that the servers those scripts drive are up, or that the evidence they once
produced would be produced again. It proves only that the reason they cannot run
elsewhere is no longer *this* reason. `npm ci`, `timTrinhDuyet()` and the harness
READMEs answer the rest.

It also did not prove the scripts *load*, and on 2026-08-31 that cost the repo
its closest-to-the-user gate. `make hero-walk` reported 0/16 stages for a whole
evening because PR #397 split `translated` into `translatedAsActor` /
`translatedAnonymous` and `qa-tt-0031/di-bo-hero-tren-demo.mjs` kept importing
the dead name. ESM refuses the whole module at LINK time, before a single line
runs, so the walk died at import with nothing to read -- and "0/16" looks far
more like "nobody ran it" than like "it is broken".

`test_moi_nhap_noi_bo_deu_ton_tai` below closes that. It is a link check, not a
run: for every first-party import under `tests/qa/`, the target file must exist
and must actually export every name the script asks for. Running the scripts is
still not an option -- they launch browsers, drive live servers and spend model
quota -- and the two questions are genuinely different, so the limit is written
into that test rather than blurred here.

`test_moi_ten_duoc_dung_deu_co_duong_nhap` covers the adjacent shape: a name
*used* but never imported, which is a ReferenceError at run time rather than a
SyntaxError at link time and so is invisible to the link check.

Scope is `tests/qa/` because that is what the QA lane owns. `apps/mobile/` has
its own equivalent, `tests/nhap-khau-chay-duoc-may-khac.test.mjs`: #326 closed
the import specifiers there and #329 closed the browser-binary constants, so the
three remaining mentions of a home directory under `apps/mobile/` are prose in
banners describing the old defect, not live paths. Two gates rather than one
widened across both trees, because each lane can only fix its own side and a
gate nobody can act on is a gate people learn to route around.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import warnings

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
QA_ROOT = REPO_ROOT / "tests" / "qa"

# An absolute path into somebody's home directory: the one shape that cannot
# survive being copied to another machine. `/tmp/...` and `/usr/share/fonts/...`
# are deliberately NOT matched -- they exist on any Linux box, and the scripts
# that use them already carry a fallback list or an env override.
#
# The optional `file://` prefix matters: that is the form the seven broken
# import specifiers used, and a pattern anchored on a bare `/` alone would still
# catch them, but spelling it out keeps the intent readable when this fails.
#
# The lookbehind is not decoration. Without it `https://example.com/home/lakiet`
# matches, and the first thing a gate like that teaches is to distrust it -- a
# URL path is not a filesystem path. Requiring the slash to follow something
# that is not a word character keeps `"/home/...`, `=/home/...` and
# `file:///home/...` while dropping `.com/home/...`.
DUONG_DAN_RIENG_MAY = re.compile(
    r"(?:file://)?(?<![A-Za-z0-9.])/(?:home|Users)/[A-Za-z0-9._-]+/"
)


def quet(text: str) -> list[tuple[int, str]]:
    """Report every line naming a home-directory absolute path.

    Comments are NOT stripped, unlike the equivalent gate in
    `apps/mobile/tests/nhap-khau-chay-duoc-may-khac.test.mjs`. That gate asks
    about import specifiers, where a quoted example in a banner is only prose.
    This one asks whether a reader can re-run the evidence, and the run
    instructions live in exactly those banners:

        *     CHROME_BIN=/home/lakiet/.cache/ms-playwright/... \\
        *       node tests/qa/qa-tt-0014/hinh-dang-khac-cua-loi-to-cha.mjs

    A comment telling the reader to use a path that exists on one laptop is the
    defect, not a description of it.
    """
    return [
        (i, m.group(0))
        for i, line in enumerate(text.splitlines(), start=1)
        for m in [DUONG_DAN_RIENG_MAY.search(line)]
        if m
    ]


def tap_tin_qa() -> list[pathlib.Path]:
    """Files tracked under tests/qa, read from git rather than the filesystem.

    `git ls-files` and not `rglob`: this worktree accumulates scratch probes and
    `node_modules/` from the harnesses that declare their own dependencies, and
    a filesystem walk would turn this gate red for files nobody committed. The
    question is about the public repository, so ask the repository.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "tests/qa"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


def doc(path: pathlib.Path) -> str | None:
    """Decoded text, or None for the binary files the guard already allows."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return None


def test_co_file_de_quet():
    """A denominator, asserted rather than printed.

    A gate that scans nothing reports "0 findings" and exits 0, which reads
    exactly like a clean tree. This repository has shipped that mistake before.
    """
    files = tap_tin_qa()
    assert len(files) > 100, f"expected the QA corpus, found {len(files)} files"
    assert any(f.suffix == ".mjs" for f in files), "no .mjs files reached the scan"
    assert any(f.suffix == ".py" for f in files), "no .py files reached the scan"


def test_khong_file_qa_nao_ghim_duong_dan_cua_mot_may():
    vi_pham = []
    for path in tap_tin_qa():
        text = doc(path)
        if text is None:
            continue
        for line_no, hit in quet(text):
            vi_pham.append(f"  {path.relative_to(REPO_ROOT)}:{line_no}: {hit}")

    assert not vi_pham, (
        f"{len(vi_pham)} absolute home-directory path(s) under tests/qa.\n"
        "Evidence that names one machine cannot be re-run by the reader of a\n"
        "verdict. Use a path relative to the file (import.meta.url / __file__),\n"
        "or an env var with a default that degrades loudly.\n" + "\n".join(vi_pham)
    )


def test_pin_puppeteer_core_khop_voi_apps_mobile():
    """One browser driver version, declared twice -- so assert they agree.

    `tests/qa/package.json` has to declare puppeteer-core because node resolves
    from the importing file upward and never reaches `apps/mobile/node_modules`.
    That is a second copy of a pin, and this repository's standing lesson about
    two copies of one fact is that somebody eventually updates one of them.

    `scripts/check_pin_drift.py` does not cover this: it compares
    `requirements-dev.txt` against installed Python distributions and knows
    nothing about npm. So the drift check for this pair lives here.
    """
    qa = json.loads((QA_ROOT / "package.json").read_text(encoding="utf-8"))
    mobile = json.loads(
        (REPO_ROOT / "apps" / "mobile" / "package.json").read_text(encoding="utf-8")
    )
    ben_qa = qa["dependencies"]["puppeteer-core"]
    ben_mobile = mobile["devDependencies"]["puppeteer-core"]
    assert ben_qa == ben_mobile, (
        f"puppeteer-core pin drift: tests/qa={ben_qa} vs apps/mobile={ben_mobile}.\n"
        "The QA probes and apps/mobile/tools drive the same browser through the\n"
        "same API; two versions means an evidence run and the gate it backs are\n"
        "no longer the same measurement."
    )


# Names a probe can only have because something imported them. Replacing a
# pasted path with a helper call is a two-part edit, and the second part is easy
# to forget: the commit that introduced this gate did forget it three times
# (qa-tt-0014, rd-qa-18, rd-qa-29), each surviving both a specifier-resolution
# check and `node --check` before dying at run time on a ReferenceError.
CAN_NHAP = {
    "timTrinhDuyet": re.compile(r"\btimTrinhDuyet\s*\("),
    "puppeteer": re.compile(r"\bpuppeteer\s*\.\s*launch\s*\("),
    "chromium": re.compile(r"\bchromium\s*\.\s*launch\s*\("),
}


def test_moi_ten_duoc_dung_deu_co_duong_nhap():
    """Used-but-never-imported is a ReferenceError, not a lint opinion.

    A text gate that only bans bad paths says nothing about whether the
    replacement works. This is the cheapest static half of that question; the
    other half is running the scripts, which this suite deliberately does not do
    (they launch browsers and drive live servers).
    """
    thieu = []
    for path in tap_tin_qa():
        if path.suffix != ".mjs":
            continue
        text = doc(path)
        if text is None:
            continue
        for ten, dung in CAN_NHAP.items():
            if not dung.search(text):
                continue
            nhap = re.compile(
                rf"^\s*import\s+(?:{ten}\b|[^;]*\b{ten}\b[^;]*\bfrom)", re.M
            )
            # A module that DECLARES the name does not import it. Without this,
            # tim-trinh-duyet.mjs -- the file that defines timTrinhDuyet -- is
            # reported for not importing itself.
            khai = re.compile(
                rf"^\s*(?:export\s+)?(?:async\s+)?(?:function|const|let|class)\s+{ten}\b",
                re.M,
            )
            if not nhap.search(text) and not khai.search(text):
                thieu.append(
                    f"  {path.relative_to(REPO_ROOT)}: dung `{ten}` ma khong nhap"
                )

    assert not thieu, "used without importing:\n" + "\n".join(thieu)


# --------------------------------------------------------------- the canary ---
# Below: proof the scanner is not blind. Each defect shape is rewritten two or
# three ways, because a checker that only recognises the exact byte sequence it
# was written against catches the tree it was born on and nothing after.


@pytest.mark.parametrize(
    "hinh_dang",
    [
        # the import specifier, three spellings
        'import puppeteer from "file:///home/lakiet/.claude/node_modules/x.js";',
        "import pw from '/home/lakiet/.npm/_npx/abc/node_modules/playwright-core/index.js';",
        'const p = await import("file:///home/someone/lib/x.mjs");',
        # the browser binary, with and without an override in front of it
        'const CHROME = "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";',
        "const C = process.env.CHROME_BIN ?? '/home/other-user/.cache/chromium/chrome';",
        "export PUPPETEER_EXECUTABLE_PATH=/home/lakiet/.cache/ms-playwright/c/chrome",
        # a sibling lane's worktree, and a foreign project
        'sys.path.insert(0, "/home/lakiet/agent-harness/wt/qa/scripts")',
        'readFileSync("/home/lakiet/CMAROX/apps/web/node_modules/axe-core/axe.min.js")',
        # macOS spelling of the same defect
        'const C = "/Users/someone/Library/Caches/chromium/Chromium.app";',
        # and inside a comment, which is where the run instructions live
        " *     CHROME_BIN=/home/lakiet/.cache/ms-playwright/c/chrome node probe.mjs",
    ],
)
def test_canary_scanner_nhin_thay_hinh_dang_xau(hinh_dang):
    assert quet(hinh_dang), f"scanner blind to: {hinh_dang}"


@pytest.mark.parametrize(
    "hinh_dang",
    [
        # the fixed forms this PR moves the 17 files to
        'import puppeteer from "puppeteer-core";',
        "const HERE = path.dirname(fileURLToPath(import.meta.url));",
        "const CHROME = process.env.PUPPETEER_EXECUTABLE_PATH ?? timTrinhDuyet();",
        'sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts"))',
        # absolute paths that are NOT machine-specific: portable on any Linux box
        'const OUT = "/tmp/qa-rd-12";',
        '"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",',
        'for (const bin of ["/usr/bin/google-chrome", "/snap/bin/chromium"])',
        # near-misses that must not trip it
        'const label = "home/lakiet is not absolute";',
        'const url = "https://example.com/home/lakiet/x";',
    ],
)
def test_canary_scanner_im_lang_voi_hinh_dang_dung(hinh_dang):
    assert not quet(hinh_dang), f"false positive on: {hinh_dang}"


# ------------------------------------------------- first-party import links ---
# The question here is narrower than "does this script work" and much wider than
# "does this one string parse": for every import a QA script writes against code
# in THIS repository, does the target exist, and does it export the names asked
# for? That is exactly the set ESM refuses at link time, which is the set that
# kills a script before its first assertion and leaves a zero where a red
# belongs.
#
# Only relative specifiers are read. `playwright`, `puppeteer-core` and
# `@axe-core/playwright` are deliberately out of scope: they fail for a
# different reason (nobody ran `npm ci` in `tests/qa/`), the fix is a different
# fix, and `tests/qa/node_modules` is absent on a clean checkout -- so a gate
# that resolved them would be red on every machine that has not installed the
# QA harness. A gate that is red for a reason the reader cannot act on is a
# gate the reader turns off.

# `import <bindings> from "<relative>"`, bindings possibly spanning many lines.
# Anchored on a line start so a specifier quoted inside a banner is prose, not
# an import -- the banners here are full of example command lines.
NHAP_NOI_BO = re.compile(
    r"""^[ \t]*import\s+(?P<buoc>[^;'"]*?)\s+from\s+["'](?P<dich>\.[^"']*)["']""",
    re.M,
)
# `import "<relative>"` -- no bindings to check, but the file still has to exist.
NHAP_TRONG = re.compile(r"""^[ \t]*import\s+["'](?P<dich>\.[^"']*)["']""", re.M)

# `export function f`, `export const C`, `export class K`, `export type T`, and
# `export default`. Line-anchored for the same reason as above.
XUAT = re.compile(
    r"""^[ \t]*export\s+(?:(?P<mac_dinh>default)\b"""
    r"""|(?:async\s+)?(?:declare\s+)?(?P<loai>function|const|let|var|class|type"""
    r"""|interface|enum)\s+(?P<ten>[A-Za-z_$][\w$]*))""",
    re.M,
)
# Shapes this reader cannot follow. No target under `tests/qa/`, `apps/mobile/`
# or `packages/` uses either today, and if one starts to, the reader would go
# blind in the PASS direction: every name would silently look unexported, or
# worse, a re-exported name would look missing. So finding one is a finding,
# not a shrug. `cong-api.ts`-style barrels are the likely first arrival.
XUAT_KHONG_DOC_DUOC = re.compile(r"^[ \t]*export\s*(?:\{|\*)", re.M)

DIST_TEST = "apps/mobile/dist-test/"


def ten_duoc_nhap(buoc: str) -> set[str]:
    """The EXPORTED names a binding clause asks for.

    `confirmExpense as confirmExpenseRaw` asks the target for `confirmExpense`;
    the local alias is this file's business and nobody else's. A default import
    asks for `default`. `* as ns` asks for nothing checkable and is dropped.
    """
    ten: set[str] = set()
    trong_ngoac = re.search(r"\{(?P<ds>.*)\}", buoc, re.S)
    if trong_ngoac:
        for muc in trong_ngoac.group("ds").split(","):
            muc = muc.strip()
            if muc:
                ten.add(muc.split()[0])
    dau = buoc.split("{")[0].strip().rstrip(",").strip()
    if dau and not dau.startswith("*"):
        ten.add("default")
    return ten


def giai_dich(nguon: pathlib.Path, dich: str) -> pathlib.Path:
    """Where a relative specifier points, in the tree a reader can edit.

    `dist-test/` is gitignored build output produced by `tsc -p
    tsconfig.test.json`, so it may be absent on a clean checkout and stale on a
    dirty one. Reading it would make this gate depend on a build and, worse,
    let a stale artifact vouch for source nobody has compiled. The tracked
    `src/*.ts` is the thing a lane actually renames, so that is what is read --
    and it means this test needs no node, no npm and no build to run.
    """
    tuyet_doi = (nguon.parent / dich).resolve()
    posix = tuyet_doi.as_posix()
    if DIST_TEST not in posix:
        return tuyet_doi
    con_lai = posix.split(DIST_TEST, 1)[1]
    goc = REPO_ROOT / "apps" / "mobile" / "src" / con_lai
    goc = goc.with_suffix("")
    for duoi in (".ts", ".tsx"):
        if goc.with_suffix(duoi).exists():
            return goc.with_suffix(duoi)
    return goc.with_suffix(".ts")


def xuat_cua(dich: pathlib.Path, chi_gia_tri: bool) -> set[str] | None:
    """Every name a target module exports, or None if the shape is unreadable.

    `chi_gia_tri` is True when the importer will load the COMPILED file: `export
    type` and `export interface` vanish at compile time, so counting them would
    turn a real runtime failure into a pass.
    """
    text = doc(dich)
    if text is None or XUAT_KHONG_DOC_DUOC.search(text):
        return None
    ten: set[str] = set()
    for m in XUAT.finditer(text):
        if m.group("mac_dinh"):
            ten.add("default")
        elif not (chi_gia_tri and m.group("loai") in {"type", "interface"}):
            ten.add(m.group("ten"))
    return ten or None


def canh_nhap_noi_bo() -> tuple[list[str], int]:
    """Every (script, first-party import) edge, and what is wrong with it.

    Returns the findings and the number of edges READ, because a scanner that
    stops recognising the import syntax would otherwise report zero findings --
    which is spelled exactly like a healthy tree.
    """
    hong: list[str] = []
    canh = 0
    for path in tap_tin_qa():
        if path.suffix != ".mjs":
            continue
        text = doc(path)
        if text is None:
            continue
        ro = path.relative_to(REPO_ROOT)
        canh_cua_file = [
            (m.group("dich"), ten_duoc_nhap(m.group("buoc")))
            for m in NHAP_NOI_BO.finditer(text)
        ] + [(m.group("dich"), set()) for m in NHAP_TRONG.finditer(text)]
        for dich, ten_can in canh_cua_file:
            canh += 1
            muc_tieu = giai_dich(path, dich)
            if not muc_tieu.exists():
                hong.append(f"{ro}: `{dich}` khong co file nao o do")
                continue
            co = xuat_cua(
                muc_tieu, DIST_TEST in (path.parent / dich).resolve().as_posix()
            )
            ro_dich = muc_tieu.relative_to(REPO_ROOT)
            if co is None:
                hong.append(
                    f"{ro}: khong doc duoc danh sach export cua {ro_dich} "
                    "(`export {` / `export *`, hoac file rong)"
                )
                continue
            for ten in sorted(ten_can - co):
                hong.append(f"{ro}: `{ten}` khong duoc {ro_dich} xuat ra")
    return hong, canh


# Findings that are real and that this PR does not fix, each with the reason.
# Pinned rather than skipped, so the list is reviewable on sight and cannot grow
# in silence -- the shape `.api-contract-unresolved.json` already uses here.
#
# Both scripts below are dead for a deeper reason than their import: they call
# `proposeSplit(draft, attempt)` against a signature that has taken
# `(contextId, draft, attempt, items)` since the synthetic `CONTEXT_ID` was
# deliberately removed from `api.ts` (see the comment at api.ts:74). Repairing
# them needs a live API to mint a real context, which is QA-lane work on QA-lane
# evidence, not a specifier edit. Reported to that lane rather than papered over.
DA_BIET_HONG = {
    "tests/qa/rd-qa-02/make-guest-url.mjs: `CONTEXT_ID` khong duoc "
    "apps/mobile/src/api.ts xuat ra",
    "tests/qa/rd-qa-02/money-server-truth.mjs: `CONTEXT_ID` khong duoc "
    "apps/mobile/src/api.ts xuat ra",
}


def test_co_canh_nhap_de_quet():
    """A denominator for the link check, asserted rather than printed.

    Measured on 2026-08-31 at 2f8a301: 43 first-party import edges. The floor is
    set below that so ordinary churn does not trip it, and above zero so a
    scanner that stops recognising `import ... from "./x.mjs"` goes red instead
    of reporting a clean tree it never looked at.
    """
    _, canh = canh_nhap_noi_bo()
    assert canh >= 35, (
        f"only {canh} first-party import edges reached the scan; 43 were there "
        "on 2026-08-31. Either the corpus shrank a lot or NHAP_NOI_BO stopped "
        "matching the way these files are written."
    )


def test_moi_nhap_noi_bo_deu_ton_tai():
    """A script that cannot LINK reports zero, and zero reads like "not run".

    Proves: every relative import in `tests/qa/` names a file that exists and
    exports the name asked for -- checked against tracked source, so this needs
    no node, no npm and no `dist-test` build.

    Does NOT prove: that any script runs. Bare specifiers are out of scope (see
    the banner above), a name used without being imported is a ReferenceError
    that only `test_moi_ten_duoc_dung_deu_co_duong_nhap` sees, and an argument
    list that has drifted from its function is invisible to both -- which is
    exactly what is still wrong with the two scripts pinned in `DA_BIET_HONG`.
    """
    hong, _ = canh_nhap_noi_bo()
    moi = [h for h in hong if h not in DA_BIET_HONG]

    # A pin that no longer matches means somebody repaired the script. Say so
    # loudly, but do NOT fail: going red for an improvement is how a gate gets
    # switched off, and this list belongs to another lane.
    for cu in sorted(DA_BIET_HONG - set(hong)):
        warnings.warn(
            f"DA_BIET_HONG khong con khop, xoa dong nay di: {cu}",
            stacklevel=1,
        )

    assert not moi, (
        f"{len(moi)} import khong link duoc trong tests/qa.\n"
        "ESM tu choi CA module o buoc link, truoc khi mot dong nao chay -- nen\n"
        "script chet o day in ra 0 phep kiem, khong phai mot dau do. Sua ten\n"
        "cho dung, hoac ghim vao DA_BIET_HONG kem ly do.\n"
        + "\n".join(f"  {h}" for h in moi)
    )


# --------------------------------------------------- the canary, both ways ---
# `ten_duoc_nhap` and `xuat_cua` are the two halves that can go blind in the
# PASS direction, so each is pinned against the shapes actually written in this
# tree -- including the exact one that took hero-walk to 0/16.


@pytest.mark.parametrize(
    ("buoc", "cho_doi"),
    [
        ("{ timTrinhDuyet }", {"timTrinhDuyet"}),
        ("{ findChrome, launch, serve }", {"findChrome", "launch", "serve"}),
        # the alias form: the TARGET's name is what matters, not the local one
        ("{ confirmExpense as confirmExpenseRaw }", {"confirmExpense"}),
        # multi-line, which is how the hero walk writes its fourteen names
        (
            "{\n  attemptFor,\n  BASE_URL,\n  taoBill,\n}",
            {"attemptFor", "BASE_URL", "taoBill"},
        ),
        ("puppeteer", {"default"}),
        ("ts, { readFileSync }", {"default", "readFileSync"}),
        ("* as helpers", set()),
    ],
)
def test_canary_doc_dung_ten_duoc_nhap(buoc, cho_doi):
    assert ten_duoc_nhap(buoc) == cho_doi


def test_canary_bat_duoc_dung_hinh_dang_da_lam_chet_hero_walk(tmp_path):
    """The 2026-08-31 defect, rebuilt: import a name the target no longer has.

    Not a paraphrase of it -- `translated` really was removed from `api.ts` by
    #397 and really was still imported by the hero walk. If this check had
    existed, this is the line it would have printed.
    """
    api = REPO_ROOT / "apps" / "mobile" / "src" / "api.ts"
    co = xuat_cua(api, chi_gia_tri=True)
    assert co, "khong doc duoc export cua api.ts -- canary nay dang do cai gi?"
    # The premise: the split really happened, and the old name really is gone.
    assert "translatedAsActor" in co
    assert "translatedAnonymous" in co
    assert "translated" not in co, (
        "api.ts lai xuat `translated` -- ca canary nay khong con noi ve #397 nua"
    )
    # ...so an import of it is a finding, and one of a real target's real names
    # is not.
    assert ten_duoc_nhap("{ translated }") - co == {"translated"}
    assert not ten_duoc_nhap("{ translatedAsActor }") - co


def test_canary_khong_doc_duoc_thi_khong_phai_dat(tmp_path):
    """An unreadable export shape must be a finding, never an empty pass.

    A barrel (`export { a } from "./b"`) would make every name look unexported
    if read naively, or -- if the reader shrugged and returned an empty set --
    make every name look fine. Both are wrong; refusing is right.
    """
    barrel = tmp_path / "barrel.mjs"
    barrel.write_text('export { phone } from "./lib.mjs";\n', encoding="utf-8")
    assert xuat_cua(barrel, chi_gia_tri=False) is None

    sao = tmp_path / "sao.mjs"
    sao.write_text('export * from "./lib.mjs";\n', encoding="utf-8")
    assert xuat_cua(sao, chi_gia_tri=False) is None

    rong = tmp_path / "rong.mjs"
    rong.write_text("// khong xuat gi\n", encoding="utf-8")
    assert xuat_cua(rong, chi_gia_tri=False) is None


def test_canary_export_type_khong_song_qua_buoc_bien_dich(tmp_path):
    """`export type` is not there at run time, so it must not vouch for an import.

    A `.mjs` importing a type name from `dist-test/*.js` fails at link time
    exactly like the hero walk did. Reading the `.ts` source without this
    distinction would call that a pass.
    """
    nguon = tmp_path / "t.ts"
    nguon.write_text(
        "export type Chi = { id: string };\n"
        "export interface Nguoi { id: string }\n"
        "export function chia() {}\n",
        encoding="utf-8",
    )
    assert xuat_cua(nguon, chi_gia_tri=True) == {"chia"}
    assert xuat_cua(nguon, chi_gia_tri=False) == {"Chi", "Nguoi", "chia"}


@pytest.mark.parametrize(
    "dong",
    [
        'import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";',
        'import { a, b } from "./lib.mjs";',
        'import puppeteer from "../../x.mjs";',
        'import "./tac-dung-phu.mjs";',
    ],
)
def test_canary_nhan_ra_import_noi_bo(dong):
    assert NHAP_NOI_BO.search(dong) or NHAP_TRONG.search(dong), f"bo sot: {dong}"


@pytest.mark.parametrize(
    "dong",
    [
        # bare specifiers are deliberately out of scope
        'import { chromium } from "playwright";',
        'import { readFileSync } from "node:fs";',
        # a specifier quoted inside a banner is prose, not an import
        ' *     import { x } from "./vi-du.mjs";',
    ],
)
def test_canary_bo_qua_cai_khong_thuoc_pham_vi(dong):
    assert not NHAP_NOI_BO.search(dong) and not NHAP_TRONG.search(dong), f"nham: {dong}"
