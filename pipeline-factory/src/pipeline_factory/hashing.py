from __future__ import annotations

import hashlib
import json
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

    Requires the ``terraform`` binary on PATH.
    """
    completed = subprocess.run(
        ["terraform", "fmt", "-"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout
