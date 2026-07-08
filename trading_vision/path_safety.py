"""Path constraints for built-in file imports."""

from __future__ import annotations

from pathlib import Path


def require_path_inside(root: Path, path: Path) -> Path:
    """Return the resolved path only if it stays inside root."""

    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise ValueError(f"Path must stay inside {resolved_root}: {path}")
    return resolved_path
