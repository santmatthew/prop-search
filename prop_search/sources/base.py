"""Source adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Listing


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self, config) -> list[Listing]:
        """Return listings matching the config's base filters (price/size/rooms).

        Geo and transit filters are applied later by the pipeline, on the common
        Listing structure.
        """
        raise NotImplementedError
