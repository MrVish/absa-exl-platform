from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """JSON-serialise *obj* deterministically.

    Uses sorted keys, 2-space indent, UTF-8 encoding, and a trailing newline.
    """
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


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
        # terraform fmt on a file strips the final newline on some versions;
        # normalise to always end with exactly one newline (matching stdin behaviour).
        return result if result.endswith("\n") else result + "\n"
    finally:
        os.unlink(tmp_path)
