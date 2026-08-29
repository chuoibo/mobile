"""Where the bytes land, and what the filename gives away.

Two rules from the brief meet in this file. Uploaded pictures may not enter the
repository -- CLAUDE.md forbids real data inside any worktree, and a media root
that defaults to somewhere under `services/` would put a group's photographs one
`git add -A` away from being published. And a stored name may not be derivable
from a group id or a person id, because a filename that can be computed is a
filename that can be requested.
"""

from __future__ import annotations

import pathlib
import uuid

import pytest

from app.media.storage import MEDIA_ROOT_ENV, PhotoStorage, media_root, new_storage_key

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


def test_the_default_media_root_is_outside_this_repository(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(MEDIA_ROOT_ENV, raising=False)

    root = media_root()

    assert root.is_absolute()
    assert not root.is_relative_to(REPO_ROOT), (
        f"{root} is inside {REPO_ROOT}: uploaded photos would sit in the worktree"
    )


def test_the_repo_root_this_test_computed_is_really_the_repo_root():
    """Guard the guard. If `parents[4]` ever points at the wrong directory the
    assertion above passes for free and stops meaning anything."""

    assert (REPO_ROOT / ".git").exists()
    assert (REPO_ROOT / "services" / "api" / "app").is_dir()


def test_the_media_root_is_configurable(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv(MEDIA_ROOT_ENV, str(tmp_path / "anh"))

    assert media_root() == (tmp_path / "anh").resolve()


def test_a_storage_key_is_random_and_says_nothing_about_who_uploaded_it():
    context_id = uuid.uuid4()
    person_id = uuid.uuid4()

    keys = {new_storage_key() for _ in range(500)}

    assert len(keys) == 500, "keys collided; they are not random enough"
    for key in keys:
        assert len(key) == 32
        assert set(key) <= set("0123456789abcdef")
        assert context_id.hex not in key
        assert person_id.hex not in key


def test_bytes_written_come_back_identical(tmp_path):
    storage = PhotoStorage(tmp_path)
    key = new_storage_key()

    storage.write(key, b"\x89PNG\r\n\x1a\n hello")

    assert storage.read(key) == b"\x89PNG\r\n\x1a\n hello"


def test_the_stored_path_does_not_contain_any_id(tmp_path):
    """The directory layout is derived from the key alone.

    A scheme like `<context_id>/<n>.jpg` is guessable by anyone who has seen a
    group id in a URL, which is every member of that group and anybody they
    forwarded a link to.
    """

    context_id = uuid.uuid4()
    storage = PhotoStorage(tmp_path)
    key = new_storage_key()
    storage.write(key, b"x")

    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(written) == 1
    assert context_id.hex not in str(written[0])
    assert str(written[0]).count(key[:2]) >= 1


def test_a_key_shaped_like_a_path_cannot_escape_the_root(tmp_path):
    """`read` takes a key, never a path. Anything else is arbitrary file read."""

    storage = PhotoStorage(tmp_path)

    for hostile in ("../../etc/passwd", "..", "a/../../b", "/etc/passwd", ""):
        with pytest.raises(ValueError):
            storage.read(hostile)
        with pytest.raises(ValueError):
            storage.write(hostile, b"x")


def test_reading_a_key_that_was_never_written_raises_file_not_found(tmp_path):
    storage = PhotoStorage(tmp_path)

    with pytest.raises(FileNotFoundError):
        storage.read(new_storage_key())
