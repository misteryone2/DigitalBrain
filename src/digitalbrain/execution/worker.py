"""Subprocess worker for isolated tool execution.

Runs a named default tool in a separate process. Input: JSON on stdin.
Output: JSON on stdout: {"ok": true, "output": {...}} or {"ok": false, "error": "..."}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        workspace = Path(str(payload["workspace"])).resolve()
        tool_name = str(payload["tool_name"])
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object")

        from digitalbrain.execution.tools import default_tools

        tools = default_tools(workspace)
        spec = tools.get(tool_name)
        if spec is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        output = spec.handler(**arguments)
        if not isinstance(output, dict):
            raise TypeError("Tool output must be a dict")
        sys.stdout.write(json.dumps({"ok": True, "output": output}, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())