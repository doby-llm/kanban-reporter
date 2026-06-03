from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CiContext:
    provider: str | None = None
    status: str | None = None
    url: str | None = None
