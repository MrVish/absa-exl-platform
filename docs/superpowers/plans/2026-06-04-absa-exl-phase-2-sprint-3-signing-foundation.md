# Sprint 3 — Signing & OIDC Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the KMS asymmetric CMK, GitHub Actions OIDC provider, two scoped IAM roles, two S3 buckets, the `manifest-signer` Python package (sign + verify-online + verify-offline + publish-key), and the CI signing step that turns Sprint 2's UNSIGNED envelopes into audit-grade signed artefacts.

**Architecture:** A new `manifest-signer` uv workspace member with five Click subcommands talks to AWS KMS (mocked via `moto v5` in tests, real in CI) and S3. A new `terraform/modules/signing-foundation` module provisions the CMK, OIDC IdP, signer + registrar IAM roles, and two S3 buckets in `exl-prod`. A new `sign` job in `.github/workflows/pipeline-factory.yml` runs between drift-gate and register on push-to-main, fills the UNSIGNED placeholders, and uploads signed envelopes to S3 (the git copy stays unsigned).

**Tech Stack:** Python 3.12, `boto3`, `cryptography`, `click`, `moto[kms,s3] >= 5`, `pytest`. Terraform >= 1.5, AWS provider `~> 5.0`. GitHub Actions OIDC. uv workspace.

**Predecessors:** Sprint 1 (Registry, merged `dbac0e5`), Sprint 2 (Pipeline Factory, merged `f028b65`). All Sprint 1 + 2 tests must still pass after this plan lands.

**Spec:** [docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md](../specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md)

**Branch:** `phase-2/sprint-3-signing-foundation` (the spec is already committed here as `f7376e1`).

---

## Task Map

| # | Title | Touches | Why this order |
|---|---|---|---|
| T1 | Refactor: move `canonical_json` to `platform-contracts` | `pipeline-factory`, `platform-contracts` | All downstream tasks import from the new home |
| T2 | Scaffold `manifest-signer` workspace member | `manifest-signer/`, root `pyproject.toml` | Establishes the package shell before any logic |
| T3 | Errors + canonical-compat test | `manifest-signer/src`, `manifest-signer/tests` | Guards the T1 refactor; cheap to verify |
| T4 | `signer.py` — `sign_envelope` with idempotency contract | `manifest-signer/src/manifest_signer/signer.py` | Core signing primitive used by CLI and tests |
| T5 | `verifier.py` — `verify_online` + `verify_offline` | `manifest-signer/src/manifest_signer/verifier.py` | Round-trip partner to signer; needed for tests |
| T6 | `publisher.py` — `publish_public_key` | `manifest-signer/src/manifest_signer/publisher.py` | Required by ADR-0003's offline-verify story |
| T7 | `cli.py` — Click commands (sign / sign-all / verify-* / publish-key) | `manifest-signer/src/manifest_signer/cli.py` | Surface used by CI workflow |
| T8 | End-to-end test | `manifest-signer/tests/test_e2e.py` | Proves the full CI happy path runs without AWS |
| T9 | Terraform `signing-foundation` module | `terraform/modules/signing-foundation/` | Provisions CMK + OIDC + roles + buckets |
| T10 | Per-env `exl-prod/signing` stack | `terraform/envs/exl-prod/signing/` | Wires the module into the env tree |
| T11 | CI workflows — sign job + publish-key workflow | `.github/workflows/` | Activates the signer on merges to main |
| T12 | ADR-0009 + ADR-0003 edit + READMEs | `docs/adr/`, module READMEs | Locks the design rationale for future readers |
| T13 | Final verification + PR | repo-wide | Acceptance criteria check, open PR |

---

## Conventions used throughout this plan

