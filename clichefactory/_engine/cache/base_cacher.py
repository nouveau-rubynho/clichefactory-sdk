from __future__ import annotations
from abc import ABC, abstractmethod
from clichefactory._engine.models.normalized_doc import NormalizedDoc


class Cacher(ABC):
    """
    Abstraction for a caching backend.
    Implementations: FileSystemCacher, RedisCacher, etc.
    """

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if a cached document for `key` exists."""
        ...

    @abstractmethod
    def load(self, key: str) -> NormalizedDoc:
        """Return the cached NormalizedDoc for `key` or raise if missing."""
        ...

    @abstractmethod
    def save(self, key: str, doc: NormalizedDoc) -> None:
        """Persist the NormalizedDoc for `key`."""
        ...

    def delete(self, key: str) -> None:
        """Optional: remove cached entry. Default is 'not implemented'."""
        raise NotImplementedError
