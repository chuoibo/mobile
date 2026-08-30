"""The docker gate must judge THIS tree's image, not whichever tree tagged last.

## What went wrong

`scripts/gate.sh docker` built `mobile-api:gate` and ran `mobile-api-gate`.
Both names are global on a Docker daemon, and this machine runs five worktrees
of one repository against one daemon.

Measured 2026-08-30 (QA lane, #291). The reporter had merged #288 into their
tree, so their `services/api/app/api/routes/memories.py` line 18 read
`from fastapi import APIRouter, Depends, Query, Response, status`. The stage
was red anyway, at that file, with the assertion #288 removed. Opening the
image the stage had just "built" showed a different source:

    $ docker run --rm mobile-api:gate grep -n "^from fastapi import" \\
          /srv/app/api/routes/memories.py
    18:from fastapi import APIRouter, Depends, Query, status

That is another worktree's file. A second lane had run the same stage in
between, and `docker build -t mobile-api:gate` moved the tag out from under
the first. The same log carried two `No such container: mobile-api-gate`
lines -- the other lane's `docker rm -f` deleting a container mid-poll.

## Why this is worse than the red it produced

A false red is loud. The same collision in the other direction is silent: lane
A builds a tree that boots, lane B reads that image and concludes ITS tree
boots. Nothing in the stage's output distinguishes the two, and on 2026-08-30
the Lead adopted the rule "a PR that changes a route declaration does not merge
until the docker stage is green". That rule rests entirely on this stage
answering about the tree in front of it.

## How this file measures it

`docker` on PATH is replaced by a stub that records its argv and exits 0. That
makes the stage run in milliseconds and, more to the point, makes the question
answerable at all: what is being asserted is not what Docker did, it is which
NAMES the stage asked Docker for. Two lanes that never utter the same name
cannot take each other's artifact, whatever the daemon does with them.

Lane B is a copy of `scripts/` plus the two files the stage reads, in a temp
directory, because `gate.sh` locates the tree from its own path. That is the
reported failure exactly: two checkouts, one daemon.

## What this proves and what it does not

It proves the stage addresses image tags and container names that no second
checkout and no second run of this checkout can also address, and that a run
still reuses one tag across its own stages so the pinned-import stage keeps
hitting the build cache the docker stage filled.

It does not prove the build context is right, that the image is the tree, or
that Docker isolates two differently-named images -- that last one is a
property of Docker, not of this repository. It also cannot see a collision
introduced by something other than a name, an env var both lanes read, say,
or a shared bind mount.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE = REPO_ROOT / "scripts" / "gate.sh"

# Recording stub. It answers the one query whose value the stage branches on --
# the health poll -- so the stage reaches its end instead of spinning for sixty
# seconds, and records everything else. Exit 0 throughout: the subject here is
# the argv, not the verdict.
STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$DOCKER_ARGV_LOG"
for a in "$@"; do
  case "$a" in *State.Health.Status*) echo healthy; exit 0 ;; esac
done
exit 0
"""

# Docker subcommands whose last positional argument is a container.
CONTAINER_SUBCOMMANDS = {"rm", "logs", "inspect", "stop", "kill", "start"}
# ... and the ones whose last positional argument is an image.
IMAGE_SUBCOMMANDS = {"rmi"}


class Artifacts:
    """The image tags and container names one gate run asked Docker for."""

    def __init__(self) -> None:
        self.images: set[str] = set()
        self.containers: set[str] = set()
        self.removed_images: set[str] = set()
        self.tokens: set[str] = set()

    def feed(self, line: str) -> None:
        argv = line.split()
        if not argv:
            return
        self.tokens.update(argv)
        sub = argv[0]
        i = 0
        while i < len(argv):
            if argv[i] == "-t" and i + 1 < len(argv):
                self.images.add(argv[i + 1])
                i += 2
                continue
            if argv[i] == "--name" and i + 1 < len(argv):
                self.containers.add(argv[i + 1])
                i += 2
                continue
            i += 1
        if sub in CONTAINER_SUBCOMMANDS and len(argv) > 1:
            self.containers.add(argv[-1])
        if sub in IMAGE_SUBCOMMANDS and len(argv) > 1:
            self.removed_images.add(argv[-1])
            self.images.add(argv[-1])
        # `docker image rm -f <tag>` -- the spelling gate.sh uses to untag.
        if sub == "image" and len(argv) > 2 and argv[1] == "rm":
            self.removed_images.add(argv[-1])
            self.images.add(argv[-1])


