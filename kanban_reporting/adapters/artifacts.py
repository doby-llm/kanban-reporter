from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactContext:
    label: str
    path_or_url: str
    safe_to_attach: bool = True
