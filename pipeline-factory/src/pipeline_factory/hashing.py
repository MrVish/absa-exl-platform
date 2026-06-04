from __future__ import annotations

import hashlib
import json
import os
import subprocess
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
    """Run ``terraform fmt -`` on *text* and return the formatted output.

    Requires the ``terraform`` binary on PATH. Disables Hashicorp's checkpoint
    telemetry (which can hang in restricted CI networks) and enforces a 30s
    timeout as a defense-in-depth against future subprocess hangs.
    """
    env = {**os.environ, "CHECKPOINT_DISABLE": "1", "TF_IN_AUTOMATION": "1"}
    completed = subprocess.run(
        ["terraform", "fmt", "-"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env=env,
    )
    return completed.stdout
