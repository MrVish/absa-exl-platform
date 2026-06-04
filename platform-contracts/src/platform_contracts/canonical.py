"""Canonical JSON encoding for the manifest envelope contract.

The encoding form is fixed: sorted keys, 2-space indent, UTF-8, trailing newline.
Both producers (Pipeline Factory, future Code Intake) and consumers (signer,
verifier) MUST agree byte-for-byte — the signature digest is over the bytes
produced by this function.

Do NOT change the encoding form. Doing so would invalidate every previously
signed manifest. If the form ever genuinely needs to change, version the
envelope contract instead.
"""

from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """JSON-serialise *obj* deterministically.

    Uses sorted keys, 2-space indent, UTF-8 encoding, and a trailing newline.
    """
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