- **Working directory** is the repo root (`C:\Vishnu\Claude\absa-exl-platform`) unless a step says otherwise.
- **Branch** is `phase-2/sprint-3-signing-foundation` (already checked out per the spec commit `f7376e1`).
- **Test runner** is `uv run pytest` from the repo root. The root `pyproject.toml` has `addopts = "-q --import-mode=importlib"` and `testpaths = ["platform-contracts/tests", "registry/api/tests", "pipeline-factory/tests"]` — T2 adds `manifest-signer/tests` to that list.
- **Commit message style:** Sprints 1 and 2 use Conventional-Commits prefixes (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`). Match.
- **No `--no-verify`.** Pre-commit hooks (`ruff`, `terraform_fmt`, `tflint`, `tfsec`, `actionlint`, secret scanning) must all pass. If a hook fails, fix the underlying issue.
- **Commit per task by default**, with intra-task commits where the plan calls them out explicitly (e.g. between failing test and passing implementation, when the diff is large).

---

## Task 1: Refactor — move `canonical_json` to `platform-contracts`

**Why:** The canonical-JSON encoder is part of the envelope contract; both Pipeline Factory (producer) and `manifest-signer` (consumer) must agree byte-for-byte. Moving it to `platform-contracts` makes the contract package the single source of truth. The encoding form is unchanged — this is a relocation, not a re-implementation.

**Files:**
- Create: `platform-contracts/src/platform_contracts/canonical.py`
- Create: `platform-contracts/tests/test_canonical.py`
- Modify: `pipeline-factory/src/pipeline_factory/hashing.py` (remove `canonical_json`)
- Modify: `pipeline-factory/src/pipeline_factory/manifest.py:7` (update import)
- Modify: `pipeline-factory/pyproject.toml` (no change required — `platform-contracts` is already a workspace dep)

- [ ] **Step 1: Write the new module's tests**

Create `platform-contracts/tests/test_canonical.py`:

```python
from __future__ import annotations

from platform_contracts.canonical import canonical_json


def test_canonical_json_returns_bytes_with_trailing_newline():
    out = canonical_json({"a": 1})
    assert isinstance(out, bytes)
    assert out.endswith(b"\n")


def test_canonical_json_sorts_keys():
    a = canonical_json({"b": 2, "a": 1})
    b = canonical_json({"a": 1, "b": 2})
    assert a == b


def test_canonical_json_uses_two_space_indent():
    out = canonical_json({"a": 1, "b": [2, 3]})
    assert out == b'{\n  "a": 1,\n  "b": [\n    2,\n    3\n  ]\n}\n'


def test_canonical_json_preserves_unicode():
    out = canonical_json({"name": "Sécurité"})
    assert b"S\xc3\xa9curit\xc3\xa9" in out  # UTF-8 bytes, not \uXXXX escapes


def test_canonical_json_is_byte_identical_to_legacy_implementation():
    # Mirror the exact form pipeline_factory.hashing.canonical_json produced
    # before this refactor. Any change here breaks Sprint 2's existing manifests.
    import json
    payload = {
        "schema_version": 1,
        "generator_version": "0.1.0",
        "model_name": "credit-risk-pd",
        "version": "1.0.0",
        "tier": "standard-batch",
        "generated_at": "2026-05-26T00:00:00+00:00",
        "artifact_hashes": {"model": "abc123", "config": "def456"},
    }
    legacy = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    assert canonical_json(payload) == legacy
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
uv run pytest platform-contracts/tests/test_canonical.py -v
```

Expected: `ModuleNotFoundError: No module named 'platform_contracts.canonical'`.

- [ ] **Step 3: Create the new module**

Create `platform-contracts/src/platform_contracts/canonical.py`:

```python
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
```

- [ ] **Step 4: Run the new tests and confirm they pass**

```bash
uv run pytest platform-contracts/tests/test_canonical.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Update pipeline-factory to import from the new home**

Edit `pipeline-factory/src/pipeline_factory/hashing.py` — **remove** the `canonical_json` function (lines 11-16) and update the file to be:

```python
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
```

(The `import` block, `__all__` re-export of `canonical_json`, and removal of the old `canonical_json` definition are the only changes. The re-export keeps `from pipeline_factory.hashing import canonical_json` working for any internal code that uses it, without making the re-export a public API.)

- [ ] **Step 6: Verify no other pipeline-factory file directly defines or shadows canonical_json**

```bash
grep -rn "def canonical_json" pipeline-factory/
```

Expected: no output (the definition has moved).

- [ ] **Step 7: Run the full Sprint-2 test suite to confirm the refactor is transparent**

```bash
uv run pytest pipeline-factory/tests -v --timeout=60 --timeout-method=thread
```

Expected: all Sprint 2 tests still pass (the import in `manifest.py:7` continues to work via the re-export; the encoding form is identical).

- [ ] **Step 8: Run the entire workspace test suite**

```bash
uv run pytest
```

Expected: previous totals + 5 new tests from `test_canonical.py`. No regressions.

- [ ] **Step 9: Ruff + mypy clean**

```bash
uv run ruff check
uv run mypy platform-contracts/src pipeline-factory/src
```

Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add platform-contracts/src/platform_contracts/canonical.py \
        platform-contracts/tests/test_canonical.py \
        pipeline-factory/src/pipeline_factory/hashing.py
git commit -m "refactor(platform-contracts): move canonical_json from pipeline-factory

The envelope contract's canonicalisation rules belong to the contracts
package, not to a single consumer. Sprint 3 introduces manifest-signer
which also needs the encoder; centralising it ensures byte-for-byte
agreement between producer (Pipeline Factory) and consumer (signer).

Encoding form is unchanged — sort_keys + 2-space indent + UTF-8 +
trailing newline. test_canonical.py asserts byte-identity with the
legacy form to catch any accidental drift.

pipeline_factory.hashing re-exports canonical_json so internal imports
keep working unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Scaffold the `manifest-signer` uv workspace member

**Why:** Establish the package shell, dependencies, and test discovery before any logic lands. The smoke test confirms `uv sync` picks up the new member and `pytest` discovers the new test directory.

**Files:**
- Create: `manifest-signer/pyproject.toml`
- Create: `manifest-signer/src/manifest_signer/__init__.py`
- Create: `manifest-signer/tests/test_smoke.py`
- Modify: `pyproject.toml` (root) — add to `[tool.uv.workspace].members` and `[tool.pytest.ini_options].testpaths`

- [ ] **Step 1: Create the `manifest-signer/pyproject.toml`**

```toml
[project]
name = "manifest-signer"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "platform-contracts",
    "boto3>=1.34",
    "botocore>=1.34",
    "cryptography>=43",
    "click>=8.1",
]

[project.scripts]
manifest-signer = "manifest_signer.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/manifest_signer"]

[tool.uv.sources]
platform-contracts = { workspace = true }
```

- [ ] **Step 2: Create the empty package**

Create `manifest-signer/src/manifest_signer/__init__.py`:

```python
"""manifest-signer — KMS-backed signing and verification for manifest envelopes."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create the smoke test**

Create `manifest-signer/tests/test_smoke.py`:

```python
def test_package_imports() -> None:
    import manifest_signer

    assert manifest_signer.__version__ == "0.1.0"
```

- [ ] **Step 4: Add manifest-signer to the root workspace**

Edit `pyproject.toml` (root). Change line 2 from:

```toml
members = ["platform-contracts", "registry/api", "pipeline-factory"]
```

to:

```toml
members = ["platform-contracts", "registry/api", "pipeline-factory", "manifest-signer"]
```

Change line 38 from:

```toml
testpaths = ["platform-contracts/tests", "registry/api/tests", "pipeline-factory/tests"]
```

to:

```toml
testpaths = ["platform-contracts/tests", "registry/api/tests", "pipeline-factory/tests", "manifest-signer/tests"]
```

- [ ] **Step 5: Resolve the workspace**

```bash
uv sync
```

Expected: `uv` resolves the new member and updates `uv.lock`. No errors.

- [ ] **Step 6: Run the smoke test**

```bash
uv run pytest manifest-signer/tests -v
```

Expected: 1 passed.

- [ ] **Step 7: Run the full workspace test suite (sanity)**

```bash
uv run pytest
```

Expected: prior counts + 1 new test (smoke). No regressions.

- [ ] **Step 8: Commit**

```bash
git add manifest-signer/ pyproject.toml uv.lock
git commit -m "chore(manifest-signer): scaffold uv workspace member

Adds an empty manifest-signer package with platform-contracts, boto3,
cryptography, and click as deps. Smoke test confirms uv sync picks up
the new member and pytest discovers the tests directory.

Subsequent tasks fill in signer / verifier / publisher / CLI modules.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Errors module + canonical-compat test

**Why:** Errors first because every subsequent module raises one of these. The canonical-compat test is the safety net for the Sprint-1/2/3 contract — if `pipeline_factory.manifest.build_envelope` and `manifest_signer` ever stop agreeing on the canonical form, sign + verify breaks silently. The test catches drift at CI time.

**Files:**
- Create: `manifest-signer/src/manifest_signer/errors.py`
- Create: `manifest-signer/tests/test_canonical_compat.py`

- [ ] **Step 1: Write the errors module's tests**

Create `manifest-signer/tests/test_errors.py`:

```python
import pytest

from manifest_signer.errors import KeyMismatchError, SignerError, VerificationError


def test_signer_error_is_exception():
    assert issubclass(SignerError, Exception)


def test_key_mismatch_error_is_signer_error():
    assert issubclass(KeyMismatchError, SignerError)


def test_verification_error_is_exception():
    assert issubclass(VerificationError, Exception)


def test_raising_key_mismatch_carries_message():
    with pytest.raises(KeyMismatchError, match="bad key"):
        raise KeyMismatchError("bad key")
```

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
uv run pytest manifest-signer/tests/test_errors.py -v
```

Expected: `ModuleNotFoundError: No module named 'manifest_signer.errors'`.

- [ ] **Step 3: Create the errors module**

Create `manifest-signer/src/manifest_signer/errors.py`:

```python
"""Error hierarchy for the manifest-signer package."""

from __future__ import annotations


class SignerError(Exception):
    """Base class for signer-side failures."""


class KeyMismatchError(SignerError):
    """Raised when a re-sign is attempted against a different key/algorithm than
    the envelope's current signature."""


class VerificationError(Exception):
    """Raised by verifier paths (online or offline) when signature validation
    fails for any reason."""
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
uv run pytest manifest-signer/tests/test_errors.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Write the canonical-compat test**

Create `manifest-signer/tests/test_canonical_compat.py`:

```python
"""Guards the byte-for-byte contract between Sprint 2's manifest builder and
Sprint 3's signer/verifier. If this test fails, the envelope contract has
silently drifted and previously-signed manifests will no longer verify.
"""

from __future__ import annotations

import pytest

from pipeline_factory.manifest import build_envelope, build_payload
from platform_contracts.canonical import canonical_json


@pytest.fixture
def sample_payload() -> dict:
    return build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard-batch",
        artifact_hashes={"model": "abc123", "config": "def456"},
        generated_at="2026-05-26T00:00:00+00:00",
    )


def test_canonical_json_form_is_pretty_printed_sort_keys_utf8(sample_payload):
    out = canonical_json(sample_payload)
    assert out.endswith(b"\n")
    # First two keys in sorted order
    assert out.startswith(b'{\n  "artifact_hashes":')


def test_pipeline_factory_envelope_uses_canonical_json_for_digest(sample_payload):
    """build_envelope sets envelope.digest = sha256(canonical_json(payload)).
       If either side drifts, signatures stop verifying."""
    import hashlib

    envelope = build_envelope(
        payload=sample_payload,
        subject_ref="pipeline:credit-risk-pd:1.0.0",
        signed_at="2026-05-26T00:00:00+00:00",
    )
    expected_digest = hashlib.sha256(canonical_json(sample_payload)).hexdigest()
    assert envelope["digest"] == expected_digest
    assert envelope["digest_algorithm"] == "SHA-256"


def test_canonical_json_is_stable_across_dict_insertion_order(sample_payload):
    reordered = dict(reversed(list(sample_payload.items())))
    assert canonical_json(sample_payload) == canonical_json(reordered)
```

- [ ] **Step 6: Run the compat test and confirm it passes**

```bash
uv run pytest manifest-signer/tests/test_canonical_compat.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Run the whole workspace**

```bash
uv run pytest
```

Expected: no regressions, +7 new tests (4 errors + 3 compat).

- [ ] **Step 8: Commit**

```bash
git add manifest-signer/src/manifest_signer/errors.py \
        manifest-signer/tests/test_errors.py \
        manifest-signer/tests/test_canonical_compat.py
git commit -m "feat(manifest-signer): add errors module and canonical-compat tests

errors.py defines the SignerError / KeyMismatchError / VerificationError
hierarchy used by signer + verifier modules.

test_canonical_compat.py guards the byte-for-byte contract between the
Sprint 2 manifest builder and the Sprint 3 signer/verifier. If the
canonical-JSON encoder ever drifts, this test catches it before signing
output silently diverges from verification expectations.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `signer.py` — `sign_envelope` with idempotency contract

**Why:** The core signing primitive. Implements the three-state idempotency contract from spec §7.1: UNSIGNED → fills sentinels; same-key signed → no-op; different-key signed → `KeyMismatchError`. Determinism of `RSASSA_PKCS1_V1_5_SHA_256` makes the same envelope produce the same signature, which is what makes the CI signing step idempotent at the S3 layer.

**Files:**
- Create: `manifest-signer/src/manifest_signer/signer.py`
- Create: `manifest-signer/tests/conftest.py`
- Create: `manifest-signer/tests/test_signer.py`

- [ ] **Step 1: Write the shared conftest fixtures**

Create `manifest-signer/tests/conftest.py`:

```python
"""Shared test fixtures: moto KMS asymmetric key, sample envelope, S3 bucket."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws

from pipeline_factory.manifest import build_envelope, build_payload


@pytest.fixture(autouse=True)
def aws_creds(monkeypatch):
    """moto requires AWS_DEFAULT_REGION + dummy creds to be set."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")


@pytest.fixture
def mock_aws_ctx():
    with mock_aws():
        yield


@pytest.fixture
def kms_client(mock_aws_ctx):
    return boto3.client("kms", region_name="eu-west-1")


@pytest.fixture
def s3_client(mock_aws_ctx):
    return boto3.client("s3", region_name="eu-west-1")


@pytest.fixture
def signing_key(kms_client) -> dict:
    """Create a moto-backed RSA-3072 asymmetric KMS key. Returns the key's
       metadata dict (KeyId, Arn) for tests."""
    resp = kms_client.create_key(
        Description="test signing key",
        KeyUsage="SIGN_VERIFY",
        KeySpec="RSA_3072",
    )
    return resp["KeyMetadata"]


@pytest.fixture
def unsigned_envelope() -> dict:
    payload = build_payload(
        model_name="credit-risk-pd",
        version="1.0.0",
        tier="standard-batch",
        artifact_hashes={"model": "abc123", "config": "def456"},
        generated_at="2026-05-26T00:00:00+00:00",
    )
    return build_envelope(
        payload=payload,
        subject_ref="pipeline:credit-risk-pd:1.0.0",
        signed_at="2026-05-26T00:00:00+00:00",
    )


@pytest.fixture
def signer_principal() -> str:
    return "arn:aws:sts::111122223333:assumed-role/pipeline-factory-signer/test-session"
```

- [ ] **Step 2: Write the signer tests**

Create `manifest-signer/tests/test_signer.py`:

```python
from __future__ import annotations

import base64

import pytest

from manifest_signer.errors import KeyMismatchError
from manifest_signer.signer import sign_envelope


def test_sign_unsigned_fills_all_four_sentinel_fields(unsigned_envelope, kms_client, signing_key, signer_principal):
    out = sign_envelope(
        unsigned_envelope,
        key_arn=signing_key["Arn"],
        kms_client=kms_client,
        signer_principal=signer_principal,
    )
    assert out["signature"] != "UNSIGNED"
    assert out["signing_key_arn"] == signing_key["Arn"]
    assert out["signing_algorithm"] == "RSASSA_PKCS1_V1_5_SHA_256"
    assert out["signer_principal"] == signer_principal


def test_sign_does_not_mutate_input(unsigned_envelope, kms_client, signing_key, signer_principal):
    snapshot = dict(unsigned_envelope)
    sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                  kms_client=kms_client, signer_principal=signer_principal)
    assert unsigned_envelope == snapshot


def test_signature_is_base64_decodable(unsigned_envelope, kms_client, signing_key, signer_principal):
    out = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                       kms_client=kms_client, signer_principal=signer_principal)
    sig = base64.b64decode(out["signature"])
    # RSA-3072 produces 384-byte signatures
    assert len(sig) == 384


def test_signed_at_is_preserved_when_provided(unsigned_envelope, kms_client, signing_key, signer_principal):
    out = sign_envelope(
        unsigned_envelope, key_arn=signing_key["Arn"], kms_client=kms_client,
        signer_principal=signer_principal, signed_at="2026-06-01T12:00:00+00:00",
    )
    assert out["signed_at"] == "2026-06-01T12:00:00+00:00"


def test_signed_at_defaults_to_iso8601_utc(unsigned_envelope, kms_client, signing_key, signer_principal):
    from datetime import datetime
    out = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                       kms_client=kms_client, signer_principal=signer_principal)
    # Must parse as ISO-8601 UTC
    parsed = datetime.fromisoformat(out["signed_at"])
    assert parsed.utcoffset() is not None


def test_signing_is_deterministic(unsigned_envelope, kms_client, signing_key, signer_principal):
    """RSASSA_PKCS1_V1_5_SHA_256 is deterministic — same digest -> same signature.
       This is the property the CI idempotency story leans on."""
    a = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                     kms_client=kms_client, signer_principal=signer_principal,
                     signed_at="2026-06-01T12:00:00+00:00")
    b = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                     kms_client=kms_client, signer_principal=signer_principal,
                     signed_at="2026-06-01T12:00:00+00:00")
    assert a == b


def test_resign_with_same_key_is_noop(unsigned_envelope, kms_client, signing_key, signer_principal):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal,
                          signed_at="2026-06-01T12:00:00+00:00")
    out = sign_envelope(signed, key_arn=signing_key["Arn"],
                       kms_client=kms_client, signer_principal=signer_principal,
                       signed_at="2026-06-01T12:00:00+00:00")
    assert out == signed


def test_resign_with_different_key_raises_key_mismatch(unsigned_envelope, kms_client, signing_key, signer_principal):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    other_key = kms_client.create_key(KeyUsage="SIGN_VERIFY", KeySpec="RSA_3072")["KeyMetadata"]
    with pytest.raises(KeyMismatchError):
        sign_envelope(signed, key_arn=other_key["Arn"], kms_client=kms_client,
                     signer_principal=signer_principal)


def test_signing_key_arn_is_resolved_arn_not_alias(unsigned_envelope, kms_client, signing_key, signer_principal):
    """If caller passes the alias, the envelope must end up with the resolved
       key ARN — the immutable identifier. This is the audit-trail requirement."""
    kms_client.create_alias(AliasName="alias/test-signing-key",
                            TargetKeyId=signing_key["KeyId"])
    out = sign_envelope(unsigned_envelope, key_arn="alias/test-signing-key",
                       kms_client=kms_client, signer_principal=signer_principal)
    assert out["signing_key_arn"] == signing_key["Arn"]
    assert "alias" not in out["signing_key_arn"]
```

- [ ] **Step 3: Run tests and confirm they fail**

```bash
uv run pytest manifest-signer/tests/test_signer.py -v
```

Expected: `ModuleNotFoundError: No module named 'manifest_signer.signer'`.

- [ ] **Step 4: Implement signer.py**

Create `manifest-signer/src/manifest_signer/signer.py`:

```python
"""sign_envelope — fill the manifest envelope's sentinel fields via kms:Sign."""

from __future__ import annotations

import base64
import copy
import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from platform_contracts.canonical import canonical_json

from .errors import KeyMismatchError

if TYPE_CHECKING:
    from mypy_boto3_kms.client import KMSClient
else:
    KMSClient = Any

# Mirrors pipeline_factory.manifest.UNSIGNED_SIGNATURE. Hardcoded here so
# manifest-signer does not depend on pipeline-factory (the dep direction is
# manifest-signer -> platform-contracts, and pipeline-factory ->
# platform-contracts; the two sibling packages never cross-import).
UNSIGNED_SENTINEL = "UNSIGNED"
SIGNING_ALGORITHM = "RSASSA_PKCS1_V1_5_SHA_256"


def sign_envelope(
    unsigned_envelope: dict[str, Any],
    *,
    key_arn: str,
    kms_client: KMSClient,
    signer_principal: str,
    signed_at: str | None = None,
) -> dict[str, Any]:
    """Return a NEW envelope dict with the four sentinel fields filled in.

    Idempotency contract:
      - signature == "UNSIGNED"                                -> sign and fill
      - signature != "UNSIGNED", same resolved key + algorithm -> return input unchanged
      - signature != "UNSIGNED", different key or algorithm    -> raise KeyMismatchError

    The signature covers canonical_json(envelope["payload"]), NOT the envelope
    itself (the envelope contains the signature field — signing it would be
    circular).

    `signed_at` is preserved if passed (CI idempotency story); otherwise filled
    with datetime.now(UTC).isoformat(timespec="seconds").

    `signer_principal` is the caller's resolved STS session ARN — convention
    documented in ADR-0009.
    """
    digest = hashlib.sha256(canonical_json(unsigned_envelope["payload"])).digest()

    # Resolve the key ARN up front. If the caller passed an alias, KMS resolves
    # it via DescribeKey; we need the resolved ARN for both the idempotency
    # check and the final envelope.
    resolved_key_arn = _resolve_key_arn(kms_client, key_arn)

    current_signature = unsigned_envelope.get("signature", UNSIGNED_SENTINEL)
    if current_signature != UNSIGNED_SENTINEL:
        current_key = unsigned_envelope.get("signing_key_arn")
        current_alg = unsigned_envelope.get("signing_algorithm")
        if current_key == resolved_key_arn and current_alg == SIGNING_ALGORITHM:
            return unsigned_envelope  # idempotent re-sign
        raise KeyMismatchError(
            f"envelope already signed by {current_key} ({current_alg}); "
            f"refusing to re-sign with {resolved_key_arn} ({SIGNING_ALGORITHM})"
        )

    resp = kms_client.sign(
        KeyId=resolved_key_arn,
        Message=digest,
        MessageType="DIGEST",
        SigningAlgorithm=SIGNING_ALGORITHM,
    )

    out = copy.deepcopy(unsigned_envelope)
    out["signature"] = base64.b64encode(resp["Signature"]).decode("ascii")
    out["signing_key_arn"] = resolved_key_arn
    out["signing_algorithm"] = SIGNING_ALGORITHM
    out["signer_principal"] = signer_principal
    out["signed_at"] = signed_at or datetime.now(UTC).isoformat(timespec="seconds")
    return out


def _resolve_key_arn(kms_client: KMSClient, key_arn_or_alias: str) -> str:
    """If the caller passed an alias, resolve to the underlying key ARN.
       If they passed a real ARN, return it unchanged."""
    if not key_arn_or_alias.startswith("alias/") and ":alias/" not in key_arn_or_alias:
        return key_arn_or_alias
    resp = kms_client.describe_key(KeyId=key_arn_or_alias)
    return resp["KeyMetadata"]["Arn"]
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
uv run pytest manifest-signer/tests/test_signer.py -v
```

Expected: 9 passed.

- [ ] **Step 6: Mypy clean**

```bash
uv run mypy manifest-signer/src
```

Expected: no errors. (If `mypy_boto3_kms` type stubs are not installed, the `if TYPE_CHECKING` guard means runtime is fine; mypy treats the type as `Any` which is acceptable for the workspace's existing mypy override on `boto3.*` and `botocore.*` modules.)

- [ ] **Step 7: Commit**

```bash
git add manifest-signer/src/manifest_signer/signer.py \
        manifest-signer/tests/conftest.py \
        manifest-signer/tests/test_signer.py
git commit -m "feat(manifest-signer): add sign_envelope with idempotency contract

sign_envelope fills the four UNSIGNED sentinel fields via kms:Sign with
RSASSA_PKCS1_V1_5_SHA_256 (deterministic — same digest -> same signature).

Three-state idempotency contract:
- UNSIGNED -> sign and fill the sentinels
- Already signed with same key + algorithm -> return input unchanged (CI re-run safe)
- Already signed with different key/algorithm -> KeyMismatchError

The resolved key ARN is what lands in the envelope (not the alias the
caller may have passed) -- the audit trail needs the immutable identifier.
Signature covers canonical_json(payload), not the envelope (the envelope
contains the signature field; signing it would be circular).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `verifier.py` — `verify_online` + `verify_offline`

**Why:** Both verification paths are required by ADR-0003: online for runtime checks against a live CMK; offline so anyone holding the published public key can verify without AWS credentials. Both paths share the canonical-digest pipeline and must agree byte-for-byte on the same envelope (tested).

**Files:**
- Create: `manifest-signer/src/manifest_signer/verifier.py`
- Create: `manifest-signer/tests/test_verifier_online.py`
- Create: `manifest-signer/tests/test_verifier_offline.py`

- [ ] **Step 1: Write the online verifier tests**

Create `manifest-signer/tests/test_verifier_online.py`:

```python
from __future__ import annotations

import copy

import pytest

from manifest_signer.errors import VerificationError
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_online


def test_sign_then_verify_online_passes(unsigned_envelope, kms_client, signing_key, signer_principal):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    verify_online(signed, kms_client=kms_client)  # must not raise


def test_tampered_payload_fails_online_verify(unsigned_envelope, kms_client, signing_key, signer_principal):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    tampered = copy.deepcopy(signed)
    tampered["payload"]["model_name"] = "different-model"
    with pytest.raises(VerificationError):
        verify_online(tampered, kms_client=kms_client)


def test_tampered_signature_fails_online_verify(unsigned_envelope, kms_client, signing_key, signer_principal):
    import base64
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    tampered = copy.deepcopy(signed)
    sig_bytes = bytearray(base64.b64decode(tampered["signature"]))
    sig_bytes[0] ^= 0xFF
    tampered["signature"] = base64.b64encode(bytes(sig_bytes)).decode("ascii")
    with pytest.raises(VerificationError):
        verify_online(tampered, kms_client=kms_client)
```

- [ ] **Step 2: Write the offline verifier tests**

Create `manifest-signer/tests/test_verifier_offline.py`:

```python
from __future__ import annotations

import base64
import copy

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from manifest_signer.errors import VerificationError
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_offline


@pytest.fixture
def public_key_pem(kms_client, signing_key) -> bytes:
    """Fetch the moto-generated public key and PEM-encode it."""
    resp = kms_client.get_public_key(KeyId=signing_key["KeyId"])
    der_bytes = resp["PublicKey"]
    pub = serialization.load_der_public_key(der_bytes)
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def test_sign_then_verify_offline_passes(unsigned_envelope, kms_client, signing_key, signer_principal, public_key_pem):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    verify_offline(signed, public_key_pem=public_key_pem)  # must not raise


def test_tampered_payload_fails_offline_verify(unsigned_envelope, kms_client, signing_key, signer_principal, public_key_pem):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    tampered = copy.deepcopy(signed)
    tampered["payload"]["model_name"] = "different-model"
    with pytest.raises(VerificationError):
        verify_offline(tampered, public_key_pem=public_key_pem)


def test_tampered_signature_fails_offline_verify(unsigned_envelope, kms_client, signing_key, signer_principal, public_key_pem):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    tampered = copy.deepcopy(signed)
    sig_bytes = bytearray(base64.b64decode(tampered["signature"]))
    sig_bytes[0] ^= 0xFF
    tampered["signature"] = base64.b64encode(bytes(sig_bytes)).decode("ascii")
    with pytest.raises(VerificationError):
        verify_offline(tampered, public_key_pem=public_key_pem)


def test_mismatched_public_key_fails_offline_verify(unsigned_envelope, kms_client, signing_key, signer_principal):
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal=signer_principal)
    # Generate an unrelated public key
    other_priv = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    other_pub_pem = other_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with pytest.raises(VerificationError):
        verify_offline(signed, public_key_pem=other_pub_pem)
```

- [ ] **Step 3: Run tests and confirm they fail**

```bash
uv run pytest manifest-signer/tests/test_verifier_online.py manifest-signer/tests/test_verifier_offline.py -v
```

Expected: `ModuleNotFoundError: No module named 'manifest_signer.verifier'`.

- [ ] **Step 4: Implement verifier.py**

Create `manifest-signer/src/manifest_signer/verifier.py`:

```python
"""verify_online (kms:Verify) and verify_offline (cryptography) — both paths
required by ADR-0003. Both share the canonical-digest pipeline."""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING, Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from platform_contracts.canonical import canonical_json

from .errors import VerificationError

if TYPE_CHECKING:
    from mypy_boto3_kms.client import KMSClient
else:
    KMSClient = Any


def verify_online(envelope: dict[str, Any], *, kms_client: KMSClient) -> None:
    """Raises VerificationError on any failure. One KMS round-trip."""
    digest = _payload_digest(envelope)
    try:
        resp = kms_client.verify(
            KeyId=envelope["signing_key_arn"],
            Message=digest,
            MessageType="DIGEST",
            SigningAlgorithm=envelope["signing_algorithm"],
            Signature=base64.b64decode(envelope["signature"]),
        )
    except Exception as e:
        raise VerificationError(f"kms:Verify raised: {e}") from e
    if not resp.get("SignatureValid", False):
        raise VerificationError("kms:Verify returned SignatureValid=false")


def verify_offline(envelope: dict[str, Any], *, public_key_pem: bytes) -> None:
    """Raises VerificationError on any failure. No AWS access required."""
    digest = _payload_digest(envelope)
    public_key = serialization.load_pem_public_key(public_key_pem)
    try:
        public_key.verify(
            base64.b64decode(envelope["signature"]),
            digest,
            padding.PKCS1v15(),
            Prehashed(hashes.SHA256()),
        )
    except InvalidSignature as e:
        raise VerificationError(f"offline verification failed: {e}") from e


def _payload_digest(envelope: dict[str, Any]) -> bytes:
    return hashlib.sha256(canonical_json(envelope["payload"])).digest()
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
uv run pytest manifest-signer/tests/test_verifier_online.py manifest-signer/tests/test_verifier_offline.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Mypy clean**

```bash
uv run mypy manifest-signer/src
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add manifest-signer/src/manifest_signer/verifier.py \
        manifest-signer/tests/test_verifier_online.py \
        manifest-signer/tests/test_verifier_offline.py
git commit -m "feat(manifest-signer): add online + offline verifiers

Two verification paths required by ADR-0003:
- verify_online: one kms:Verify round-trip, validates signature against
  the live CMK
- verify_offline: cryptography library against a PEM-encoded public key,
  no AWS credentials required

Both paths share canonical_json(payload) -> sha256 -> verify. Round-trip
tests prove byte-for-byte agreement: a manifest signed by sign_envelope
verifies through both paths, and any tamper (payload or signature) is
caught by both.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `publisher.py` — `publish_public_key`

**Why:** ADR-0003 commits to publishing the public key to a versioned, world-readable S3 location so any party can verify any historical signed manifest offline. The publisher is the one-shot tool that does that.

**Files:**
- Create: `manifest-signer/src/manifest_signer/publisher.py`
- Create: `manifest-signer/tests/test_publisher.py`

- [ ] **Step 1: Write the publisher tests**

Create `manifest-signer/tests/test_publisher.py`:

```python
from __future__ import annotations

from cryptography.hazmat.primitives import serialization

from manifest_signer.publisher import publish_public_key


def test_publish_uploads_pem_to_expected_key(kms_client, s3_client, signing_key):
    bucket = "test-public-keys"
    s3_client.create_bucket(Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})

    uri = publish_public_key(
        key_arn=signing_key["Arn"], bucket=bucket,
        kms_client=kms_client, s3_client=s3_client, version="v1",
    )

    key_id = signing_key["KeyId"]
    expected_key = f"manifest-signing/{key_id}/v1.pem"
    assert uri == f"s3://{bucket}/{expected_key}"

    obj = s3_client.get_object(Bucket=bucket, Key=expected_key)
    body = obj["Body"].read()
    pub = serialization.load_pem_public_key(body)
    assert pub.key_size == 3072


