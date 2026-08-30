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

It also does not prove the scripts *load*. A pasted path replaced by a helper
call is a two-part edit, and dropping the second part yields a ReferenceError
that no text scan can see -- so `test_moi_ten_duoc_dung_deu_co_duong_nhap` below
covers the one shape of that which actually happened here, and the rest was
checked by hand (`node <each file>`, watching for ReferenceError / SyntaxError /
ERR_MODULE_NOT_FOUND). Running them in the gate is not an option: they launch
browsers and drive live servers.

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
