# aio/cache/filesystem.py
from __future__ import annotations

import pathlib
from clichefactory._engine.cache.base_cacher import Cacher
from clichefactory._engine.models.normalized_doc import NormalizedDoc


class FileSystemCacher(Cacher):
    """
    Simple filesystem-based cacher.
    - root: directory where cache files are stored
    - suffix: extension to use for cache files (e.g. ".bin", ".cache")
    """

    def __init__(self, root: str | pathlib.Path, suffix: str = ".cache") -> None:
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.suffix = suffix

    def _key_to_path(self, key: str) -> pathlib.Path:
        # Very simple mapping; you can also shard if you expect many files.
        return self.root / f"{key}{self.suffix}"

    def exists(self, key: str) -> bool:
        return self._key_to_path(key).is_file()

    def load(self, key: str) -> NormalizedDoc:
        path = self._key_to_path(key)
        if not path.is_file():
            raise FileNotFoundError(f"No cache entry for key={key!r} at {path}")
        data = path.read_bytes()
        return NormalizedDoc.deserialize(data)

    def save(self, key: str, doc: NormalizedDoc) -> None:
        path = self._key_to_path(key)
        if path.exists():
            # Idempotent; skip rewrites by default
            return
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(doc.serialize())
        tmp_path.replace(path)

    def delete(self, key: str) -> None:
        path = self._key_to_path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
