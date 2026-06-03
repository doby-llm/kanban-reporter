from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GitContext:
    repo_path: str | None = None
    branch: str | None = None
    head: str | None = None