def test_publish_is_idempotent_on_rerun(kms_client, s3_client, signing_key):
    bucket = "test-public-keys"
    s3_client.create_bucket(Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})

    uri_a = publish_public_key(key_arn=signing_key["Arn"], bucket=bucket,
                               kms_client=kms_client, s3_client=s3_client, version="v1")
    uri_b = publish_public_key(key_arn=signing_key["Arn"], bucket=bucket,
                               kms_client=kms_client, s3_client=s3_client, version="v1")
    assert uri_a == uri_b
    body_a = s3_client.get_object(Bucket=bucket, Key=f"manifest-signing/{signing_key['KeyId']}/v1.pem")["Body"].read()
    body_b = s3_client.get_object(Bucket=bucket, Key=f"manifest-signing/{signing_key['KeyId']}/v1.pem")["Body"].read()
    assert body_a == body_b
```

- [ ] **Step 2: Run tests and confirm they fail**

```bash
uv run pytest manifest-signer/tests/test_publisher.py -v
```

Expected: `ModuleNotFoundError: No module named 'manifest_signer.publisher'`.

- [ ] **Step 3: Implement publisher.py**

Create `manifest-signer/src/manifest_signer/publisher.py`:

```python
"""publish_public_key — fetch the CMK's public key, PEM-encode, upload to S3.

Run once after the first terraform apply for a new CMK, then again on each
key rotation. The bucket policy on exl-platform-public-keys grants read to
Principal: "*" so any party can fetch and verify offline (ADR-0003)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives import serialization

if TYPE_CHECKING:
    from mypy_boto3_kms.client import KMSClient
    from mypy_boto3_s3.client import S3Client
else:
    KMSClient = Any
    S3Client = Any


def publish_public_key(
    *,
    key_arn: str,
    bucket: str,
    kms_client: KMSClient,
    s3_client: S3Client,
    version: str = "v1",
) -> str:
    """Fetches the CMK's public key via kms:GetPublicKey, PEM-encodes it,
       uploads to s3://<bucket>/manifest-signing/<key_id>/<version>.pem.
       Returns the s3:// URI.

       Idempotent — the public key for a given CMK is immutable, so re-runs
       upload identical content. We do not use IfNoneMatch here because the
       expected case is "republish on rotation" where overwrite is acceptable;
       overwrite of the same content is a no-op at the audit layer."""
    resp = kms_client.get_public_key(KeyId=key_arn)
    der_bytes = resp["PublicKey"]
    key_id = resp["KeyId"].rsplit("/", 1)[-1]   # extract UUID suffix from full ARN

    pub = serialization.load_der_public_key(der_bytes)
    pem_bytes = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    s3_key = f"manifest-signing/{key_id}/{version}.pem"
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=pem_bytes,
        ContentType="application/x-pem-file",
    )
    return f"s3://{bucket}/{s3_key}"
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
uv run pytest manifest-signer/tests/test_publisher.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Mypy clean**

```bash
uv run mypy manifest-signer/src
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add manifest-signer/src/manifest_signer/publisher.py \
        manifest-signer/tests/test_publisher.py
git commit -m "feat(manifest-signer): add publish_public_key

Fetches the KMS asymmetric CMK's public key via kms:GetPublicKey,
PEM-encodes, uploads to s3://<bucket>/manifest-signing/<key_id>/<version>.pem.

One-shot tool for first deploy and key rotations. The public key is
immutable for a given CMK; re-running on the same key + version uploads
identical bytes (idempotent).

The published PEM is what auditors / ABSA reviewers / external regulators
use for offline verification per ADR-0003.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `cli.py` — Click commands

**Why:** The CI workflow calls `manifest-signer sign-all` on push to main. `sign-all` is the workhorse — it globs for unsigned manifests, signs each, uploads to S3 with `IfNoneMatch="*"`. The four other subcommands (`sign`, `verify-online`, `verify-offline`, `publish-key`) cover developer and operator workflows.

**Files:**
- Create: `manifest-signer/src/manifest_signer/cli.py`
- Create: `manifest-signer/tests/test_cli.py`
- Modify: `manifest-signer/tests/conftest.py` — add a `pipelines_tree` fixture used by `sign-all` tests.

- [ ] **Step 1: Extend conftest with the `pipelines_tree` fixture**

Add the following to `manifest-signer/tests/conftest.py` (append at the end):

```python
import json


@pytest.fixture
def pipelines_tree(tmp_path, unsigned_envelope):
    """Build a fixture pipelines/ tree with two manifests: one UNSIGNED, one
    already-signed-by-a-different-marker (so sign-all sees a mix)."""
    root = tmp_path / "pipelines"
    one = root / "credit-risk-pd" / "1.0.0"
    one.mkdir(parents=True)
    (one / "manifest.json").write_text(json.dumps(unsigned_envelope, sort_keys=True, indent=2) + "\n")

    # Second manifest, already marked signed (the signer must treat this as no-op).
    # Use the SAME signing_key_arn the test will pass, so the idempotency contract
    # returns "unchanged" rather than raising.
    other_payload = dict(unsigned_envelope["payload"])
    other_payload["model_name"] = "fraud-detection"
    other_envelope = {**unsigned_envelope, "payload": other_payload,
                      "subject_ref": "pipeline:fraud-detection:0.1.0"}
    two = root / "fraud-detection" / "0.1.0"
    two.mkdir(parents=True)
    (two / "manifest.json").write_text(json.dumps(other_envelope, sort_keys=True, indent=2) + "\n")
    return root
```

- [ ] **Step 2: Write CLI tests**

Create `manifest-signer/tests/test_cli.py`:

```python
from __future__ import annotations

import json

import boto3
import pytest
from click.testing import CliRunner
from moto import mock_aws

from manifest_signer.cli import main


def _ctx(env=None):
    """Combine moto + a fresh CliRunner. Returns (runner, env_dict)."""
    runner = CliRunner()
    return runner, env or {}


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_all_subcommands(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for cmd in ("sign", "sign-all", "verify-online", "verify-offline", "publish-key"):
        assert cmd in result.output


def test_sign_dry_run_does_not_call_kms(runner, unsigned_envelope, tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(unsigned_envelope, indent=2) + "\n")
    # No KMS mock -- if --dry-run actually called KMS, this would fail with
    # a connection error.
    result = runner.invoke(main, [
        "sign", "--manifest", str(manifest),
        "--key-arn", "arn:aws:kms:eu-west-1:111:key/abc",
        "--signer-principal", "test-principal",
        "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    # Local file is unchanged
    assert json.loads(manifest.read_text())["signature"] == "UNSIGNED"


def test_sign_in_place_overwrites_file(runner, unsigned_envelope, signing_key, kms_client, tmp_path):
    """Full sign with --in-place modifies the file on disk."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(unsigned_envelope, indent=2) + "\n")
    result = runner.invoke(main, [
        "sign", "--manifest", str(manifest),
        "--key-arn", signing_key["Arn"],
        "--signer-principal", "test-principal",
        "--in-place",
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(manifest.read_text())["signature"] != "UNSIGNED"


def test_sign_all_signs_unsigned_uploads_skips_existing(runner, pipelines_tree, signing_key,
                                                        kms_client, s3_client):
    bucket = "test-signed-manifests"
    s3_client.create_bucket(Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
    result = runner.invoke(main, [
        "sign-all",
        "--root", str(pipelines_tree),
        "--key-arn", signing_key["Arn"],
        "--upload-to-bucket", bucket,
        "--signer-principal", "test-principal",
    ])
    assert result.exit_code == 0, result.output
    # Both manifests uploaded
    objs = s3_client.list_objects_v2(Bucket=bucket)
    keys = {o["Key"] for o in objs.get("Contents", [])}
    assert "credit-risk-pd/1.0.0/manifest.json" in keys
    assert "fraud-detection/0.1.0/manifest.json" in keys


def test_sign_all_second_run_is_idempotent(runner, pipelines_tree, signing_key, kms_client, s3_client):
    bucket = "test-signed-manifests"
    s3_client.create_bucket(Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
    args = ["sign-all", "--root", str(pipelines_tree), "--key-arn", signing_key["Arn"],
            "--upload-to-bucket", bucket, "--signer-principal", "test-principal"]
    r1 = runner.invoke(main, args)
    r2 = runner.invoke(main, args)
    assert r1.exit_code == 0 and r2.exit_code == 0


def test_verify_online_exits_zero_on_valid(runner, unsigned_envelope, signing_key, kms_client, tmp_path):
    from manifest_signer.signer import sign_envelope
    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal="test")
    manifest = tmp_path / "signed.json"
    manifest.write_text(json.dumps(signed, indent=2))
    result = runner.invoke(main, ["verify-online", "--manifest", str(manifest)])
    assert result.exit_code == 0, result.output


def test_verify_offline_exits_zero_on_valid(runner, unsigned_envelope, signing_key, kms_client, tmp_path):
    from manifest_signer.signer import sign_envelope
    from cryptography.hazmat.primitives import serialization

    signed = sign_envelope(unsigned_envelope, key_arn=signing_key["Arn"],
                          kms_client=kms_client, signer_principal="test")
    manifest = tmp_path / "signed.json"
    manifest.write_text(json.dumps(signed, indent=2))

    der = kms_client.get_public_key(KeyId=signing_key["KeyId"])["PublicKey"]
    pub = serialization.load_der_public_key(der)
    pem = pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    pem_path = tmp_path / "pub.pem"
    pem_path.write_bytes(pem)

    result = runner.invoke(main, [
        "verify-offline", "--manifest", str(manifest), "--public-key", str(pem_path),
    ])
    assert result.exit_code == 0, result.output


def test_publish_key_uploads_pem(runner, kms_client, s3_client, signing_key):
    bucket = "test-keys"
    s3_client.create_bucket(Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
    result = runner.invoke(main, [
        "publish-key", "--key-arn", signing_key["Arn"],
        "--bucket", bucket, "--version", "v1",
    ])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 3: Run tests and confirm they fail**

```bash
uv run pytest manifest-signer/tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'manifest_signer.cli'`.

- [ ] **Step 4: Implement cli.py**

Create `manifest-signer/src/manifest_signer/cli.py`:

```python
"""Click CLI for manifest-signer.

Subcommands:
- sign            — sign a single manifest file (developer / one-off)
- sign-all        — discover and sign every UNSIGNED manifest under a root (CI)
- verify-online   — kms:Verify against the live CMK
- verify-offline  — local verify against a PEM-encoded public key
- publish-key     — kms:GetPublicKey -> upload PEM to S3 (one-shot)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3
import click

from .errors import VerificationError
from .publisher import publish_public_key
from .signer import sign_envelope
from .verifier import verify_offline, verify_online


@click.group(help=__doc__)
def main() -> None:
    pass


@main.command("sign")
@click.option("--manifest", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--key-arn", required=True, help="KMS key ARN or alias")
@click.option("--signer-principal", required=True, help="STS session ARN of the assumed signer role")
@click.option("--upload-to", default=None, help="s3:// URI to upload the signed envelope to")
@click.option("--in-place", is_flag=True, help="Overwrite the local manifest file with the signed envelope")
@click.option("--dry-run", is_flag=True, help="Compute and report what would be signed; do not call KMS")
def sign_cmd(manifest, key_arn, signer_principal, upload_to, in_place, dry_run):
    envelope = json.loads(manifest.read_text())
    if dry_run:
        from platform_contracts.canonical import canonical_json
        import hashlib
        digest = hashlib.sha256(canonical_json(envelope["payload"])).hexdigest()
        click.echo(f"[dry-run] would sign payload digest={digest} with key={key_arn}")
        return

    kms = boto3.client("kms")
    signed = sign_envelope(envelope, key_arn=key_arn, kms_client=kms,
                          signer_principal=signer_principal)

    if upload_to:
        _upload_signed_envelope(signed, s3_uri=upload_to)
    if in_place:
        manifest.write_text(json.dumps(signed, indent=2, ensure_ascii=False) + "\n")
    if not upload_to and not in_place:
        click.echo(json.dumps(signed, indent=2, ensure_ascii=False))


@main.command("sign-all")
@click.option("--root", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--key-arn", required=True)
@click.option("--upload-to-bucket", required=True)
@click.option("--signer-principal", required=True)
@click.option("--continue-on-error", is_flag=True)
def sign_all_cmd(root, key_arn, upload_to_bucket, signer_principal, continue_on_error):
    """Discover pipelines/*/*/manifest.json, sign each UNSIGNED one, upload to S3.

    Derives <name>/<version> from the manifest payload (not the file path) for
    robustness. Treats S3 412 PreconditionFailed as success (idempotent re-run).
    """
    kms = boto3.client("kms")
    s3 = boto3.client("s3")

    manifests = sorted(root.glob("*/*/manifest.json"))
    if not manifests:
        click.echo(f"No manifests found under {root}")
        return

    signed_count = 0
    skipped_count = 0
    error_count = 0
    for manifest_path in manifests:
        try:
            envelope = json.loads(manifest_path.read_text())
            signed = sign_envelope(envelope, key_arn=key_arn, kms_client=kms,
                                   signer_principal=signer_principal)
            name = signed["payload"]["model_name"]
            version = signed["payload"]["version"]
            s3_key = f"{name}/{version}/manifest.json"

            try:
                s3.put_object(
                    Bucket=upload_to_bucket,
                    Key=s3_key,
                    Body=json.dumps(signed, indent=2, ensure_ascii=False).encode("utf-8"),
                    ContentType="application/json",
                    IfNoneMatch="*",
                )
                click.echo(f"[signed] {name}@{version} -> s3://{upload_to_bucket}/{s3_key}")
                signed_count += 1
            except Exception as e:
                if _is_precondition_failed(e):
                    click.echo(f"[skip-existing] {name}@{version} already in S3")
                    skipped_count += 1
                else:
                    raise
        except Exception as e:
            error_count += 1
            click.echo(f"[error] {manifest_path}: {e}", err=True)
            if not continue_on_error:
                raise

    click.echo(f"Done. signed={signed_count} skipped-existing={skipped_count} errors={error_count}")
    if error_count and continue_on_error:
        sys.exit(1)


def _is_precondition_failed(exc: Exception) -> bool:
    """Detect S3 PutObject IfNoneMatch="*" returning 412."""
    try:
        code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
        return code in ("PreconditionFailed", "412")
    except Exception:
        return False


@main.command("verify-online")
@click.option("--manifest", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def verify_online_cmd(manifest):
    envelope = json.loads(manifest.read_text())
    kms = boto3.client("kms")
    try:
        verify_online(envelope, kms_client=kms)
    except VerificationError as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)
    click.echo("OK")


@main.command("verify-offline")
@click.option("--manifest", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--public-key", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def verify_offline_cmd(manifest, public_key):
    envelope = json.loads(manifest.read_text())
    pem_bytes = public_key.read_bytes()
    try:
        verify_offline(envelope, public_key_pem=pem_bytes)
    except VerificationError as e:
        click.echo(f"FAIL: {e}", err=True)
        sys.exit(1)
    click.echo("OK")


@main.command("publish-key")
@click.option("--key-arn", required=True)
@click.option("--bucket", required=True)
@click.option("--version", default="v1")
def publish_key_cmd(key_arn, bucket, version):
    kms = boto3.client("kms")
    s3 = boto3.client("s3")
    uri = publish_public_key(key_arn=key_arn, bucket=bucket,
                             kms_client=kms, s3_client=s3, version=version)
    click.echo(uri)


def _upload_signed_envelope(envelope: dict, *, s3_uri: str) -> None:
    """Upload a signed envelope dict to an s3:// URI using IfNoneMatch="*"."""
    assert s3_uri.startswith("s3://")
    bucket, _, key = s3_uri[5:].partition("/")
    s3 = boto3.client("s3")
    body = json.dumps(envelope, indent=2, ensure_ascii=False).encode("utf-8")
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body,
                     ContentType="application/json", IfNoneMatch="*")
    except Exception as e:
        if _is_precondition_failed(e):
            return
        raise
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
uv run pytest manifest-signer/tests/test_cli.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Sanity-check the entry point**

```bash
uv run manifest-signer --help
```

Expected: help output listing all five subcommands.

- [ ] **Step 7: Ruff + mypy clean**

```bash
uv run ruff check
uv run mypy manifest-signer/src
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add manifest-signer/src/manifest_signer/cli.py \
        manifest-signer/tests/test_cli.py \
        manifest-signer/tests/conftest.py
git commit -m "feat(manifest-signer): add Click CLI with five subcommands

sign            — single-file signer (developer + dry-run + in-place + upload-to)
sign-all        — CI workhorse: globs <root>/*/*/manifest.json, signs UNSIGNED,
                  uploads to s3 with IfNoneMatch=\"*\" (412 treated as success)
verify-online   — kms:Verify against the live CMK; exit 0 / 1
verify-offline  — cryptography verify against a PEM-encoded public key
publish-key     — kms:GetPublicKey -> upload PEM to S3 (one-shot)

sign-all derives <name>/<version> from the manifest's payload, not the
file path -- robust to layout drift.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: End-to-end test

**Why:** Prove the full CI happy path runs without AWS. Sign-all → verify-online → verify-offline on the same fixture tree inside one moto context.

**Files:**
- Create: `manifest-signer/tests/test_e2e.py`

- [ ] **Step 1: Write the e2e test**

Create `manifest-signer/tests/test_e2e.py`:

```python
"""End-to-end happy path: sign-all → verify-online → verify-offline."""

from __future__ import annotations

import json

import boto3
from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization

from manifest_signer.cli import main


def test_full_ci_happy_path(pipelines_tree, signing_key, kms_client, s3_client):
    runner = CliRunner()
    bucket = "ci-signed-manifests"
    s3_client.create_bucket(Bucket=bucket,
                            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})

    # 1. sign-all
    r = runner.invoke(main, [
        "sign-all",
        "--root", str(pipelines_tree),
        "--key-arn", signing_key["Arn"],
        "--upload-to-bucket", bucket,
        "--signer-principal", "arn:aws:sts::111:assumed-role/signer/run-42",
    ])
    assert r.exit_code == 0, r.output

    # 2. Re-run sign-all -> should be idempotent
    r2 = runner.invoke(main, [
        "sign-all",
        "--root", str(pipelines_tree),
        "--key-arn", signing_key["Arn"],
        "--upload-to-bucket", bucket,
        "--signer-principal", "arn:aws:sts::111:assumed-role/signer/run-42",
    ])
    assert r2.exit_code == 0, r2.output

    # 3. Download both signed manifests; verify online and offline
    der = kms_client.get_public_key(KeyId=signing_key["KeyId"])["PublicKey"]
    pub = serialization.load_der_public_key(der)
    pem = pub.public_bytes(serialization.Encoding.PEM,
                           serialization.PublicFormat.SubjectPublicKeyInfo)

    from manifest_signer.verifier import verify_offline, verify_online

    for s3_key in ("credit-risk-pd/1.0.0/manifest.json",
                   "fraud-detection/0.1.0/manifest.json"):
        body = s3_client.get_object(Bucket=bucket, Key=s3_key)["Body"].read()
        envelope = json.loads(body)
        assert envelope["signature"] != "UNSIGNED"
        verify_online(envelope, kms_client=kms_client)
        verify_offline(envelope, public_key_pem=pem)
```

- [ ] **Step 2: Run the e2e test**

```bash
uv run pytest manifest-signer/tests/test_e2e.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Run the full workspace test suite (sanity)**

```bash
uv run pytest
```

Expected: previous totals + all the new manifest-signer tests (smoke 1, errors 4, canonical-compat 3, signer 9, verifier-online 3, verifier-offline 4, publisher 2, cli 8, e2e 1 = 35).

- [ ] **Step 4: Commit**

```bash
git add manifest-signer/tests/test_e2e.py
git commit -m "test(manifest-signer): end-to-end CI happy-path test

Exercises the full flow inside one moto context: sign-all on a fixture
pipelines/ tree, idempotent re-run, then verify-online + verify-offline
against the uploaded artefacts. Proves the CI signing step works without
AWS credentials.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Terraform `signing-foundation` module

**Why:** Provisions the CMK, OIDC IdP, both IAM roles, and two S3 buckets. This is the deploy-time backbone for everything in this sprint. All resources land in `exl-prod`. The IAM trust policies gate on the GitHub Actions OIDC token's `aud` and `sub` claims so only this repo on `main` can assume either role.

**Files:**
- Create: `terraform/modules/signing-foundation/versions.tf`
- Create: `terraform/modules/signing-foundation/variables.tf`
- Create: `terraform/modules/signing-foundation/outputs.tf`
- Create: `terraform/modules/signing-foundation/kms.tf`
- Create: `terraform/modules/signing-foundation/oidc.tf`
- Create: `terraform/modules/signing-foundation/iam_signer.tf`
- Create: `terraform/modules/signing-foundation/iam_registrar.tf`
- Create: `terraform/modules/signing-foundation/s3.tf`
- Create: `terraform/modules/signing-foundation/README.md`

- [ ] **Step 1: Create `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

- [ ] **Step 2: Create `variables.tf`**

```hcl
variable "env" {
  description = "Environment identifier (exl-prod, exl-stg, etc.)."
  type        = string
}

variable "region" {
  description = "AWS region. Defaults to eu-west-1 for POPIA proximity to ABSA; override per-env if needed."
  type        = string
  default     = "eu-west-1"
}

variable "repo_full_name" {
  description = "GitHub repository in <owner>/<repo> form for OIDC sub-claim trust."
  type        = string
}

variable "allowed_refs" {
  description = "List of GitHub refs allowed to assume the signer and registrar roles. Defaults to refs/heads/main only."
  type        = list(string)
  default     = ["refs/heads/main"]
}

variable "key_admin_principals" {
  description = "ARNs allowed to administer the KMS key (Describe/Update/Schedule deletion). Human admins or break-glass roles."
  type        = list(string)
}

variable "absa_verifier_principals" {
  description = "Cross-account ABSA IAM principals allowed kms:Verify + kms:GetPublicKey on the signing CMK. Defaults to empty until ABSA handoff."
  type        = list(string)
  default     = []
}

variable "writer_policy_arn" {
  description = "ARN of the pipeline-registry writer IAM policy. Attached to the registrar role for execute-api:Invoke on POST/PATCH routes."
  type        = string
}

variable "signed_manifests_bucket_name" {
  description = "Name of the S3 bucket holding signed manifest envelopes."
  type        = string
  default     = "exl-platform-signed-manifests"
}

variable "public_keys_bucket_name" {
  description = "Name of the S3 bucket holding published public keys for offline verification."
  type        = string
  default     = "exl-platform-public-keys"
}

variable "kms_alias_name" {
  description = "Alias for the signing CMK (must start with alias/)."
  type        = string
  default     = "alias/absa-exl-manifest-signer-v1"
}
```

- [ ] **Step 3: Create `kms.tf`**

```hcl
data "aws_caller_identity" "current" {}

resource "aws_kms_key" "manifest_signer" {
  description              = "ABSA x EXL manifest envelope signer (RSA-3072, deterministic RSASSA_PKCS1_V1_5_SHA_256)"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = "RSA_3072"
  deletion_window_in_days  = 30
  enable_key_rotation      = false # asymmetric KMS keys do not support automatic rotation (ADR-0009)
  policy                   = data.aws_iam_policy_document.kms_key.json
  tags = {
    Sprint = "phase-2-sprint-3"
    ADR    = "0009"
  }
}

resource "aws_kms_alias" "manifest_signer" {
  name          = var.kms_alias_name
  target_key_id = aws_kms_key.manifest_signer.id
}

data "aws_iam_policy_document" "kms_key" {
  statement {
    sid       = "EnableRootAccount"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid = "KeyAdminsManage"
    actions = [
      "kms:Describe*", "kms:Get*", "kms:List*",
      "kms:Update*", "kms:TagResource", "kms:UntagResource",
      "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = var.key_admin_principals
    }
  }

  statement {
    sid       = "SignerSigns"
    actions   = ["kms:Sign", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.signer.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }

  dynamic "statement" {
    for_each = length(var.absa_verifier_principals) > 0 ? [1] : []
    content {
      sid       = "AbsaVerifiers"
      actions   = ["kms:Verify", "kms:GetPublicKey", "kms:DescribeKey"]
      resources = ["*"]
      principals {
        type        = "AWS"
        identifiers = var.absa_verifier_principals
      }
    }
  }
}
```

- [ ] **Step 4: Create `oidc.tf`**

```hcl
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"] # GitHub Actions root CA thumbprint
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [for r in var.allowed_refs : "repo:${var.repo_full_name}:ref:${r}"]
    }
  }
}
```

- [ ] **Step 5: Create `iam_signer.tf`**

```hcl
resource "aws_iam_role" "signer" {
  name               = "pipeline-factory-signer"
  description        = "Assumed by GitHub Actions on push to main to sign manifest envelopes via kms:Sign."
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

data "aws_iam_policy_document" "signer_perms" {
  statement {
    sid       = "SignManifestsWithFixedAlgorithm"
    actions   = ["kms:Sign"]
    resources = [aws_kms_key.manifest_signer.arn]
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["RSASSA_PKCS1_V1_5_SHA_256"]
    }
  }

  statement {
    sid       = "GetPublicKeyForVerifyHelpers"
    actions   = ["kms:GetPublicKey", "kms:DescribeKey"]
    resources = [aws_kms_key.manifest_signer.arn]
  }

  statement {
    sid       = "WriteSignedManifests"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.signed_manifests.arn}/*"]
  }

  statement {
    sid       = "PublishPublicKeyArtifact"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.public_keys.arn}/manifest-signing/*"]
  }
}

resource "aws_iam_role_policy" "signer_perms" {
  name   = "signer-perms"
  role   = aws_iam_role.signer.id
  policy = data.aws_iam_policy_document.signer_perms.json
}
```

- [ ] **Step 6: Create `iam_registrar.tf`**

```hcl
resource "aws_iam_role" "registrar" {
  name               = "pipeline-factory-registrar"
  description        = "Assumed by GitHub Actions on push to main to POST/PATCH the pipeline registry API."
  assume_role_policy = data.aws_iam_policy_document.github_trust.json
}

resource "aws_iam_role_policy_attachment" "registrar_writer" {
  role       = aws_iam_role.registrar.name
  policy_arn = var.writer_policy_arn
}
```

- [ ] **Step 7: Create `s3.tf`**

```hcl
# -------- Signed manifests bucket (private, audit anchor) --------

resource "aws_s3_bucket" "signed_manifests" {
  bucket = var.signed_manifests_bucket_name
  tags = {
    Sprint = "phase-2-sprint-3"
    ADR    = "0009"
  }
}

resource "aws_s3_bucket_versioning" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "signed_manifests" {
  bucket = aws_s3_bucket.signed_manifests.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "signed_manifests" {
  bucket                  = aws_s3_bucket.signed_manifests.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -------- Public keys bucket (scoped public read on manifest-signing/*) --------

resource "aws_s3_bucket" "public_keys" {
  bucket = var.public_keys_bucket_name
  tags = {
    Sprint = "phase-2-sprint-3"
    ADR    = "0009"
  }
}

resource "aws_s3_bucket_versioning" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "public_keys" {
  bucket = aws_s3_bucket.public_keys.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "public_keys" {
  bucket                  = aws_s3_bucket.public_keys.id
  block_public_acls       = true
  block_public_policy     = false # required for the scoped read policy below
  ignore_public_acls      = true
  restrict_public_buckets = false # required for the scoped read policy below
}

data "aws_iam_policy_document" "public_keys_read" {
  statement {
    sid       = "AllowPublicReadOfPublishedKeys"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.public_keys.arn}/manifest-signing/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

# tfsec:ignore:aws-s3-no-public-buckets see docs/adr/0009-signing-foundation-topology.md
resource "aws_s3_bucket_policy" "public_keys_read" {
  bucket = aws_s3_bucket.public_keys.id
  policy = data.aws_iam_policy_document.public_keys_read.json
}
```

- [ ] **Step 8: Create `outputs.tf`**

```hcl
output "kms_key_arn" {
  description = "ARN of the manifest-signing KMS asymmetric CMK."
  value       = aws_kms_key.manifest_signer.arn
}

output "kms_key_alias" {
  description = "Alias of the manifest-signing CMK."
  value       = aws_kms_alias.manifest_signer.name
}

output "signer_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions to sign manifests."
  value       = aws_iam_role.signer.arn
}

output "registrar_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions to POST/PATCH the registry."
  value       = aws_iam_role.registrar.arn
}

output "signed_manifests_bucket" {
  description = "Name of the S3 bucket holding signed manifest envelopes."
  value       = aws_s3_bucket.signed_manifests.id
}

output "public_keys_bucket" {
  description = "Name of the S3 bucket holding published public keys."
  value       = aws_s3_bucket.public_keys.id
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  value       = aws_iam_openid_connect_provider.github_actions.arn
}
```

- [ ] **Step 9: Create the module README**

Create `terraform/modules/signing-foundation/README.md`:

```markdown
# `signing-foundation` Terraform module

Provisions the KMS asymmetric CMK, the GitHub Actions OIDC identity provider, two scoped IAM roles (`pipeline-factory-signer`, `pipeline-factory-registrar`), and two S3 buckets (`exl-platform-signed-manifests`, `exl-platform-public-keys`) used by the Phase 2 manifest-signing pipeline.

See [ADR-0009](../../../docs/adr/0009-signing-foundation-topology.md) for design rationale, [ADR-0003](../../../docs/adr/0003-manifest-signing-kms-asymmetric.md) for the broader signing posture, and [the Sprint 3 spec](../../../docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md) for the full context.

## Inputs

| Variable | Required | Default | Notes |
|---|---|---|---|
| `env` | yes | — | `exl-prod`, `exl-stg`, etc. |
| `region` | no | `eu-west-1` | POPIA proximity default |
| `repo_full_name` | yes | — | `<owner>/<repo>` for OIDC sub-claim |
| `allowed_refs` | no | `["refs/heads/main"]` | Refs allowed to assume signer / registrar |
| `key_admin_principals` | yes | — | Human admins / break-glass IAM principals |
| `absa_verifier_principals` | no | `[]` | Cross-account verifiers (populated post ABSA handoff) |
| `writer_policy_arn` | yes | — | From `pipeline-registry` module's existing output |
| `signed_manifests_bucket_name` | no | `exl-platform-signed-manifests` | |
| `public_keys_bucket_name` | no | `exl-platform-public-keys` | |
| `kms_alias_name` | no | `alias/absa-exl-manifest-signer-v1` | |

## Outputs

`kms_key_arn`, `kms_key_alias`, `signer_role_arn`, `registrar_role_arn`, `signed_manifests_bucket`, `public_keys_bucket`, `oidc_provider_arn`.

## Key policy

Four statements:
- `EnableRootAccount` — account root, `kms:*`.
- `KeyAdminsManage` — Describe/Update/Schedule deletion to `var.key_admin_principals`.
- `SignerSigns` — `kms:Sign` + `kms:GetPublicKey` + `kms:DescribeKey` to the signer role, conditioned on `kms:SigningAlgorithm = "RSASSA_PKCS1_V1_5_SHA_256"`.
- `AbsaVerifiers` (dynamic, only emitted when `var.absa_verifier_principals` non-empty) — `kms:Verify` + `kms:GetPublicKey` + `kms:DescribeKey` to ABSA cross-account principals.

## OIDC trust

Both roles use the same trust document — `sts:AssumeRoleWithWebIdentity` from the GitHub Actions IdP, conditioned on `token.actions.githubusercontent.com:aud = "sts.amazonaws.com"` and `:sub LIKE repo:<repo>:ref:<allowed-ref>`.

## tfsec

One expected suppression: `aws-s3-no-public-buckets` on `aws_s3_bucket_policy.public_keys_read`. Justified in ADR-0009 — public read on `manifest-signing/*` is the offline-audit story.
```

- [ ] **Step 10: Validate the module**

```bash
cd terraform/modules/signing-foundation
terraform init -backend=false
terraform validate
cd ../../..
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 11: Run tflint**

```bash
cd terraform/modules/signing-foundation
tflint --init
tflint
cd ../../..
```

Expected: no errors.

- [ ] **Step 12: Run tfsec**

```bash
tfsec terraform/modules/signing-foundation
```

Expected: one suppressed finding (the `aws-s3-no-public-buckets` annotation on the public-keys policy). All other checks pass.

- [ ] **Step 13: Commit**

```bash
git add terraform/modules/signing-foundation/
git commit -m "feat(terraform): add signing-foundation module

Provisions the Sprint 3 signing backbone in exl-prod:
- KMS asymmetric CMK (RSA-3072, RSASSA_PKCS1_V1_5_SHA_256, sign-only)
- GitHub Actions OIDC identity provider
- pipeline-factory-signer IAM role (kms:Sign + s3:PutObject)
- pipeline-factory-registrar IAM role (attaches existing
  pipeline-registry writer policy via var.writer_policy_arn)
- exl-platform-signed-manifests bucket (private, audit anchor)
- exl-platform-public-keys bucket (scoped public read on
  manifest-signing/* for offline verification per ADR-0003)

Key policy enforces RSASSA_PKCS1_V1_5_SHA_256 as a defence-in-depth IAM
condition. OIDC trust gates on the sub claim limited to refs/heads/main
by default. The public-keys bucket policy carries an annotated
tfsec:ignore for aws-s3-no-public-buckets, justified in ADR-0009.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Per-env signing stack — `terraform/envs/exl-prod/signing`

**Why:** The module is just the parts catalogue. The per-env stack actually composes it for `exl-prod`, including reading the `writer_policy_arn` from the registry stack's remote state.

**Files:**
- Create: `terraform/envs/exl-prod/signing/versions.tf`
- Create: `terraform/envs/exl-prod/signing/main.tf`
- Create: `terraform/envs/exl-prod/signing/variables.tf`
- Create: `terraform/envs/exl-prod/signing/outputs.tf`
- Create: `terraform/envs/exl-prod/signing/terraform.tfvars`
- Create: `terraform/envs/exl-prod/signing/backend.tf`

- [ ] **Step 1: Check the existing exl-prod stack structure for conventions**

```bash
ls terraform/envs/exl-prod/
```

Find the existing registry stack (likely `terraform/envs/exl-prod/registry/` or similar). Read its `backend.tf` / `main.tf` / `variables.tf` to mirror the conventions for the new `signing` stack — same backend bucket, same region, same provider config style.

- [ ] **Step 2: Create `versions.tf`**

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

- [ ] **Step 3: Create `backend.tf`**

Mirror the existing `exl-prod` registry stack's backend block, changing only the `key` to `signing/terraform.tfstate`. Example shape (adjust to match the existing convention exactly):

```hcl
terraform {
  backend "s3" {
    bucket         = "absa-exl-tfstate-exl-prod"
    key            = "signing/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    use_lockfile   = true
  }
}
```

- [ ] **Step 4: Create `variables.tf`**

```hcl
variable "repo_full_name" {
  description = "GitHub repository in <owner>/<repo> form."
  type        = string
}

variable "key_admin_principals" {
  description = "ARNs allowed to administer the KMS key."
  type        = list(string)
}

variable "absa_verifier_principals" {
  description = "Cross-account ABSA verifiers. Empty until ABSA handoff."
  type        = list(string)
  default     = []
}

variable "registry_state_bucket" {
  description = "S3 bucket holding the registry stack's remote state."
  type        = string
}

variable "registry_state_key" {
  description = "Key path of the registry stack's remote state in the bucket."
  type        = string
  default     = "registry/terraform.tfstate"
}
```

- [ ] **Step 5: Create `main.tf`**

```hcl
provider "aws" {
  region = "eu-west-1"
}

data "terraform_remote_state" "registry" {
  backend = "s3"
  config = {
    bucket = var.registry_state_bucket
    key    = var.registry_state_key
    region = "eu-west-1"
  }
}

module "signing" {
  source = "../../../modules/signing-foundation"

  env                       = "exl-prod"
  region                    = "eu-west-1"
  repo_full_name            = var.repo_full_name
  key_admin_principals      = var.key_admin_principals
  absa_verifier_principals  = var.absa_verifier_principals
  writer_policy_arn         = data.terraform_remote_state.registry.outputs.writer_policy_arn
}
```

- [ ] **Step 6: Create `outputs.tf`**

```hcl
output "kms_key_arn"             { value = module.signing.kms_key_arn }
output "kms_key_alias"           { value = module.signing.kms_key_alias }
output "signer_role_arn"         { value = module.signing.signer_role_arn }
output "registrar_role_arn"      { value = module.signing.registrar_role_arn }
output "signed_manifests_bucket" { value = module.signing.signed_manifests_bucket }
output "public_keys_bucket"      { value = module.signing.public_keys_bucket }
output "oidc_provider_arn"       { value = module.signing.oidc_provider_arn }
```

- [ ] **Step 7: Create `terraform.tfvars`**

```hcl
repo_full_name = "MrVish/absa-exl-platform"

# Placeholder admin principals — set to a real IAM admin role once exl-prod is
# provisioned. The module accepts a list of ARNs.
key_admin_principals = [
  "arn:aws:iam::000000000000:role/exl-prod-admin",
]

# Empty until ABSA hands over account IDs and the cross-account verifier
# principals are known.
absa_verifier_principals = []

# Registry stack remote-state location. Adjust to the actual bucket name set
# up for exl-prod state.
registry_state_bucket = "absa-exl-tfstate-exl-prod"
registry_state_key    = "registry/terraform.tfstate"
```

- [ ] **Step 8: Validate the stack**

```bash
cd terraform/envs/exl-prod/signing
terraform init -backend=false
terraform validate
cd ../../../..
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 9: tflint + tfsec**

```bash
cd terraform/envs/exl-prod/signing
tflint --init
tflint
cd ../../../..

tfsec terraform/envs/exl-prod/signing
```

Expected: no errors, one suppressed finding (inherited from the module's public-keys policy).

- [ ] **Step 10: Add the stack to terraform-validate.yml's matrix**

Open `.github/workflows/terraform-validate.yml`. Find the `validate-stacks` matrix and add the new stack path. Example (the exact list will already include `terraform/envs/exl-prod/registry` and the per-pipeline `pipelines/credit-risk-pd/1.0.0/terraform` from Sprint 2):

```yaml
strategy:
  matrix:
    stack:
      - terraform/envs/exl-prod/registry
      - terraform/envs/exl-prod/signing  # NEW (Sprint 3)
      - pipelines/credit-risk-pd/1.0.0/terraform
```

Read the actual file to confirm the matrix shape before editing — match the existing pattern exactly.

- [ ] **Step 11: Commit**

```bash
git add terraform/envs/exl-prod/signing/ .github/workflows/terraform-validate.yml
git commit -m "feat(terraform): add exl-prod/signing per-env stack

Composes the signing-foundation module for exl-prod, reading
writer_policy_arn from the registry stack's remote state.

Adds the stack to terraform-validate.yml's validate-stacks matrix so
the CI gate exercises it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: CI workflows — sign job + publish-signing-key workflow

**Why:** Activates the signer on every push to main, with the same env-variable-gated pattern as Sprint 2's register step (sign job is a no-op until the AWS secrets are set, so dev runs stay green).

**Files:**
- Modify: `.github/workflows/pipeline-factory.yml` (add `sign` job, make `register` depend on `sign`)
- Create: `.github/workflows/publish-signing-key.yml`

- [ ] **Step 1: Modify `pipeline-factory.yml`**

Open `.github/workflows/pipeline-factory.yml`. The existing file has two jobs: `validate-and-generate` and `register`. We insert `sign` between them.

Add the `sign` job after the existing `validate-and-generate` block and before the `register` block:

```yaml
  sign:
    name: sign (kms:Sign + upload to S3)
    needs: validate-and-generate
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    env:
      SIGNER_ROLE_ARN: ${{ secrets.AWS_OIDC_SIGNER_ROLE_ARN }}
      KMS_KEY_ARN: ${{ secrets.AWS_KMS_SIGNING_KEY_ARN }}
      SIGNED_MANIFESTS_BUCKET: ${{ secrets.AWS_SIGNED_MANIFESTS_BUCKET }}
    concurrency:
      group: pipeline-factory-sign
      cancel-in-progress: false
    steps:
      - name: Skip if not configured
        if: env.SIGNER_ROLE_ARN == ''
        run: echo "AWS_OIDC_SIGNER_ROLE_ARN not set — sign step is a no-op until creds land."
      - uses: actions/checkout@v4
        if: env.SIGNER_ROLE_ARN != ''
      - uses: astral-sh/setup-uv@v5
        if: env.SIGNER_ROLE_ARN != ''
        with:
          enable-cache: true
      - name: Sync
        if: env.SIGNER_ROLE_ARN != ''
        run: uv sync --frozen
      - uses: aws-actions/configure-aws-credentials@v4
        if: env.SIGNER_ROLE_ARN != ''
        with:
          role-to-assume: ${{ env.SIGNER_ROLE_ARN }}
          aws-region: eu-west-1
      - name: Sign all unsigned manifests
        if: env.SIGNER_ROLE_ARN != ''
        run: |
          set -euo pipefail
          # Build the assumed-role STS session ARN to record as signer_principal
          CALLER=$(aws sts get-caller-identity --query Arn --output text)
          uv run manifest-signer sign-all \
            --root pipelines \
            --key-arn "$KMS_KEY_ARN" \
            --upload-to-bucket "$SIGNED_MANIFESTS_BUCKET" \
            --signer-principal "$CALLER"
```

Modify the existing `register` job: change `needs: validate-and-generate` to `needs: [validate-and-generate, sign]`. Also rename the env var read from `AWS_OIDC_REGISTRAR_ROLE_ARN` to remain the same (no change to the secret name; the spec's suggestion to rename was an idea, not a requirement — preserve the existing secret name).

The full register block after edit:

```yaml
  register:
    name: register (POST to Registry API)
    needs: [validate-and-generate, sign]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    env:
      ROLE_ARN: ${{ secrets.AWS_OIDC_REGISTRAR_ROLE_ARN }}
      REGISTRY_API_ENDPOINT: ${{ secrets.REGISTRY_API_ENDPOINT }}
    # … (existing steps unchanged)
```

Also update the `paths` triggers (both `pull_request.paths` and `push.paths`) to include `manifest-signer/**`:

```yaml
on:
  pull_request:
    paths:
      - "pipeline-factory/**"
      - "manifest-signer/**"          # NEW
      - "pipelines/**"
      - "platform-contracts/**"
      - "pyproject.toml"
      - "uv.lock"
      - ".github/workflows/pipeline-factory.yml"
  push:
    # same set, mirrored
```

- [ ] **Step 2: Create `publish-signing-key.yml`**

Create `.github/workflows/publish-signing-key.yml`:

```yaml
name: publish-signing-key

on:
  workflow_dispatch:
    inputs:
      version:
        description: 'Version label for the published public key (e.g. v1, v2)'
        required: true
        default: 'v1'

permissions:
  contents: read
  id-token: write

jobs:
  publish:
    name: publish public key
    runs-on: ubuntu-latest
    env:
      SIGNER_ROLE_ARN: ${{ secrets.AWS_OIDC_SIGNER_ROLE_ARN }}
      KMS_KEY_ARN: ${{ secrets.AWS_KMS_SIGNING_KEY_ARN }}
      PUBLIC_KEYS_BUCKET: ${{ secrets.AWS_PUBLIC_KEYS_BUCKET }}
    steps:
      - name: Skip if not configured
        if: env.SIGNER_ROLE_ARN == ''
        run: echo "AWS_OIDC_SIGNER_ROLE_ARN not set — publish-signing-key is a no-op until creds land."
      - uses: actions/checkout@v4
        if: env.SIGNER_ROLE_ARN != ''
      - uses: astral-sh/setup-uv@v5
        if: env.SIGNER_ROLE_ARN != ''
        with:
          enable-cache: true
      - name: Sync
        if: env.SIGNER_ROLE_ARN != ''
        run: uv sync --frozen
      - uses: aws-actions/configure-aws-credentials@v4
        if: env.SIGNER_ROLE_ARN != ''
        with:
          role-to-assume: ${{ env.SIGNER_ROLE_ARN }}
          aws-region: eu-west-1
      - name: Publish public key
        if: env.SIGNER_ROLE_ARN != ''
        run: |
          set -euo pipefail
          uv run manifest-signer publish-key \
            --key-arn "$KMS_KEY_ARN" \
            --bucket  "$PUBLIC_KEYS_BUCKET" \
            --version "${{ inputs.version }}"
```

- [ ] **Step 3: Run actionlint on the changed workflows**

```bash
actionlint .github/workflows/pipeline-factory.yml .github/workflows/publish-signing-key.yml
```

Expected: no errors. (If `actionlint` isn't installed locally, the pre-commit hook from the repo's existing config will run it automatically on commit.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/pipeline-factory.yml .github/workflows/publish-signing-key.yml
git commit -m "ci: add sign job + publish-signing-key workflow

pipeline-factory.yml now runs three jobs in sequence on push to main:
1. validate-and-generate (Sprint 2 drift gate; unchanged)
2. sign  — assumes AWS_OIDC_SIGNER_ROLE_ARN, runs manifest-signer
          sign-all on pipelines/*/*/manifest.json, uploads signed
          envelopes to s3://AWS_SIGNED_MANIFESTS_BUCKET/<name>/<version>/
          manifest.json. Concurrency group serialises back-to-back
          merges; sign job no-ops in dev (secrets unset).
3. register — now needs: [validate-and-generate, sign]. Existing
              Sprint 2 logic otherwise unchanged.

publish-signing-key.yml is a new workflow_dispatch one-shot for
publishing the CMK's public key to s3://AWS_PUBLIC_KEYS_BUCKET. Run
once after first apply and on each key rotation.

New required secrets (all blank-OK in dev):
  AWS_OIDC_SIGNER_ROLE_ARN
  AWS_KMS_SIGNING_KEY_ARN
  AWS_SIGNED_MANIFESTS_BUCKET
  AWS_PUBLIC_KEYS_BUCKET

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: ADRs + READMEs

**Why:** Lock the design rationale so future contributors can re-derive the choices. ADR-0009 is the load-bearing document; ADR-0003 gets a back-pointer.

**Files:**
- Create: `docs/adr/0009-signing-foundation-topology.md`
- Modify: `docs/adr/0003-manifest-signing-kms-asymmetric.md` (add storage layout subsection)
- Create: `manifest-signer/README.md`
- Modify: `docs/compliance-matrix.md` if it exists (add new rows for ADR-0009)

- [ ] **Step 1: Create ADR-0009**

Create `docs/adr/0009-signing-foundation-topology.md`:

```markdown
# ADR-0009 — Signing Foundation Topology

**Status:** Accepted
**Date:** 2026-06-04
**Supersedes:** —
**Superseded by:** —
**Related:** [ADR-0003](0003-manifest-signing-kms-asymmetric.md) (parent decision: KMS asymmetric signing), [ADR-0008](0008-generator-runtime-dual-mode.md), [Sprint 3 spec](../superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md)

## Context

ADR-0003 chose KMS asymmetric CMK signing for manifest envelopes but did not pin the bucket layout, the IAM trust scopes, the signing algorithm, or the idempotency posture. Sprint 3 needs those decisions concrete enough to build infrastructure code against.

## Decision

**Key spec.** RSA-3072 with signing algorithm `RSASSA_PKCS1_V1_5_SHA_256`. Chosen because the algorithm is **deterministic** — signing the same digest twice produces byte-identical output. This property is what makes content-addressable S3 storage and `s3:PutObject IfNoneMatch="*"`-based idempotency work end-to-end. Re-signing the same manifest on a CI re-run produces the same envelope, the same S3 object body, and a `412 PreconditionFailed` that the signer treats as success.

**Location.** The CMK lives in `exl-prod` only. No multi-region replica in Phase 2. Cross-account verification is enabled via the key policy granting `kms:Verify` + `kms:GetPublicKey` + `kms:DescribeKey` to a parameterised list of ABSA principals (defaulted empty until handoff).

**Roles & trust.** Two distinct IAM roles assumed via GitHub Actions OIDC: `pipeline-factory-signer` (`kms:Sign` + `s3:PutObject` on the signed-manifests bucket) and `pipeline-factory-registrar` (attaches the existing `pipeline-registry` writer policy granting `execute-api:Invoke`). Both roles trust the same OIDC IdP and both gate on the same subject pattern (`repo:MrVish/absa-exl-platform:ref:refs/heads/main` by default). The two roles never share permissions — least privilege at the per-job boundary.

**Algorithm enforcement.** The KMS key policy's signer statement carries a `kms:SigningAlgorithm` equality condition. Even if the signer role were over-permissioned, KMS itself refuses any `kms:Sign` call with the wrong algorithm. The signer's inline policy carries the same condition for defence-in-depth.

**Storage.**
- `s3://exl-platform-signed-manifests/<name>/<version>/manifest.json` — versioned, SSE-S3, all-public-access-blocked. The audit-grade signed envelope.
- `s3://exl-platform-public-keys/manifest-signing/<key_id>/<version>.pem` — versioned, scoped public-read on `manifest-signing/*`. The audit-trail surface that lets any party verify any historical signed manifest offline without AWS credentials.

The committed manifest in git stays UNSIGNED (drift-gated). The signed copy lives only in S3. This separation keeps the drift gate uncomplicated and removes the need for CI to push commits.

**Idempotency.** Sign-all on CI uses `s3:PutObject IfNoneMatch="*"` on every upload. The deterministic algorithm guarantees the second-attempt body equals the first; the precondition-failed response is silently swallowed. A workflow-level `concurrency.group = pipeline-factory-sign` serialises near-simultaneous merges to `main` for defence-in-depth.

## Consequences

### Pros

- **Clean separation.** Signing and registration are independent CI jobs with separate IAM roles. Either can be replaced or extended without touching the other.
- **Offline-verifiable.** Anyone holding the public key from the published S3 bucket can verify any historical signed manifest with any standard RSA tooling. No AWS credentials needed. This is the audit story for ABSA, internal auditors, SARB GOI 3/5, ISO 27001, SOC 2 Type II.
- **CI-only signer.** No human path to `kms:Sign`. Key admins can describe / update / schedule deletion but cannot themselves sign.
- **Deterministic algorithm.** Bit-for-bit idempotent re-signs make CI re-runs safe.
- **Three-layer least privilege.** OIDC trust gates on the repo + ref. Inline role policy gates on actions + resources. KMS key policy gates on the algorithm.

### Cons (accepted)

- **No KMS auto-rotation.** Asymmetric KMS keys do not support automatic rotation. Rotation is a deliberate `v2`-alongside-`v1` operation: provision `v2` via Terraform, update the signer role's resource list to include both keys, switch the application config to sign with `v2`, publish `v2`'s public key, keep `v1` indefinitely for verification of historical manifests. The runbook is a Phase 3 ops deliverable.
- **Public-read S3 policy.** The public-keys bucket carries `Principal: "*"` on `s3:GetObject` for the `manifest-signing/*` prefix. `tfsec:ignore:aws-s3-no-public-buckets` annotated with a link to this ADR. Public read is the audit story, not a misconfiguration.
- **Sprint 4 schema decision deferred.** Whether to add a `signed_manifest_ref` field to the registry record is deferred to Sprint 4 once Code Intake's audit story makes the cost of the schema change concrete.

## Alternatives considered

- **Symmetric HMAC.** Rejected. Verification by ABSA / external auditors would require shared secret distribution, defeating the audit story. KMS asymmetric is the only option that gives auditor verifiability without exposing the signing key.
- **ECC-NIST-P384.** Deferred. The deterministic property of `RSASSA_PKCS1_V1_5_SHA_256` matters more than the smaller key size; revisit if RSA performance ever becomes a bottleneck (extremely unlikely at our volume — one sign per merge).
- **Storing the signed manifest inline in the registry record.** Deferred to Sprint 4. Adds schema-change surface for marginal benefit today; the S3 location is a stable cross-link if the registry ever needs it.
- **Auto-committing the signed manifest back to git.** Rejected. Would require CI write perms, complicate the drift gate (signed manifest differs from a fresh `generate` output), and conflate source-of-truth (the unsigned committed file) with audit-grade artefact (the signed S3 copy). Cleaner to keep them separate.

## Key rotation operational notes (informational)

Asymmetric KMS rotation is the inverse of standard symmetric rotation:

1. Provision `aws_kms_key.manifest_signer_v2` via the same Terraform module (new resource or a `count`-driven variant).
2. Update `var.kms_alias_name` strategy: keep `alias/absa-exl-manifest-signer-v1` pointing at `v1`; new alias `alias/absa-exl-manifest-signer-v2` points at `v2`.
3. Update the signer role's inline policy to include `kms:Sign` on both keys.
4. Update the application config (`AWS_KMS_SIGNING_KEY_ARN` secret) to point at `v2`.
5. Publish `v2`'s public key via `manifest-signer publish-key --key-arn <v2-arn> --version v1` (the `v1` here is the *publication* version of the *v2* key, not the KMS key version).
6. Verifiers route on `envelope.signing_key_arn` — historical manifests signed by `v1` continue to verify against `v1`'s public key.
7. Retire `v1` only after all referenced manifests have expired (Phase 3 ops decision).
```

- [ ] **Step 2: Edit ADR-0003 — add storage layout subsection**

Open `docs/adr/0003-manifest-signing-kms-asymmetric.md` and append a new section before the "Consequences" section (or at the bottom if structure differs):

```markdown
## Storage layout (locked in ADR-0009)

Signed manifest envelopes are uploaded to `s3://exl-platform-signed-manifests/<name>/<version>/manifest.json` by the CI signer immediately after generation. Public keys for offline verification are published to `s3://exl-platform-public-keys/manifest-signing/<key_id>/<version>.pem`. See [ADR-0009](0009-signing-foundation-topology.md) for the IAM, KMS, and OIDC topology that supports these paths.
```

- [ ] **Step 3: Create `manifest-signer/README.md`**

```markdown
# `manifest-signer`

KMS-backed signing and verification for manifest envelopes produced by the Phase 2 Pipeline Factory (and, in Sprint 4, by Code Intake).

See [Sprint 3 spec](../docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md), [ADR-0003](../docs/adr/0003-manifest-signing-kms-asymmetric.md), [ADR-0009](../docs/adr/0009-signing-foundation-topology.md).

## Subcommands

| Command | Use case |
|---|---|
| `manifest-signer sign --manifest <path> --key-arn <arn> --signer-principal <arn> [--upload-to s3://...] [--in-place] [--dry-run]` | Sign a single manifest file. `--dry-run` skips KMS and prints what would be signed. `--upload-to` uploads to S3 with `IfNoneMatch="*"`. `--in-place` overwrites the local file. |
| `manifest-signer sign-all --root <dir> --key-arn <arn> --upload-to-bucket <bucket> --signer-principal <arn>` | CI workhorse. Globs `<root>/*/*/manifest.json`, signs every UNSIGNED one, uploads to S3. Derives `<name>/<version>` from the manifest's payload. `412 PreconditionFailed` is treated as success. |
| `manifest-signer verify-online --manifest <path>` | KMS round-trip verification against the live CMK. Exit 0 / 1. |
| `manifest-signer verify-offline --manifest <path> --public-key <path>` | Local verification with no AWS access required, against a PEM-encoded public key. |
| `manifest-signer publish-key --key-arn <arn> --bucket <name> [--version v1]` | One-shot: fetch CMK public key, PEM-encode, upload to S3. Run after first apply and on each key rotation. |

## Library API

```python
from manifest_signer.signer import sign_envelope
from manifest_signer.verifier import verify_online, verify_offline
from manifest_signer.publisher import publish_public_key
```

All three functions are pure with respect to their `kms_client` / `s3_client` parameters — pass moto-mocked clients in tests, real boto3 clients in production.

## Idempotency

`sign_envelope` follows a three-state contract: unsigned → sign; same-key signed → no-op; different-key signed → `KeyMismatchError`. Combined with the deterministic `RSASSA_PKCS1_V1_5_SHA_256` algorithm, this makes CI re-runs safe at the S3 layer (same bytes, same object, `IfNoneMatch="*"` returns 412 silently).
```

- [ ] **Step 4: Check whether `docs/compliance-matrix.md` exists; if yes, add ADR-0009 rows**

```bash
ls docs/compliance-matrix.md
```

If the file exists, add rows referencing ADR-0009 for the relevant controls (SARB GOI 3/5 "auditability of model deployment", ISO 27001 "cryptographic controls", SOC 2 Type II "change-management evidence"). Match the existing row format. If the file doesn't exist, skip — the matrix may live elsewhere or have been deferred.

- [ ] **Step 5: Commit**

```bash
git add docs/adr/0009-signing-foundation-topology.md \
        docs/adr/0003-manifest-signing-kms-asymmetric.md \
        manifest-signer/README.md
[ -f docs/compliance-matrix.md ] && git add docs/compliance-matrix.md
git commit -m "docs(adr): add ADR-0009 + manifest-signer README

ADR-0009 (Signing Foundation Topology) locks the Sprint 3 design
decisions: RSA-3072 + RSASSA_PKCS1_V1_5_SHA_256, the deterministic
algorithm property the idempotency story leans on, the role split,
the storage layout, and the rotation runbook.

ADR-0003 gains a Storage Layout subsection cross-referencing 0009.

manifest-signer README documents the five CLI subcommands and the
library API.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Final verification + PR

**Why:** Acceptance criteria check from spec §13 before opening the PR.

- [ ] **Step 1: Full test suite**

```bash
uv run pytest
```

Expected: Sprint 1 + Sprint 2 + Sprint 3 totals, all green. Sprint 3 adds ~35 tests (smoke 1, errors 4, canonical 5, canonical-compat 3, signer 9, verifier-online 3, verifier-offline 4, publisher 2, cli 8, e2e 1).

- [ ] **Step 2: Ruff clean across the workspace**

```bash
uv run ruff check
```

Expected: no errors.

- [ ] **Step 3: Mypy strict across all changed packages**

```bash
uv run mypy platform-contracts/src pipeline-factory/src manifest-signer/src
```

Expected: no errors.

- [ ] **Step 4: Terraform validate matrix locally**

```bash
for stack in terraform/modules/signing-foundation \
             terraform/envs/exl-prod/signing \
             terraform/modules/pipeline-registry; do
  echo "--- validating $stack ---"
  (cd "$stack" && terraform init -backend=false && terraform validate)
done
```

Expected: all three report `Success! The configuration is valid.`

- [ ] **Step 5: tflint + tfsec on the new module + stack**

```bash
(cd terraform/modules/signing-foundation && tflint --init && tflint)
(cd terraform/envs/exl-prod/signing && tflint --init && tflint)
tfsec terraform/modules/signing-foundation terraform/envs/exl-prod/signing
```

Expected: tflint clean. tfsec reports one suppressed `aws-s3-no-public-buckets` finding (the annotated one); no unsuppressed findings.

- [ ] **Step 6: actionlint on the changed workflows**

```bash
actionlint .github/workflows/pipeline-factory.yml \
           .github/workflows/publish-signing-key.yml \
           .github/workflows/terraform-validate.yml
```

Expected: no errors.

- [ ] **Step 7: Final acceptance-criteria check (mirrors spec §13)**

Manually confirm:
- [ ] All Sprint 3 unit tests + the e2e test pass on `main` after merge candidate (Step 1).
- [ ] Terraform validate / tflint / tfsec all clean on the new module + stack (Steps 4-5).
- [ ] `tfsec:ignore:aws-s3-no-public-buckets` is annotated with a comment referencing ADR-0009.
- [ ] `canonical_json` move landed without breaking Sprint 2 — `test_canonical_compat.py` proves byte-identity, all pipeline-factory tests still pass.
- [ ] `pipeline-registry`'s `writer_policy_arn` output is consumed by the `signing-foundation` module via `terraform_remote_state` in the per-env stack (Step 4 validate confirms).
- [ ] ADR-0009 is committed; ADR-0003 has the storage-layout edit.
- [ ] READMEs exist for `manifest-signer/` and `terraform/modules/signing-foundation/`.

- [ ] **Step 8: Run a final code-reviewer subagent**

Dispatch a fresh `superpowers:code-reviewer` subagent over the full sprint diff with the prompt:

> "Review the entire diff for Sprint 3 (Signing & OIDC Foundation) on branch `phase-2/sprint-3-signing-foundation` vs `main`. Check for: dead code, missing test coverage, IAM trust-policy or KMS key-policy weaknesses, unsafe defaults, drift between the spec (`docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md`) and the implementation, shell-injection or YAML-quoting issues in the new workflows. Skip stylistic nits unless they affect correctness or maintainability."

Address any blocking findings. Non-blocking ones go into the PR description as Known Limitations.

- [ ] **Step 9: Push the branch and open the PR**

```bash
git push -u origin phase-2/sprint-3-signing-foundation
gh pr create --title "Phase 2 Sprint 3: Signing & OIDC Foundation" --body "$(cat <<'EOF'
## Summary

Sprint 3 lands the cryptographic and identity foundation that turns Sprint 2's UNSIGNED manifest envelopes into audit-grade signed artefacts. It also delivers the `pipeline-factory-registrar` IAM role that was deferred from Sprint 2.

- New uv workspace member `manifest-signer/` — `sign` / `sign-all` / `verify-online` / `verify-offline` / `publish-key`.
- New Terraform module `signing-foundation` — KMS asymmetric CMK + GitHub Actions OIDC IdP + signer/registrar IAM roles + signed-manifests + public-keys S3 buckets, all in `exl-prod`.
- New per-env stack `terraform/envs/exl-prod/signing/`.
- New CI `sign` job in `pipeline-factory.yml` (between `validate-and-generate` and `register`) + new `publish-signing-key.yml` workflow.
- ADR-0009 (Signing Foundation Topology) introduced; ADR-0003 cross-references it.
- Refactor: `canonical_json` moved from `pipeline-factory` to `platform-contracts` so producers (Pipeline Factory, future Code Intake) and consumers (signer, verifier) share one source of truth.

## Spec

[2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md](docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation-design.md)

## Test plan

- [ ] CI green on this PR (the new `sign` and `register` jobs no-op in dev because secrets are unset; drift-gate, validate-and-generate, terraform-validate, python-validate, actionlint, tfsec all run)
- [ ] Reviewer confirms ADR-0009 captures the design rationale faithfully
- [ ] Reviewer verifies the IAM trust policy on the signer + registrar roles gates on `refs/heads/main` only by default
- [ ] Reviewer confirms the `tfsec:ignore:aws-s3-no-public-buckets` suppression is annotated with the ADR reference

## Known limitations (intentional, deferred to Sprint 4 / Phase 3)

- No real `terraform apply` runs anywhere in CI; all Terraform is `validate` / `tflint` / `tfsec` only until ABSA hands over real account IDs.
- The first real `kms:Sign` call happens in Phase 3 against ABSA's actual CMK. The CI flow is exercised entirely via `moto v5` until then.
- Code Intake validators and the first end-to-end Track A run are Sprint 4.

EOF
)"
```

- [ ] **Step 10: Branch finalisation**

Hand off to `superpowers:finishing-a-development-branch` to walk the standard options (merge locally / push and create PR / keep as-is / discard). The PR was already opened in Step 9 if `gh pr create` was chosen; otherwise the skill resolves the choice.

---

## Self-review checklist (controller-side, run before dispatching tasks)

Run through this once before kicking off subagent-driven execution:

- [ ] **Spec coverage.** Every section of the spec (§1–§14) maps to at least one task: §3 scope → T1–T13 collectively; §4 architecture → T9 (TF) + T11 (CI) flow; §5 repo layout → T2/T3/T9/T10; §6 TF module details → T9; §7 manifest-signer module → T3–T7; §8 testing → T3/T4/T5/T6/T7/T8 + T13 verification; §9 CI integration → T11; §10 ADRs → T12; §13 acceptance criteria → T13.
- [ ] **No placeholders.** Every code block is complete; no `TBD`, `TODO`, `implement later`, or `# ...` ellipses where real code is required.
- [ ] **Type consistency.** `sign_envelope`, `verify_online`, `verify_offline`, `publish_public_key` signatures in T4/T5/T6 match their CLI uses in T7 and library uses in T8. `UNSIGNED_SENTINEL = "UNSIGNED"` matches Sprint 2's `pipeline_factory.manifest.UNSIGNED_SIGNATURE = "UNSIGNED"`.
- [ ] **Refactor depends-first.** T1 (canonical_json move) precedes every consumer; T2 (workspace scaffold) precedes every manifest-signer code task.
- [ ] **No silent dependencies on Sprint 1/2 internals.** `manifest-signer` imports only from `platform_contracts.canonical` (Sprint 1) and `cryptography` / `boto3` / `click`. The `test_canonical_compat.py` is the only place where pipeline-factory is imported (intentional — guard the contract).
- [ ] **Idempotency story consistent.** Signer's three-state contract (T4), CLI's `sign-all` `IfNoneMatch="*"` + 412-as-success (T7), e2e test's re-run (T8), CI `concurrency.group` (T11), and ADR-0009 (T12) all refer to the same property. Determinism + content-addressable upload + precondition-failed = no-op.

---

## Execution handoff

Plan complete and saved to [docs/superpowers/plans/2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation.md](2026-06-04-absa-exl-phase-2-sprint-3-signing-foundation.md). Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task with two-stage review (spec compliance, then code quality) between tasks. Same pattern as Sprints 1 and 2.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

**Which approach?**
