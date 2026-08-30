"""No gate in this tree may render a ruff verdict with an unpinned ruff.

## Why this exists

`scripts/ruff_pinned.sh` (#246) closed one unpinned path: `ruff_changed.sh`
used to lint with whatever `ruff` was first on PATH. Its header states the
measurement -- pinned 0.9.2 reports 31 findings over the tracked tree, this
machine's 0.15.15 reports 30, and the one it cannot see is UP038, a rule later
ruff REMOVED. Editing that file got ĐẠT locally and HỎNG from CI.

It closed one path and left a second. `tests/test_qa_scripts_are_ruff_formatted.py`
-- the ratchet that keeps unformatted Python out of tests/qa/ -- kept calling
bare `ruff`. The QA lane found it (qa-tt-0010) and could only mark it, because
closing it meant editing `scripts/`, which QA does not own.

Two files, one root cause, found weeks apart. That is the signature of a class
rather than an incident, and a fix that closes only the instances found so far
leaves the third one to be discovered the same way. This gate closes the class:
a *new* bare-ruff verdict path fails here on the pull request that adds it.

## What it checks

One thing, structurally rather than by grep. In every tracked `*.py` and `*.sh`
file, ruff must not be executed under the bare name `ruff`:

  - Python: the argv of a `subprocess` call, read from the AST. argv[0] is the
    defect when it evaluates to *the ruff this machine happens to have*, in any
    of the three ways a file can say that: the literal `"ruff"`; a
    `shutil.which("ruff")` written inline; or a name bound earlier in the file
    to either of those. A path resolved through the pin -- `pinned_ruff()`,
    `str(some_path)` -- is not, because the AST cannot say it is, and a gate
    that guesses is a gate that gets switched off.

    The rule is about argv, not about `shutil.which` itself. Three files ask
    `if shutil.which("ruff") is None` to decide whether their own fixture can
    run; that value never reaches a subprocess and never decides anything about
    repository files. Reporting them would be a false accusation, and a false
    accusation is what gets a gate disabled.

    `shutil.which("ruff", path=...)` is likewise outside the rule: it asks a
    named directory, not the machine. `test_duong_phan_quyet_ruff_thu_hai.py`
    uses it to prove a shim really landed at the front of a PATH it just built,
    which is the opposite of trusting whatever was there.
  - Shell: `ruff` standing in a command position (start of a line, or after
    `|`, `&&`, `||`, `;`, `(`). `"$RUFF" check` and `command -v ruff` are
    argument and lookup, not execution, and do not match.

## Why grep would not do

`ruff` appears 60-odd times in this tree in prose: comments explaining the pin,
docstrings quoting failure text, `echo "--- ruff check ---"` banners in
`ruff_changed.sh` printed right before it runs the resolved binary. A grep gate
here would be red on arrival and would be silenced within a day. The AST and
the command-position rule read code as code.

## The self-test, and why it runs every time

A detector that finds nothing is indistinguishable from a detector that cannot
see, and this repository has been bitten by that exact shape more than once --
a scanner with no browser returning `[]` and exit 0, a postgres tier reporting
147 skips that read as green. So `test_the_detector_can_see` feeds it a file
that IS the defect and a file that is deliberately near-miss, and both verdicts
have to come out right before the sweep below means anything.

The near-miss case is the one that matters. Three red rows would only prove the
detector reacts to *any* change; the near-miss proves it reacts to the right
one -- it holds the property (ruff resolved through the pin) while changing
everything around it, and must stay clean.

## What this does NOT prove

- Nothing here runs ruff. A path that resolves the pin and then ignores the
  answer passes.
- `.github/workflows/*.yml` is out of scope. The lint job installs the pin into
  the runner before calling `ruff_changed.sh`, so bare `ruff` there IS the pin;
  deciding that from YAML would mean tracking which steps share a shell, and a
  gate that models a runner will drift from it. `tests/test_gate_covers_every_workflow_job.py`
  holds the narrower line for workflows.
- It cannot see ruff invoked through a name it computes at runtime from
  something other than the two forms above -- read out of a config file, joined
  from parts, returned by a helper in another module.

  The first draft of this file said "nothing in the tree does that today" and
  stopped there. That sentence was true when written and false eight hours
  later: #252 landed `tests/qa/qa-tt-0010/test_duong_phan_quyet_ruff_thu_hai.py`,
  which resolves `shutil.which("ruff")` into a local and hands that local to
  `subprocess.run`. The gate stayed green through the merge -- git reports no
  conflict between a new detector and a new file it cannot read.

  Measured before the rule below was widened, on four spellings of one
  violation: literal argv[0] -> 1 finding; `which` into a local -> 0; `which`
  inline -> 0; module constant `RUFF = "ruff"` -> 0. One in four. The three
  silent spellings are why the rule is written over what argv[0] *evaluates to*
  rather than over what it looks like.
- The guarantee `ruff_pinned.sh` gives is "a binary reporting the pinned
  version number", not "that binary". A shim that lies about `--version`
  passes, as tests/test_ruff_pinned.py already records.
"""