def run_gate(tree: Path, *stages: str) -> Artifacts:
    """Run gate stages in `tree` with a recording docker, return what it named."""
    with tempfile.TemporaryDirectory() as sandbox:
        bindir = Path(sandbox) / "bin"
        bindir.mkdir()
        (bindir / "docker").write_text(STUB, encoding="utf-8")
        (bindir / "docker").chmod(0o755)
        log = Path(sandbox) / "argv.log"
        log.touch()

        env = dict(os.environ)
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        env["DOCKER_ARGV_LOG"] = str(log)
        # A run id inherited from the caller would defeat the whole point of
        # asking two lanes what they name things.
        env.pop("MOBILE_GATE_RUN_ID", None)
        env.pop("MOBILE_PINNED_IMAGE", None)

        subprocess.run(
            ["bash", str(tree / "scripts" / "gate.sh"), *stages],
            cwd=tree,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        found = Artifacts()
        for line in log.read_text(encoding="utf-8").splitlines():
            found.feed(line)
        return found


class GateDockerNamesArePerLane(unittest.TestCase):
    """Two checkouts on one daemon must not address one artifact."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        lane_b = Path(cls._tmp.name) / "lane-b"
        (lane_b / "services" / "api").mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "scripts", lane_b / "scripts")
        for name in ("Dockerfile", "requirements-dev.txt"):
            shutil.copy(
                REPO_ROOT / "services" / "api" / name,
                lane_b / "services" / "api" / name,
            )
        cls.lane_b = lane_b

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_docker_stage_names_an_image_and_a_container(self) -> None:
        """The premise of every case below: the stage names something.

        Without this, a rename that made the stage stop tagging altogether
        would satisfy every disjointness assertion in this file with two empty
        sets -- the shape that reads as a pass because nothing was measured.
        """
        found = run_gate(REPO_ROOT, "docker")
        self.assertTrue(found.images, "chặng docker không đặt tên ảnh nào")
        self.assertTrue(found.containers, "chặng docker không đặt tên container nào")

    def test_two_checkouts_do_not_share_an_image_tag(self) -> None:
        a = run_gate(REPO_ROOT, "docker")
        b = run_gate(self.lane_b, "docker")
        self.assertTrue(a.images and b.images)
        shared = a.images & b.images
        self.assertEqual(
            set(),
            shared,
            "hai cây dùng chung tag ảnh %s — cây dựng sau ghi đè tag của cây dựng trước, "
            "và chặng chấm điểm ảnh của người khác" % sorted(shared),
        )

    def test_two_checkouts_do_not_share_a_container_name(self) -> None:
        a = run_gate(REPO_ROOT, "docker")
        b = run_gate(self.lane_b, "docker")
        self.assertTrue(a.containers and b.containers)
        shared = a.containers & b.containers
        self.assertEqual(
            set(),
            shared,
            "hai cây dùng chung tên container %s — `docker rm -f` của cây này xoá "
            "container đang được cây kia đo" % sorted(shared),
        )

    def test_two_runs_of_one_checkout_do_not_share_names(self) -> None:
        """Same worktree, twice, concurrently. The reported collision was across
        checkouts; a fix keyed only on the path would leave this one open, and
        one lane running the gate twice is not an exotic scenario."""
        a = run_gate(REPO_ROOT, "docker")
        b = run_gate(REPO_ROOT, "docker")
        self.assertTrue(a.images and b.images)
        self.assertEqual(
            set(), a.images & b.images, "hai lượt chạy cùng cây dùng chung tag ảnh"
        )
        self.assertEqual(
            set(),
            a.containers & b.containers,
            "hai lượt chạy cùng cây dùng chung tên container",
        )

    def test_pinned_import_stage_is_per_lane_too(self) -> None:
        """`check_pinned_import.sh` builds the same image under its own default.

        It is the stage the Lead now requires on every route-declaration PR, so
        a shared tag here means the two-second check reports on whichever tree
        built last -- the loud direction of the same bug, and the quiet one."""
        a = run_gate(REPO_ROOT, "pinned-import")
        b = run_gate(self.lane_b, "pinned-import")
        self.assertTrue(a.images and b.images)
        shared = a.images & b.images
        self.assertEqual(
            set(), shared, "chặng pinned-import dùng chung tag ảnh %s" % sorted(shared)
        )

    def test_one_run_reuses_one_tag_across_its_own_stages(self) -> None:
        """Isolation between lanes must not cost isolation's opposite inside one.

        `check_pinned_import.sh` says it reuses the docker stage's build; two
        different tags in one run means two builds and two images left behind
        for what is one artifact."""
        found = run_gate(REPO_ROOT, "pinned-import", "docker")
        self.assertTrue(found.images)
        self.assertEqual(
            1,
            len(found.images),
            "một lượt gate dựng %d tag khác nhau (%s) — pinned-import và docker "
            "phải nói về cùng một ảnh" % (len(found.images), sorted(found.images)),
        )

    def test_no_globally_named_leftover(self) -> None:
        """A net under the two cases above.

        They read the names out of `-t` and `--name`. A half-applied fix that
        parameterised the build but left one `docker run mobile-api:gate`
        behind would pass both and still reach into another lane's tree, so
        every token the stage hands Docker that looks like this gate's artifact
        has to be one of the names it just generated."""
        found = run_gate(REPO_ROOT, "docker")
        known = found.images | found.containers
        stray = {
            t
            for t in found.tokens
            if (t.startswith("mobile-api:") or t.startswith("mobile-api-"))
            and t not in known
        }
        self.assertEqual(
            set(), stray, "token mang tên toàn cục còn sót: %s" % sorted(stray)
        )

    def test_the_run_untags_the_image_it_created(self) -> None:
        """Per-run names trade one collision for unbounded accumulation.

        A fixed tag is reused forever; a generated one is a new dangling image
        every run on a machine that runs this gate dozens of times a day. The
        run has to take its own tag back off."""
        found = run_gate(REPO_ROOT, "docker")
        self.assertTrue(found.images)
        self.assertTrue(
            found.images <= found.removed_images,
            "lượt chạy dựng %s nhưng chỉ gỡ tag %s — mỗi lượt để lại một ảnh"
            % (sorted(found.images), sorted(found.removed_images)),
        )


if __name__ == "__main__":
    unittest.main()
