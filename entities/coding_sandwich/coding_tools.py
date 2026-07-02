# Copyright (c) Microsoft. All rights reserved.

"""The "coding engine" slice of the sandwich — a small, *reliable* toolset.

The customer wraps a coding engine (Codex / Cursor) with Agent Framework and
found the tools "somewhat unreliable — it would fail more often than the pure
Codex approach." A big cause of that is brittle tool contracts: vague argument
names, tools that raise raw exceptions (which abort the run), and unbounded
side effects.

These tools take the opposite approach:

* Every argument is typed and described (``Annotated[... , Field(description=...)]``)
  so the model gets a precise schema.
* Every tool returns a **structured string** and never raises — failures come
  back as ``ERROR: ...`` text the model can read and recover from, instead of
  killing the turn.
* All file access is confined to a sandbox workspace (path-traversal is blocked).

Swap these for real Codex/Cursor calls later; the contract stays the same.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

from pydantic import Field


def _workspace_root() -> Path:
    """Resolve (and create) the sandbox workspace directory."""
    root = Path(os.getenv("SANDWICH_WORKSPACE", "./sandbox-workspace")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(relative_path: str) -> Path | None:
    """Resolve ``relative_path`` inside the workspace, or ``None`` if it escapes."""
    root = _workspace_root()
    candidate = (root / relative_path).resolve()
    if root == candidate or root in candidate.parents:
        return candidate
    return None


def list_files(
    subdir: Annotated[
        str, Field(description="Directory to list, relative to the workspace root. Use '.' for the root.")
    ] = ".",
) -> str:
    """List files and folders in the sandbox workspace."""
    target = _safe_path(subdir)
    if target is None:
        return f"ERROR: '{subdir}' is outside the workspace."
    if not target.exists():
        return f"ERROR: '{subdir}' does not exist."
    root = _workspace_root()
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
    if not entries:
        return f"(empty) {subdir}"
    lines = [f"{'FILE' if p.is_file() else 'DIR '}  {p.relative_to(root)}" for p in entries]
    return "\n".join(lines)


def read_file(
    path: Annotated[str, Field(description="File path to read, relative to the workspace root.")],
) -> str:
    """Read a text file from the sandbox workspace."""
    target = _safe_path(path)
    if target is None:
        return f"ERROR: '{path}' is outside the workspace."
    if not target.is_file():
        return f"ERROR: '{path}' is not a file."
    try:
        return target.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - surface as tool text, never abort
        return f"ERROR: could not read '{path}': {exc}"


def write_file(
    path: Annotated[str, Field(description="File path to write, relative to the workspace root.")],
    content: Annotated[str, Field(description="Full text content to write to the file.")],
) -> str:
    """Create or overwrite a text file in the sandbox workspace."""
    target = _safe_path(path)
    if target is None:
        return f"ERROR: '{path}' is outside the workspace."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} chars to '{path}'."
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: could not write '{path}': {exc}"


def run_python(
    path: Annotated[str, Field(description="Python file to execute, relative to the workspace root.")],
    timeout_seconds: Annotated[int, Field(description="Max seconds to allow before killing the process.")] = 30,
) -> str:
    """Run a Python file inside the sandbox workspace and capture its output."""
    target = _safe_path(path)
    if target is None:
        return f"ERROR: '{path}' is outside the workspace."
    if not target.is_file():
        return f"ERROR: '{path}' is not a file."
    try:
        proc = subprocess.run(
            [sys.executable, str(target)],
            cwd=str(_workspace_root()),
            capture_output=True,
            text=True,
            timeout=max(1, timeout_seconds),
        )
    except subprocess.TimeoutExpired:
        return f"ERROR: '{path}' timed out after {timeout_seconds}s."
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: could not run '{path}': {exc}"

    parts = [f"exit_code={proc.returncode}"]
    if proc.stdout:
        parts.append(f"stdout:\n{proc.stdout.rstrip()}")
    if proc.stderr:
        parts.append(f"stderr:\n{proc.stderr.rstrip()}")
    return "\n".join(parts)


CODING_TOOLS = [list_files, read_file, write_file, run_python]
