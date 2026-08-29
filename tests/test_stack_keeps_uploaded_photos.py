"""Photos uploaded to the stack must outlive the container that received them.

## What went wrong

`docker-compose.yml` gave Postgres a named volume and gave the photo directory
nothing. `app/media/storage.py` falls back to `$HOME/.local/share/rudi/media`,
which inside the container is the writable layer, so `docker compose build api
&& up -d api` threw every uploaded photo away. Measured on the shared stack
after one rebuild:

    select count(*) from uploaded_images;          ->  4
    find ~/.local/share/rudi/media -type f | wc -l ->  0

Four rows, no files. That asymmetry is what makes it worse than losing both:
an empty memory wall reads as "nothing here yet", while a wall that lists
memories whose photos 404 forever reads as a broken product.

## Why there are two kinds of case in one file

The YAML cases parse the file directly, so they gate on a machine with no
Docker -- including the `api` job, which is the one job that always runs. They
prove the declaration is present and has the right shape.

They cannot prove the behaviour. Three separate strings have to agree
(`MOBILE_MEDIA_ROOT`, the mount target, the directory the Dockerfile creates),
and agreeing today is a coincidence, not a property. Worse, the failure mode of
disagreement is not "photos vanish on rebuild" but "uploads fail with EACCES on
day one", because Docker creates a mount point absent from the image as
root:root while the API runs as uid 10001.

So the live case runs `scripts/check_media_persists.sh`, which writes a photo in
one container and reads it back in another, and skips OUT LOUD when Docker is
missing. A silent skip here would be indistinguishable from a pass.

## What this does not prove

Nothing here says the photos are backed up, or that `make clean` spares them --
it does not, and `make clean`'s refusal message now names the media volume for
that reason. It also says nothing about the four rows already orphaned on the
demo stack: those are kept deliberately, and the API answers them with a clean
404 (`avatar_not_found` / `photo_not_found`), measured against the running
stack rather than assumed from the code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "services" / "api" / "Dockerfile"
LIVE_GATE = REPO_ROOT / "scripts" / "check_media_persists.sh"

# The variable the code actually reads: `app/media/storage.py` does
# `os.environ.get("MOBILE_MEDIA_ROOT")`. Any other spelling is a variable
# nobody consumes, which is worse than an unset one because it looks configured.
MEDIA_ROOT_ENV = "MOBILE_MEDIA_ROOT"

# The runtime user in the image. `useradd --uid 10001 app`; a named volume is
# only writable by it when the mount target exists in the image and is owned by
# it, so this number is load-bearing rather than descriptive.
RUNTIME_USER = "app"


def compose_document() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def api_service() -> dict:
    return compose_document()["services"]["api"]


def media_root() -> str:
    return str(api_service()["environment"][MEDIA_ROOT_ENV])


def mounts_for(service: dict) -> list[dict]:
    """Normalise both spellings Compose accepts into one shape.

    Short syntax (`source:target:mode`) and long syntax (a mapping) mean the
    same thing to Compose. A test that understood only one would pass a file
    rewritten in the other while proving nothing.
    """

    parsed = []
    for entry in service.get("volumes") or []:
        if isinstance(entry, dict):
            parsed.append(
                {
                    "type": entry.get("type", "volume"),
                    "source": entry.get("source"),
                    "target": entry.get("target"),
                }
            )
            continue
        parts = str(entry).split(":")
        if len(parts) == 1:
            # An anonymous volume. It has a target and no name, which is
            # exactly the thing this file exists to reject.
            parsed.append({"type": "volume", "source": None, "target": parts[0]})
        else:
            source, target = parts[0], parts[1]
            kind = "bind" if source.startswith((".", "/", "~")) else "volume"
            parsed.append({"type": kind, "source": source, "target": target})
    return parsed


def covers(target: str, path: str) -> bool:
    """True when a mount at `target` contains `path` (or is it)."""

    target = target.rstrip("/")
    path = path.rstrip("/")
    return path == target or path.startswith(target + "/")


class MediaRootIsDeclared(unittest.TestCase):
    def test_the_api_service_pins_the_media_root(self):
        """Unset, the code falls back into the container's writable layer.

        This is the whole defect in one assertion: the fallback in
        `storage.py` is a reasonable default for a laptop and a data-loss bug
        for a container.
        """

        self.assertIn(
            MEDIA_ROOT_ENV,
            api_service()["environment"],
            f"service `api` không đặt {MEDIA_ROOT_ENV}; app sẽ ghi ảnh vào "
            "$HOME/.local/share/rudi/media, tức lớp ghi của container.",
        )

    def test_the_media_root_is_an_absolute_path(self):
        root = media_root()
        self.assertTrue(
            root.startswith("/"),
            f"{MEDIA_ROOT_ENV}={root!r} phải là đường tuyệt đối; "
            "đường tương đối giải theo cwd của tiến trình, không cố định.",
        )

    def test_the_media_root_is_not_inside_the_application_code(self):
        """`/srv` holds the app. A writable directory inside it is an upload
        path that has become a code path."""

        root = media_root()
        self.assertFalse(
            covers("/srv", root),
            f"{MEDIA_ROOT_ENV}={root!r} nằm trong cây mã ứng dụng.",
        )


class MediaRootIsBackedByANamedVolume(unittest.TestCase):
    def mount_covering_media_root(self) -> dict:
        root = media_root()
        for mount in mounts_for(api_service()):
            if mount["target"] and covers(mount["target"], root):
                return mount
        self.fail(
            f"Không mount nào của service `api` phủ {MEDIA_ROOT_ENV}={root!r}. "
            "Ảnh sẽ nằm trong lớp ghi của container và mất khi dựng lại."
        )

    def test_a_mount_covers_the_media_root(self):
        self.mount_covering_media_root()

    def test_that_mount_is_a_named_volume_and_not_a_bind(self):
        """A bind mount would put photographs of real bills at a path git can
        stage. The repo guard fails closed on binaries, but a guard is a net,
        not a floor."""

        mount = self.mount_covering_media_root()
        self.assertEqual(
            mount["type"],
            "volume",
            f"mount {mount!r} là bind mount; ảnh bill không được nằm ở đường "
            "mà git stage được (CLAUDE.md).",
        )
        self.assertIsNotNone(
            mount["source"],
            "volume ẩn danh: docker sinh tên mới mỗi lần dựng lại container, "
            "nên nó KHÔNG giữ được ảnh — nó chỉ trông giống thế.",
        )

    def test_the_volume_is_declared_at_the_top_level(self):
        mount = self.mount_covering_media_root()
        declared = compose_document().get("volumes") or {}
        self.assertIn(
            mount["source"],
            declared,
            f"volume {mount['source']!r} chưa khai ở mục `volumes:` gốc.",
        )

    def test_the_media_volume_is_not_the_postgres_volume(self):
        """Sharing one volume would let `make clean`-style surgery on one
        dataset take the other with it, and would put photo bytes inside the
        directory Postgres owns."""

        mount = self.mount_covering_media_root()
        self.assertNotEqual(mount["source"], "mobile-postgres-data")


class TheVolumeIsWritableByTheRuntimeUser(unittest.TestCase):
    """The half of this that a compose file cannot express.

    Docker copies ownership from the image when it first populates an empty
    named volume; when the path is absent from the image it creates the mount
    point root:root 0755 instead. Measured on this image, uid 10001 writing
    into a fresh volume at a path the image does not contain:

        drwxr-xr-x 2 0 0 /var/lib/rudi/media
        touch: cannot touch '/var/lib/rudi/media/x': Permission denied

    So a compose file that mounts the volume without the Dockerfile line does
    not lose photos on rebuild -- it refuses to store them at all.
    """

    def test_the_dockerfile_creates_the_media_root(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        root = media_root()
        self.assertIn(
            f"mkdir -p {root}",
            text,
            f"Dockerfile không tạo {root}; docker sẽ tự tạo mount point bằng "
            "root và mọi lượt tải ảnh lên chết với EACCES.",
        )

    def test_the_dockerfile_gives_it_to_the_runtime_user(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        root = media_root()
        self.assertIn(
            f"chown {RUNTIME_USER}:{RUNTIME_USER} {root}",
            text,
            f"{root} phải thuộc user `{RUNTIME_USER}` trong ảnh; quyền sở hữu "
            "đó là thứ named volume chép lại lúc mount lần đầu.",
        )


class TheLiveGateExists(unittest.TestCase):
    """A declaration test cannot fail for the reason the bug happened."""

    def test_the_live_gate_is_executable(self):
        self.assertTrue(LIVE_GATE.exists(), f"thiếu {LIVE_GATE}")
        self.assertTrue(os.access(LIVE_GATE, os.X_OK), f"{LIVE_GATE} không +x")

    def test_the_live_gate_refuses_to_run_against_the_shared_stack(self):
        """It ends in `down -v`. Pointed at `mobile-local` that is every
        lane's database and every uploaded photo on the machine."""

        result = subprocess.run(
            ["sh", str(LIVE_GATE)],
            cwd=REPO_ROOT,
            env={**os.environ, "MOBILE_MEDIA_GATE_PROJECT": "mobile-local"},
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 77:
            self.skipTest("BỎ QUA: máy này không có docker compose.")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Từ chối", result.stderr)


class PhotosSurviveANewContainer(unittest.TestCase):
    """The only case here that would have caught the original bug."""

    def test_a_photo_written_in_one_container_is_readable_in_another(self):
        if shutil.which("docker") is None:
            self.skipTest(
                "BỎ QUA: máy này không có docker. Các ca YAML ở trên đã chạy, "
                "nhưng KHÔNG ca nào chứng minh ảnh sống sót thật — điều đó cần "
                "dựng container."
            )
        result = subprocess.run(
            ["sh", str(LIVE_GATE)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        if result.returncode == 77:
            self.skipTest("BỎ QUA: " + result.stderr.strip().splitlines()[0])
        self.assertEqual(
            result.returncode,
            0,
            "check_media_persists.sh hỏng:\n" + result.stdout + result.stderr,
        )
        self.assertIn("ĐẠT", result.stdout)


if __name__ == "__main__":
    unittest.main()
