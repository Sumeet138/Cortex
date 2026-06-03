from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from pathlib import Path

from app.models import ContentItem

REGISTRY: dict[str, type["SourceAdapter"]] = {}


class SourceAdapter(ABC):
    @abstractmethod
    def parse(self, file: Path) -> Iterator[ContentItem]:
        """Stream-parse an export file, yielding ContentItems one at a time."""
        ...


def register(source: str) -> "Callable[[type[SourceAdapter]], type[SourceAdapter]]":
    """Decorator that registers a SourceAdapter subclass under the given source name."""
    def decorator(cls: type[SourceAdapter]) -> type[SourceAdapter]:
        REGISTRY[source] = cls
        return cls
    return decorator
