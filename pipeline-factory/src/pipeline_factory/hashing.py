from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from typing import Any

from platform_contracts.canonical import canonical_json

__all__ = ["canonical_json", "sha256_of_bytes", "sha256_of_text", "sha256_of_json", "terraform_fmt"]


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_text(text: str) -> str:
    return sha256_of_bytes(text.encode("utf-8"))


def sha256_of_json(obj: Any) -> str:
    return sha256_of_bytes(canonical_json(obj))


def terraform_fmt(text: str) -> str:
    """Run ``terraform fmt`` on *text* and return the formatted output.

    Writes the input to a temporary ``.tf`` file (avoids stdin EOF handling
    differences across terraform versions / platforms — the stdin form
    hangs in some CI environments), invokes ``terraform fmt`` on the file,
    then reads it back. Disables Hashicorp's checkpoint telemetry and
    enforces a 30s timeout as defense-in-depth.

    Requires the ``terraform`` binary on PATH.
    """
    env = {**os.environ, "CHECKPOINT_DISABLE": "1", "TF_IN_AUTOMATION": "1"}
    fd, tmp_path = tempfile.mkstemp(suffix=".tf", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(text)
        subprocess.run(
            ["terraform", "fmt", tmp_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            env=env,
        )
        with open(tmp_path, encoding="utf-8") as fp:
            result = fp.read()
        return result if result.endswith("\n") else result + "\n"
    finally:
        os.unlink(tmp_path)
