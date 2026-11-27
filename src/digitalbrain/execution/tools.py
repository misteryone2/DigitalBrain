"""Read-only tool definitions for DigitalBrain execution layer.

M4 baseline: only safe, inspectable, read-only tools. No shell, no write, no
network. All paths are constrained to an allowed workspace root.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    handler: Callable[..., dict[str, Any]]


def _resolve_safe_path(root: Path, raw_path: str) -> Path:
    if not raw_path or not raw_path.strip():
        raise ValueError("Path must not be empty.")
    candidate = Path(raw_path)
    resolved = (candidate if candidate.is_absolute() else (root / candidate)).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Path is outside allowed workspace.") from exc
    return resolved


def tool_list_dir(root: Path, *, path: str = ".", limit: int = 200) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("Limit must be greater than zero.")
    target = _resolve_safe_path(root, path)
    if not target.exists():
        raise ValueError(f"Path not found: {path}")
    if not target.is_dir():
        raise ValueError(f"Not a directory: {path}")
    entries = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:limit]:
        entries.append(
            {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            }
        )
    return {"path": str(target), "entries": entries}


def tool_read_file(root: Path, *, path: str, max_chars: int = 20_000) -> dict[str, Any]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")
    target = _resolve_safe_path(root, path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"File not found: {path}")
    data = target.read_text(encoding="utf-8", errors="replace")
    truncated = len(data) > max_chars
    return {
        "path": str(target),
        "content": data[:max_chars],
        "truncated": truncated,
        "chars": min(len(data), max_chars),
    }


def tool_grep(root: Path, *, pattern: str, path: str = ".", limit: int = 100) -> dict[str, Any]:
    if not pattern or not pattern.strip():
        raise ValueError("Pattern must not be empty.")
    if limit <= 0:
        raise ValueError("Limit must be greater than zero.")
    target = _resolve_safe_path(root, path)
    if not target.exists():
        raise ValueError(f"Path not found: {path}")
    matches: list[dict[str, Any]] = []
    files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file()]
    for file_path in files:
        if len(matches) >= limit:
            break
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.lower() in line.lower():
                matches.append({"path": str(file_path), "line": i, "text": line[:300]})
                if len(matches) >= limit:
                    break
    return {"pattern": pattern, "matches": matches, "count": len(matches)}


def default_readonly_tools(root: Path) -> dict[str, ToolSpec]:
    return {
        "list_dir": ToolSpec(
            name="list_dir",
            description="List directory entries within workspace.",
            read_only=True,
            handler=lambda **kw: tool_list_dir(root, **kw),
        ),
        "read_file": ToolSpec(
            name="read_file",
            description="Read a UTF-8 text file within workspace.",
            read_only=True,
            handler=lambda **kw: tool_read_file(root, **kw),
        ),
        "grep": ToolSpec(
            name="grep",
            description="Search for a text pattern in files within workspace.",
            read_only=True,
            handler=lambda **kw: tool_grep(root, **kw),
        ),
    }
