"""Workspace-level pytest configuration for code-intake tests.

Fixture packages under `tests/fixtures/` contain their own pytest test
files used as *inputs* to the static_python checker. The workspace pytest
must not try to collect those — they have intentional violations (e.g.
broken fixtures) and a sys.path that only resolves inside the checker's
subprocess invocation.
"""

from __future__ import annotations

collect_ignore_glob = ["fixtures/*"]