from __future__ import annotations

import ast
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The names through which a Python file starts a process.
SUBPROCESS_CALLS = frozenset({"run", "call", "check_call", "check_output", "Popen"})

#: A shell command position: the start of a line, or just after a separator
#: that ends the previous command. `"$RUFF" check` fails to match because the
#: word is quoted-expanded, and `command -v ruff` because `command` holds the
#: position.
SHELL_RUFF = re.compile(r"(?:^|[|;&(]|\|\||&&)\s*ruff\s+(?P<rest>.*)$")

#: Flags that make ruff describe itself instead of judging anything. Asking a
#: binary its version is how `tests/test_ruff_pinned.py` proves a hostile shim
#: is really on PATH before asserting the gate rejects it -- the probe has to
#: use the bare name, because the bare name is the thing under test. A probe
#: cannot produce a verdict about repository files, so it is outside the rule
#: rather than excused from it. Narrow on purpose: one real argument, and this
#: stops applying.
PROBE_ONLY = frozenset({"--version", "-V", "--help", "-h"})


def tracked(*globs: str) -> list[Path]:
    """Files git tracks, so an untracked scratch file cannot fail the gate."""
    out = subprocess.run(
        ["git", "ls-files", "-z", *globs],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(REPO_ROOT / name for name in out.split("\0") if name)


def _argv(node: ast.Call) -> list[ast.expr]:
    """The argv nodes a call was handed, in either shape it can take.

    `run(["ruff", ...])` is the list shape. `run("ruff", "--version")` is the
    varargs shape used by the thin `run(*argv)` helpers in tests/. Both are
    read, because a rule that only understood one of them would be a rule a
    future file steps around by accident.
    """
    if not node.args:
        return []
    first = node.args[0]
    if isinstance(first, (ast.List, ast.Tuple)):
        return list(first.elts)
    return list(node.args)


def _is_path_lookup(node: ast.expr) -> bool:
    """True for `shutil.which("ruff")` -- the machine's ruff, not the pin.

    `path=` excludes the call: that form asks a directory the caller names,
    which is how a test proves a shim it just built sits at the front of a PATH
    it just built. The question this gate asks is "which binary answered", and
    a caller who names the directory has already answered it.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    if name != "which":
        return False
    if any(kw.arg == "path" for kw in node.keywords):
        return False
    return bool(node.args) and (
        isinstance(node.args[0], ast.Constant) and node.args[0].value == "ruff"
    )


def _path_bound_names(tree: ast.AST) -> set[str]:
    """Names this file binds to the machine's ruff.

    Collected file-wide rather than per-scope, deliberately. Resolving scopes
    correctly would let a violation hide behind a shadowed name, and the cost
    of the coarse version is a false report only if a file binds `ruff = "ruff"`
    in one function and a pinned path to the same name in another -- at which
    point the file has a worse problem than this gate.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        if not (
            (isinstance(value, ast.Constant) and value.value == "ruff")
            or _is_path_lookup(value)
        ):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _is_bare_ruff_verdict(argv: list[ast.expr], path_bound: set[str]) -> bool:
    """True when *argv* executes the machine's ruff to judge something.

    argv[0] must evaluate to PATH's ruff -- as a literal, as an inline
    `shutil.which("ruff")`, or through a name this file bound to either.
    Everything after it decides verdict from probe: all-literal and drawn from
    PROBE_ONLY is a probe; anything else -- including an argument this gate
    cannot read, such as a variable holding a path -- is a verdict. Unreadable
    resolves to "report it", since a gate that stays quiet when unsure is the
    failure mode being closed.
    """
    if not argv:
        return False
    head = argv[0]
    resolves_to_path_ruff = (
        (isinstance(head, ast.Constant) and head.value == "ruff")
        or _is_path_lookup(head)
        or (isinstance(head, ast.Name) and head.id in path_bound)
    )
    if not resolves_to_path_ruff:
        return False
    rest = argv[1:]
    literal = [n.value for n in rest if isinstance(n, ast.Constant)]
    # `rest` must be non-empty. An argv of exactly ["ruff"] carries no probe
    # flag, so calling it a probe would be inferring intent from an absence --
    # and "no arguments I can read" is the unsure case, which reports.
    if rest and len(literal) == len(rest) and set(literal) <= PROBE_ONLY:
        return False
    return True


def python_offenders(source: str, label: str) -> list[str]:
    """Every `subprocess.*` call in *source* that judges with a bare ruff."""
    offenders: list[str] = []
    tree = ast.parse(source, filename=label)
    path_bound = _path_bound_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # `subprocess.run(...)` and a bare `run(...)` imported from it both
        # count: the second form is how a file would slip past a check that
        # only looked for the dotted name.
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in SUBPROCESS_CALLS:
            continue
        if _is_bare_ruff_verdict(_argv(node), path_bound):
            offenders.append(f"{label}:{node.lineno}")
    return offenders


def shell_offenders(source: str, label: str) -> list[str]:
    """Every line of *source* that runs `ruff` as a command word to judge."""
    offenders: list[str] = []
    for number, line in enumerate(source.splitlines(), start=1):
        # Comments carry most of this repository's mentions of ruff. Cutting at
        # the first `#` is coarse -- it would also cut a `#` inside a string --
        # but it errs toward NOT reporting, and a false accusation is what gets
        # a gate disabled.
        code = line.split("#", 1)[0]
        match = SHELL_RUFF.search(code)
        if match is None:
            continue
        # Same probe rule as Python, so the two halves cannot disagree about
        # what counts. `ruff --version` describes the binary; it judges nothing.
        rest = match.group("rest").split()
        if rest and set(rest) <= PROBE_ONLY:
            continue
        offenders.append(f"{label}:{number}")
    return offenders


class RuffVerdictsUseThePin(unittest.TestCase):
    def test_the_detector_can_see(self) -> None:
        """Red on the defect, clean on a near-miss that keeps the property.

        Without the second half a passing sweep says only "the detector reacts
        to something". With it, the sweep says "the detector reacts to an
        unpinned ruff and not to the shape of the code around it".
        """
        guilty_py = (
            "import subprocess\n"
            'subprocess.run(["ruff", "format", "--check", path])\n'
            'subprocess.check_output("ruff")\n'
            'run(["ruff", "check"])\n'
        )
        self.assertEqual(
            python_offenders(guilty_py, "canary-bad.py"),
            ["canary-bad.py:2", "canary-bad.py:3", "canary-bad.py:4"],
            "the Python detector missed a bare-ruff subprocess call",
        )

        # The same violation in the three spellings that do not put the word
        # "ruff" in argv[0]. Every one of these returned 0 findings until this
        # row existed, and the middle one is the shape #252 actually shipped --
        # so this is a regression row against a live miss, not a hypothetical.
        # Written as three separate spellings on purpose: one canary in the
        # shape the author finds natural is how a detector passes its own
        # self-test while blind to the other ways of writing the same thing.
        spelled_differently = (
            "import shutil, subprocess\n"
            'found = shutil.which("ruff")\n'
            'subprocess.run([found, "format", "--check", path])\n'
            'subprocess.run([shutil.which("ruff"), "check", path])\n'
            'RUFF = "ruff"\n'
            'subprocess.run([RUFF, "format", path])\n'
        )
        self.assertEqual(
            python_offenders(spelled_differently, "canary-spelling.py"),
            ["canary-spelling.py:3", "canary-spelling.py:4", "canary-spelling.py:6"],
            "a PATH-resolved ruff reached a subprocess argv unreported",
        )

        # Keeps the property, changes everything else: the pin is resolved, so
        # every line here is correct and none may be reported.
        innocent_py = (
            "import subprocess\n"
            '# subprocess.run(["ruff", "check"]) -- how NOT to do it\n'
            'MESSAGE = "run: ruff format the offenders"\n'
            'subprocess.run([pinned_ruff(), "format", "--check", path])\n'
            "subprocess.run([str(RUFF_PINNED)], capture_output=True)\n"
            'subprocess.run(["scripts/ruff_changed.sh", base])\n'
            'shutil.which("ruff")\n'
            'run("ruff", "--version", env=self.env)\n'
        )
        self.assertEqual(
            python_offenders(innocent_py, "canary-good.py"),
            [],
            "the Python detector accused a call that resolves the pin",
        )

        # Near-misses of the WIDENED rule specifically. Each holds the property
        # -- no machine-resolved ruff renders a verdict -- while sitting as
        # close to the new logic as code can. If the rule is ever loosened into
        # "mentions shutil.which" or "argv[0] is a variable", these go red and
        # say so, which is the row that separates a gate that measures the
        # property from a gate that measures whether a file was touched.
        near_miss_py = (
            "import shutil, subprocess\n"
            'found = shutil.which("ruff", path=bin_dir)\n'
            'subprocess.run([found, "--version"])\n'
            'if shutil.which("ruff") is None:\n'
            '    self.fail("no ruff at all")\n'
            "binary = pinned_ruff()\n"
            'subprocess.run([binary, "format", "--check", path])\n'
            'other = shutil.which("black")\n'
            'subprocess.run([other, "--check", path])\n'
        )
        self.assertEqual(
            python_offenders(near_miss_py, "canary-near.py"),
            [],
            "the widened rule accused code that never lets PATH decide",
        )

        # The probe carve-out has to stay narrow: one real argument alongside
        # `--version` and it is a verdict again. Without this row the rule
        # could widen to "mentions --version" and nobody would notice.
        self.assertEqual(
            python_offenders(
                'run("ruff", "--version", "check", path)\n', "canary-edge.py"
            ),
            ["canary-edge.py:1"],
            "a probe flag was allowed to launder a real ruff invocation",
        )
        self.assertEqual(
            python_offenders('subprocess.run(["ruff", flag])\n', "canary-var.py"),
            ["canary-var.py:1"],
            "an argument the gate cannot read must be reported, not excused",
        )

        guilty_sh = "ruff check --no-cache foo.py\ncat x | ruff format -\n"
        self.assertEqual(
            shell_offenders(guilty_sh, "canary-bad.sh"),
            ["canary-bad.sh:1", "canary-bad.sh:2"],
            "the shell detector missed ruff in a command position",
        )

        innocent_sh = (
            "# ruff check runs here, eventually\n"
            'echo "--- ruff check ---"\n'
            '"$RUFF" check --no-cache "${files[@]}"\n'
            "command -v ruff >/dev/null 2>&1\n"
            "version_of ruff\n"
            'RUFF="$("$RUFF_PINNED")"\n'
            "ruff --version\n"
        )
        self.assertEqual(
            shell_offenders(innocent_sh, "canary-good.sh"),
            [],
            "the shell detector accused a line that does not execute bare ruff",
        )
        self.assertEqual(
            shell_offenders("ruff --version check foo.py\n", "canary-edge.sh"),
            ["canary-edge.sh:1"],
            "a probe flag was allowed to launder a real ruff invocation",
        )

    def test_the_sweep_actually_reads_files(self) -> None:
        """A pass must mean files were read, not that the glob found nothing."""
        files = tracked("*.py", "*.sh")
        self.assertGreater(
            len(files),
            100,
            f"expected the tree's Python and shell files, found {len(files)} "
            f"-- has the layout moved? A gate that inspects nothing must not "
            f"report success.",
        )

    def test_no_gate_renders_a_ruff_verdict_with_an_unpinned_ruff(self) -> None:
        offenders: list[str] = []
        for path in tracked("*.py", "*.sh"):
            label = str(path.relative_to(REPO_ROOT))
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:  # pragma: no cover - no such file today
                continue
            if path.suffix == ".py":
                try:
                    offenders.extend(python_offenders(source, label))
                except SyntaxError:
                    # Deliberately broken fixtures exist under tests/. Their
                    # syntax is somebody else's gate's business, not this one's.
                    continue
            else:
                offenders.extend(shell_offenders(source, label))

        self.assertEqual(
            sorted(offenders),
            [],
            "these run ruff under its bare name, so their verdict comes from "
            "whatever\nversion the machine happens to have rather than the pin "
            "CI installs:\n  "
            + "\n  ".join(sorted(offenders))
            + "\n\nResolve it instead:\n"
            '  shell:   RUFF="$(scripts/ruff_pinned.sh)" && "$RUFF" check ...\n'
            "  python:  subprocess.run([pinned_ruff(), ...])  "
            "(see tests/test_qa_scripts_are_ruff_formatted.py)",
        )
