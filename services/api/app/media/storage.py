"""Store sanitized photos under opaque keys outside the repository."""

from __future__ import annotations

import os
import pathlib
import re
import secrets
import tempfile

MEDIA_ROOT_ENV = "MOBILE_MEDIA_ROOT"

_STORAGE_KEY = re.compile(r"[0-9a-f]{32}")


def media_root() -> pathlib.Path:
    """Keep uploads away from paths that can be accidentally committed."""

    configured = os.environ.get(MEDIA_ROOT_ENV)
    root = (
        pathlib.Path(configured)
        if configured is not None
        else pathlib.Path.home() / ".local" / "share" / "rudi" / "media"
    )
    return root.expanduser().resolve()


def new_storage_key() -> str:
    """Use an opaque name that reveals no participant or context identity."""

    return secrets.token_hex(16)


class PhotoStorage:
    def __init__(self, root: pathlib.Path | str | None = None) -> None:
        self.root = media_root() if root is None else pathlib.Path(root).resolve()

    def write(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        temporary_path: pathlib.Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{key}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = pathlib.Path(temporary.name)
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())

            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def read(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def _path_for(self, key: str) -> pathlib.Path:
        if not isinstance(key, str) or _STORAGE_KEY.fullmatch(key) is None:
            raise ValueError(
                "Storage keys must be exactly 32 lowercase hex characters."
            )
        return self.root / key[:2] / key[2:4] / key
