"""Tool definitions for DigitalBrain execution layer.

M4 baseline: safe, inspectable, read-only tools by default. No shell, no network.
All paths are constrained to an allowed workspace root. Mutating tools may exist
in registry but must be blocked by policy unless explicitly enabled and approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    handler: Callable[..., dict[str, Any]]
    risk_class: str = "none"  # none|low|medium|high
    timeout_s: float = 10.0
    limits: dict[str, Any] = field(default_factory=dict)


def _resolve_safe_path(root: Path, raw_path: str, *, allow_missing: bool = False) -> Path:
    if not raw_path or not raw_path.strip():
        raise ValueError("Path must not be empty.")
    candidate = Path(raw_path)
    resolved = (candidate if candidate.is_absolute() else (root / candidate)).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Path is outside allowed workspace.") from exc

    # Reject symlink escapes along existing path components.
    probe = root_resolved
    rel = resolved.relative_to(root_resolved)
    for part in rel.parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("Symlink paths are not allowed.")
    if not allow_missing and not resolved.exists() and resolved != root_resolved:
        # For existing-target operations, missing is handled by callers; this keeps logic explicit.
        pass
    return resolved


def tool_list_dir(root: Path, *, path: str = ".", limit: int = 200) -> dict[str, Any]:
    if limit <= 0 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")
    target = _resolve_safe_path(root, path)
    if not target.exists():
        raise ValueError(f"Path not found: {path}")
    if not target.is_dir():
        raise ValueError(f"Not a directory: {path}")
    entries = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:limit]:
        if entry.is_symlink():
            entries.append({"name": entry.name, "type": "symlink", "size": None})
            continue
        entries.append(
            {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            }
        )
    return {"path": str(target), "entries": entries}


def tool_read_file(root: Path, *, path: str, max_chars: int = 20_000) -> dict[str, Any]:
    if max_chars <= 0 or max_chars > 200_000:
        raise ValueError("max_chars must be between 1 and 200000.")
    target = _resolve_safe_path(root, path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"File not found: {path}")
    if target.is_symlink():
        raise ValueError("Symlink paths are not allowed.")
    data = target.read_text(encoding="utf-8", errors="replace")
    truncated = len(data) > max_chars
    return {
        "path": str(target),
        "content": data[:max_chars],
        "truncated": truncated,
        "chars": min(len(data), max_chars),
    }


def tool_grep(root: Path, *, pattern: str, path: str = ".", limit: int = 100, max_files: int = 500) -> dict[str, Any]:
    if not pattern or not pattern.strip():
        raise ValueError("Pattern must not be empty.")
    if limit <= 0 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")
    if max_files <= 0 or max_files > 2000:
        raise ValueError("max_files must be between 1 and 2000.")
    target = _resolve_safe_path(root, path)
    if not target.exists():
        raise ValueError(f"Path not found: {path}")
    matches: list[dict[str, Any]] = []
    files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file()]
    scanned = 0
    for file_path in files:
        if len(matches) >= limit or scanned >= max_files:
            break
        if file_path.is_symlink():
            continue
        scanned += 1
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pattern.lower() in line.lower():
                matches.append({"path": str(file_path), "line": i, "text": line[:300]})
                if len(matches) >= limit:
                    break
    return {"pattern": pattern, "matches": matches, "count": len(matches), "scanned_files": scanned}


def tool_write_file(root: Path, *, path: str, content: str, overwrite: bool = False, max_chars: int = 100_000) -> dict[str, Any]:
    """Mutating tool: disabled by default policy. Requires explicit approval + ready gate."""
    if not isinstance(content, str):
        raise ValueError("content must be a string.")
    if max_chars <= 0 or max_chars > 500_000:
        raise ValueError("max_chars must be between 1 and 500000.")
    if len(content) > max_chars:
        raise ValueError(f"content exceeds max_chars ({max_chars}).")
    target = _resolve_safe_path(root, path, allow_missing=True)
    if target.exists():
        if target.is_symlink():
            raise ValueError("Symlink paths are not allowed.")
        if not overwrite:
            raise ValueError("File exists and overwrite is false.")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Ensure parent chain is not symlinked outside/inside root in unsafe way.
    _resolve_safe_path(root, str(target.parent.relative_to(root.resolve())))
    target.write_text(content, encoding="utf-8")
    return {"path": str(target), "chars": len(content), "overwritten": target.exists()}


def tool_mkdir(root: Path, *, path: str, exist_ok: bool = True) -> dict[str, Any]:
    """Mutating low-risk tool: creates directory within workspace."""
    target = _resolve_safe_path(root, path, allow_missing=True)
    if target.exists():
        if target.is_symlink():
            raise ValueError("Symlink paths are not allowed.")
        if not target.is_dir():
            raise ValueError("Path exists and is not a directory.")
        if not exist_ok:
            raise ValueError("Directory already exists.")
    target.mkdir(parents=True, exist_ok=exist_ok)
    return {"path": str(target), "created": True}


def default_tools(root: Path) -> dict[str, ToolSpec]:
    return {
        "list_dir": ToolSpec(
            name="list_dir",
            description="List directory entries within workspace.",
            read_only=True,
            risk_class="none",
            timeout_s=5.0,
            limits={"limit_max": 500, "max_output_bytes": 262144},
            handler=lambda **kw: tool_list_dir(root, **kw),
        ),
        "read_file": ToolSpec(
            name="read_file",
            description="Read a UTF-8 text file within workspace.",
            read_only=True,
            risk_class="none",
            timeout_s=5.0,
            limits={"max_chars_max": 200_000, "max_output_bytes": 262144},
            handler=lambda **kw: tool_read_file(root, **kw),
        ),
        "grep": ToolSpec(
            name="grep",
            description="Search for a text pattern in files within workspace.",
            read_only=True,
            risk_class="none",
            timeout_s=10.0,
            limits={"limit_max": 500, "max_files_max": 2000, "max_output_bytes": 262144},
            handler=lambda **kw: tool_grep(root, **kw),
        ),
        "write_file": ToolSpec(
            name="write_file",
            description="Write a UTF-8 text file within workspace. Mutating; disabled by default policy.",
            read_only=False,
            risk_class="low",
            timeout_s=5.0,
            limits={"max_chars_max": 500_000, "max_output_bytes": 65536},
            handler=lambda **kw: tool_write_file(root, **kw),
        ),
        "mkdir": ToolSpec(
            name="mkdir",
            description="Create a directory within workspace. Mutating low-risk; disabled by default policy.",
            read_only=False,
            risk_class="low",
            timeout_s=5.0,
            limits={"max_output_bytes": 65536},
            handler=lambda **kw: tool_mkdir(root, **kw),
        ),
    }


def default_readonly_tools(root: Path) -> dict[str, ToolSpec]:
    # Backward-compatible name; includes mutating tools marked read_only=False.
    return default_tools(root)
