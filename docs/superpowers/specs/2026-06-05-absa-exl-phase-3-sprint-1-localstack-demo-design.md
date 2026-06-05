# Phase 3 Sprint 1 — LocalStack End-to-End Demo + Hygiene

**Status:** Design approved · 2026-06-05
**Owner:** EXL platform team
**Sprint window:** ~10 engineer-days (~5-6 days with parallel subagents)
**Branch:** `phase-3/sprint-1-localstack-demo`

---

## 1. Goal

Deliver a single `make demo` command (and equivalent `python -m demo run`) that stands up a local replica of the EXL signing + registry stack against LocalStack, runs the full producer + verifier chain against the worked-example package `credit-risk-pd@1.0.0`, and prints a structured transcript proving every link of the cryptographic audit chain holds.

The same flow runs on every PR via GitHub Actions, becoming the first CI gate that exercises the seams between Code Intake, Pipeline Factory, manifest-signer, and pipeline-registry — surfaces our unit tests cannot reach because they run in-process under moto.

Bundled with the demo: nine reviewer follow-ups (F0–F8) carried over from Sprints 2-4.

## 2. Architecture summary

`python -m demo run` orchestrates four phases:

1. **`up`** — `docker compose up -d localstack`; wait for `/_localstack/health` ready; `terraform apply` three stacks (signing-foundation, registry, public-key-bucket) against LocalStack endpoints.
2. **`registry`** — start `uvicorn pipeline_registry.app:app --port 8080` as a background subprocess pointed at LocalStack DynamoDB; wait for `/healthz` 200.
3. **`run`** — execute the producer chain (7 sub-steps: code-intake validate → generate-manifest → sign+upload → factory generate → sign+upload pipeline → publish-key → register), then execute the verifier chain (5 sub-steps under the `absa-sim` boto3 session: fetch manifest from S3 → fetch PEM → verify-offline → registry GET → chain-digest assertion).
4. **`down`** — kill uvicorn, `docker compose down`, optionally `terraform destroy` (`--keep-state` to skip).

Key architectural commitments:

- **The producer chain reuses our existing CLIs verbatim.** No demo-only code paths in `code-intake`, `generate-pipeline`, `manifest-signer`, `register-pipeline`. The demo is a *consumer* of the platform, not a fork.
- **The verifier chain is new code** in `scripts/demo/verifier.py` that imports `manifest_signer.verifier.verify_offline` directly so the cross-account boto3 session can be injected.
- **LocalStack runs as one CE container** with two simulated AWS accounts via the `x-localstack-account-id` header. No Pro license required.
- **Terraform reuses the existing modules** (`pipeline-registry/terraform`, `manifest-signer/terraform/signing-foundation`). The new stack at `infra/localstack/terraform/` adds endpoint overrides; production Terraform is untouched.

## 3. Scope decisions

These were locked during the brainstorming round:

| Decision | Choice | Rationale |
|---|---|---|
| Demo depth | Producer chain + verifier chain | Proves both sign-and-publish and verify-and-consume; doesn't need LocalStack Pro |
| ASL execution | Out of scope | Requires Pro; unit tests already golden-test ASL render correctness |
| Form factor | Single `make demo` (also `python -m demo`) + CI gate | Production rigor; catches end-to-end regressions automatically |
| Registry API | `uvicorn pipeline_registry.app:app` in background | Exercises the FastAPI → repository → DDB boundary that unit tests skip |
| Cross-account | Two LocalStack accounts: `111111111111` exl-prod-sim, `222222222222` absa-sim | Verifier runs under absa-sim; exercises Sprint 3's cross-account IAM grants |
| Follow-ups | All 9 bundled (F0–F8) | One PR closes the demo deliverable and all reviewer carryover items |

## 4. LocalStack topology

### 4.1 Image and services

`infra/localstack/docker-compose.yml`:

```yaml
services:
  localstack:
    image: localstack/localstack:3.8.1
    ports: ["4566:4566"]
    environment:
      SERVICES: kms,s3,dynamodb,sts,iam
      DEBUG: "0"
      PERSISTENCE: "0"
      LOCALSTACK_AUTH_TOKEN: ""
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 5s
      timeout: 5s
      retries: 12
```

Pinning notes:
- Exact image tag, no `:latest`. Pin updates go through PR review.
- `SERVICES` explicit — keeps the container ~1.2 GB resident vs ~4 GB with all services.
- `PERSISTENCE: 0` — every demo run starts clean. Deterministic CI behavior; the `IfNoneMatch="*"` idempotency proofs fire on first run.
- Empty `LOCALSTACK_AUTH_TOKEN` is a positive assertion: we never need Pro.

### 4.2 Two simulated accounts

LocalStack CE supports per-request multi-account via the `x-localstack-account-id` HTTP header. Two sims:

| Account ID | Role | Used by | Resources |
|---|---|---|---|
| `111111111111` | `exl-prod-sim` | producer chain, terraform-apply, uvicorn registry | KMS asymmetric CMK + alias, manifest S3 bucket, public-key S3 bucket, DynamoDB pipeline-registry table |
| `222222222222` | `absa-sim` | verifier chain only | (none — reads cross-account from exl-prod-sim) |

Session factory (`scripts/demo/sessions.py`):

```python
LS_ENDPOINT = "http://localhost:4566"

def producer_session() -> boto3.Session:
    return _session(account_id="111111111111")

def absa_session() -> boto3.Session:
    return _session(account_id="222222222222")

def _session(*, account_id: str) -> boto3.Session:
    s = boto3.Session(
        aws_access_key_id="test", aws_secret_access_key="test",
        region_name="eu-west-1",
    )
    s.events.register("before-sign.*.*", _inject_account_id_header(account_id))
    return s

def _inject_account_id_header(account_id: str):
    def hook(request, **_):
        request.headers["x-localstack-account-id"] = account_id
    return hook
```

The `before-sign` event hook fires on every botocore request, so any client built from the session targets the right account regardless of service.

### 4.3 Terraform stack

`infra/localstack/terraform/`:

```
main.tf              # provider block w/ endpoint override
kms.tf               # → reuses manifest-signer/terraform/signing-foundation module
s3.tf                # manifest bucket + public-key bucket
dynamodb.tf          # → reuses pipeline-registry/terraform module
iam.tf               # cross-account policy stub matching Sprint 3 IAM shape
outputs.tf           # KEY_ARN, MANIFEST_BUCKET, PUBLIC_KEY_BUCKET, TABLE_NAME, region, account
versions.tf          # terraform + provider pins
.terraform.lock.hcl  # committed
```

Provider block:

```hcl
provider "aws" {
  region                      = "eu-west-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  endpoints {
    kms      = "http://localhost:4566"
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    sts      = "http://localhost:4566"
    iam      = "http://localhost:4566"
  }
}
```

The signing-foundation module is invoked with `external_verifier_arns = ["arn:aws:iam::222222222222:root"]` so the key policy resolves to absa-sim. The registry module uses the same DDB schema, GSIs, KMS encryption (LocalStack-side same CMK).

After `terraform apply`, the orchestrator reads `terraform output -json` into:

```python
@dataclass(frozen=True)
class DemoEndpoints:
    kms_key_arn: str
    kms_key_alias: str
    manifest_bucket: str
    public_key_bucket: str
    registry_table: str
    registry_url: str   # populated post-uvicorn-boot
```

## 5. Component file layout

```
scripts/demo/
├── __init__.py
├── __main__.py             # Click CLI: python -m demo {up,run,down,status}
├── sessions.py             # producer_session() / absa_session()
├── endpoints.py            # DemoEndpoints + from_terraform_output()
├── localstack.py           # docker-compose up/down + health-wait
├── terraform_runner.py     # subprocess wrapper around terraform init|apply|output|destroy
├── uvicorn_runner.py       # background uvicorn lifecycle (Popen + readyz wait + cleanup)
├── chain.py                # producer chain orchestration (7 sub-steps)
├── verifier.py             # ABSA-side simulator (5 sub-steps)
├── transcript.py           # structured stdout + Markdown report writer
└── errors.py               # DemoError, DemoStepFailed, DemoCleanupFailed

scripts/demo/tests/
├── __init__.py
├── test_sessions.py
├── test_endpoints.py
├── test_chain_shapes.py
└── test_verifier_shapes.py

infra/localstack/
├── docker-compose.yml
└── terraform/
    ├── main.tf, kms.tf, s3.tf, dynamodb.tf, iam.tf, outputs.tf, versions.tf
    └── .terraform.lock.hcl

.github/workflows/localstack-demo.yml
Makefile                    # NEW at repo root: demo, demo-up, demo-run, demo-down, demo-keep, demo-clean
docs/runbooks/localstack-demo.md
docs/runbooks/sample-transcripts/2026-06-XX-demo.md
```

### 5.1 Per-file responsibilities

| File | Responsibility |
|---|---|
| `__main__.py` | Click `@click.group()` with `up`, `run`, `down`, `status`. `run` is composite (up → registry → producer → verifier → down). Flags: `--keep-state`, `--no-cleanup`, `--transcript PATH`, `--no-color`. |
| `sessions.py` | Session factories with header-injection hook (~30 LOC including hook). |
| `endpoints.py` | `DemoEndpoints` dataclass + `from_terraform_output(json_bytes) -> DemoEndpoints` parser. Raises `DemoError` on missing keys. |
| `localstack.py` | `up(compose_file: Path) -> None`, `wait_healthy(timeout_s=60) -> None` polling `/_localstack/health`, `down(compose_file: Path, *, keep_state: bool) -> None`. |
| `terraform_runner.py` | `init(stack_dir)`, `apply(stack_dir, vars: dict)`, `output(stack_dir) -> bytes`, `destroy(stack_dir)`. Each raises `DemoStepFailed` with captured streams on non-zero exit. |
| `uvicorn_runner.py` | Context manager `run_registry(*, endpoints, port=8080)` that Popens uvicorn with LocalStack env, polls `/healthz` until 200, yields the URL, terminates on exit. Writes pid to `infra/localstack/.uvicorn.pid` for cross-run cleanup. |
| `chain.py` | `run_producer_chain(endpoints, package_path, transcript) -> ProducerResult`. The 7 sub-steps documented in §6.3. |
| `verifier.py` | `run_verifier_chain(endpoints, producer_result, transcript) -> None` under `absa_session()`. The 5 sub-steps in §6.4. |
| `transcript.py` | `Transcript` class. `step(account, message)` writes to stdout with `[exl-prod-sim]`/`[absa-sim]`/`[demo]` prefix; `write_markdown(path)` produces the artifact for CI upload. Plain ANSI codes, no `rich` dep. |
| `errors.py` | `DemoError` (base) → `DemoStepFailed(step, account, exit_code, stdout, stderr, hint)`, `DemoCleanupFailed(primary_error)`. |

### 5.2 What we explicitly do NOT add

- No new workspace package — `scripts/demo/` is tracked by root `pyproject.toml` for ruff/mypy coverage but has no `pyproject.toml` of its own.
- No `rich`/`loguru`/similar dep — `transcript.py` uses stdlib ANSI codes (~30 LOC).
- No `requests` dep — verifier HTTP GET uses `urllib.request`. `register-pipeline` already uses `requests`; that's where the dep lives.
- No new ADR — orchestration scaffolding isn't load-bearing. New documentation goes in `docs/runbooks/localstack-demo.md`.

## 6. Demo flow

### 6.1 Phase 0 — Argument parse + environment detect

`python -m demo run` reads:
- `--keep-state` — skip `docker compose down` on exit
- `--no-cleanup` — skip all teardown (for CI artifact capture)
- `--transcript PATH` — write Markdown report to PATH (default `demo-transcript.md`)
- `--no-color` — disable ANSI codes

Asserts `docker --version`, `terraform --version`, `uv --version`, `python --version >= 3.12` on PATH. Fails fast with clear hint if not.

### 6.2 Phase 1 — `up`: LocalStack + Terraform

| Step | Action | Assertion |
|---|---|---|
| 1.1 | `docker compose -f infra/localstack/docker-compose.yml up -d` | exit 0 |
| 1.2 | Poll `GET http://localhost:4566/_localstack/health` until kms+s3+dynamodb+sts+iam all `available` (timeout 60s) | all green |
| 1.3 | `terraform -chdir=infra/localstack/terraform init -input=false` | exit 0 |
| 1.4 | `terraform -chdir=infra/localstack/terraform apply -input=false -auto-approve -var='external_verifier_arns=["arn:aws:iam::222222222222:root"]'` | exit 0 |
| 1.5 | `terraform output -json` → parse into `DemoEndpoints` | all 5 outputs present |

Per-step timeouts: 60s health, 120s terraform apply, 10s output.

### 6.3 Phase 3 — Producer chain (7 sub-steps under exl-prod-sim)

| # | CLI invoked | What it touches | What's asserted |
|---|---|---|---|
| 3.1 | `code-intake validate packages/credit-risk-pd/1.0.0 --strict` | reads package, runs 5 checkers | exit 0, no findings |
| 3.2 | `code-intake generate-manifest packages/credit-risk-pd/1.0.0` | regenerates `packages/credit-risk-pd/1.0.0/manifest.json` | byte-equal to committed manifest (drift gate) |
| 3.3 | `manifest-signer sign --in-place --upload-to s3://… --manifest packages/credit-risk-pd/1.0.0/manifest.json …` | KMS sign + S3 PutObject | package envelope's `signature != "UNSIGNED"` on disk and in S3 |
| 3.4 | `generate-pipeline generate credit-risk-pd 1.0.0 --force` | regenerates `pipelines/credit-risk-pd/1.0.0/` | byte-equal to committed pipeline (drift gate) |
| 3.5 | `manifest-signer sign-all --root pipelines …` | KMS sign + S3 PutObject (pipeline manifest, `pipelines/` prefix per T15 fix) | stdout contains `[signed]` not `[skip-existing]` |
| 3.6 | `manifest-signer publish-key --key-arn … --bucket exl-public-keys-dev --version v1` | KMS GetPublicKey + S3 PutObject | PEM at `s3://exl-public-keys-dev/v1/public-key.pem` exists |
| 3.7 | `register-pipeline register --manifest pipelines/credit-risk-pd/1.0.0/manifest.json --api-url http://localhost:8080` | SigV4 POST → FastAPI → DynamoDB | response 201 with `record_id`; capture for verifier |

**Critical assertion between 3.3 and 3.5:** the package manifest's `digest` field at S3 must equal the pipeline manifest's `payload.upstream_refs[0].digest` field. This is the cryptographic anchor Sprint 4 shipped; the demo proves it survives signing.

### 6.4 Phase 4 — Verifier chain (5 sub-steps under absa-sim)

All boto3 calls use `absa_session()`. Every request carries `x-localstack-account-id: 222222222222`, so LocalStack evaluates the request as if it came from the ABSA account.

| # | What runs | What's asserted |
|---|---|---|
| 4.1 | Read pipeline manifest from manifest bucket via `s3.get_object` | cross-account `s3:GetObject` succeeds — Sprint 3's bucket policy actually grants ABSA read |
| 4.2 | Read public key PEM from public-key bucket | cross-account `s3:GetObject` on public-key bucket succeeds |
| 4.3 | `from manifest_signer.verifier import verify_offline; verify_offline(envelope, public_key_pem=pem)` | no exception — signature valid against published PEM |
| 4.4 | Re-read package manifest; assert `pipeline.upstream_refs[0].digest == sha256(canonical_json(package.payload))` | chain digest holds end-to-end through signing |
| 4.5 | `urllib.request` GET `{registry_url}/registry/credit-risk-pd/1.0.0` (registry API is exl-prod-sim-side, no cross-account here) | 200 OK; response `manifest_uri` == S3 URI from step 3.5 |

### 6.5 Phase 5 — `down` (skipped if `--keep-state` or `--no-cleanup`)

LIFO cleanup:
1. `popen.terminate()`; `popen.wait(timeout=5)`; `popen.kill()` if still alive
2. `terraform destroy -auto-approve` (optional; container teardown handles it anyway)
3. `docker compose down -v` (`-v` removes LocalStack volume)

`atexit.register()` + `signal.SIGINT`/`SIGTERM` handlers guarantee teardown fires on Ctrl+C and Docker Desktop-initiated shutdown on Windows.

### 6.6 Phase 6 — Transcript artifact

`demo-transcript.md` is written alongside terminal output. Contains:
- Per-step timestamps + durations
- Exit codes
- The two chain-digest assertion values (package digest, pipeline upstream_refs[0].digest)
- Final summary: `DEMO PASSED (16.8s total: up 8.0s · registry 4.5s · producer 3.1s · verifier 1.2s)`

Wall-clock targets:
- **Local** (Docker warm): 15-20s for `run` (excluding image pull)
- **CI** (cold runner, includes image pull): 60-90s

## 7. Error handling

### 7.1 Failure taxonomy

```python
class DemoError(Exception): ...                  # base
class DemoStepFailed(DemoError):                 # platform-side failure
    def __init__(self, *, step, account, exit_code, stdout, stderr, hint=None): ...
class DemoCleanupFailed(DemoError):              # teardown failure; carries primary
    def __init__(self, *, primary_error, cleanup_errors): ...
```

### 7.2 Exit-code split

| Exit code | Meaning | CI annotation |
|---|---|---|
| `0` | Full chain verified | ✅ green |
| `1` | Producer/verifier step failed (platform broke) | ❌ red, blocks merge |
| `2` | Infrastructure failure (Docker/Terraform/uvicorn) | ⚠️ orange, does not block merge |
| `3` | Teardown failed (orphan state may remain) | ⚠️ orange warning |

The split matters because exit 1 should block merges, exit 2/3 should not — they're environmental flakes, not regressions.

### 7.3 Per-phase failure matrix

| Phase | Failure | Detection | Exit | Hint |
|---|---|---|---|---|
| 1.1 | Docker not running | `docker compose up` stderr contains "Cannot connect" | 2 | "start Docker Desktop" |
| 1.1 | Port 4566 in use | bind failure | 2 | "another LocalStack instance is running; `make demo-down` first" |
| 1.2 | Health-check timeout | 60s elapsed | 2 | capture `docker logs` to transcript |
| 1.4 | Terraform apply | exit ≠ 0 | 2 if endpoint error, 1 if module validation error | — |
| 2.1 | Port 8080 in use | `Popen` ok but `/healthz` poll connects to different pid | 2 | "another uvicorn is running on :8080" |
| 2.2 | uvicorn `/healthz` 500 | upstream FastAPI raised on startup | 1 | platform bug |
| 3.x | CLI exit ≠ 0 | `subprocess.run` returncode | 1 | platform bug |
| 3.5 | `[skip-existing]` on a fresh run | parse stdout | 1 | T15 regression or LocalStack persistence leak |
| 3.x or 4.4 | Chain digest mismatch | explicit assertion | 1 | upstream resolver regression or signing mutated payload |
| 4.1 / 4.2 | Cross-account 403 | botocore `ClientError` code=AccessDenied | 1 | Sprint 3 IAM regression |
| 4.3 | `VerificationError` from verify_offline | exception | 1 | signing/canonicalization regression |
| 4.5 | Registry GET 404 | `urllib.error.HTTPError` | 1 | register step silently failed or DDB write didn't land |

### 7.4 Cleanup guarantee

```python
def run() -> int:
    primary: DemoError | None = None
    cleanups: list[Callable[[], None]] = []
    try:
        endpoints = phase_up(cleanups)            # appends docker-down, tf-destroy
        url = phase_registry(endpoints, cleanups) # appends uvicorn-kill
        result = phase_producer(endpoints, url)
        phase_verifier(endpoints, url, result)
    except DemoError as e:
        primary = e
    finally:
        cleanup_errors = _teardown(cleanups, keep_state=args.keep_state)
    if primary:
        return 1 if isinstance(primary, DemoStepFailed) else 2
    if cleanup_errors:
        return 3
    return 0
```

Cleanup is LIFO. A cleanup failure never masks a primary failure — primary wins for exit code and transcript; cleanup is logged as warning.

### 7.5 Idempotency / re-run safety

`make demo` followed by `make demo` (no `down` between) must work:
- LocalStack: `docker compose up -d` is a no-op if already running.
- Terraform: `apply` is idempotent (Terraform's whole job).
- uvicorn: pid-file at `infra/localstack/.uvicorn.pid`. If port 8080 is held by *our previous* uvicorn, kill it and re-spawn.
- Step 3.5's `[signed]` assertion: re-runs without `down` would hit `[skip-existing]`. Orchestrator detects this via pid-file and clears the bucket (s3:DeleteObject) before re-running. Alternative ("require `down` between runs") rejected — iterative dev is more common than fresh demos.

## 8. CI workflow

### 8.1 Trigger

```yaml
name: localstack-demo
on:
  pull_request:
    paths:
      - "code-intake/**"
      - "pipeline-factory/**"
      - "manifest-signer/**"
      - "pipeline-registry/**"
      - "platform-contracts/**"
      - "packages/credit-risk-pd/**"
      - "pipelines/credit-risk-pd/**"
      - "pipeline-factory/configs/credit-risk-pd/**"
      - "scripts/demo/**"
      - "infra/localstack/**"
      - ".github/workflows/localstack-demo.yml"
      - "pyproject.toml"
      - "uv.lock"
  push:
    branches: [main]
    paths: <same>

concurrency:
  group: localstack-demo-${{ github.ref }}
  cancel-in-progress: true
```

### 8.2 Job

Single job, `runs-on: ubuntu-latest`, `timeout-minutes: 8`.

Cross-platform local-dev support (Windows/macOS) is validated by hand during PR walkthrough, not by CI matrix — Docker-on-Windows GH runners don't reliably support Linux containers. Documented in the runbook.

Steps:
1. `actions/checkout@v4`
2. `astral-sh/setup-uv@v3` with `enable-cache: true`, `cache-dependency-glob: uv.lock`
3. `uv sync --frozen --all-extras`
4. `hashicorp/setup-terraform@v3` with `terraform_version: "1.9.5"`, `terraform_wrapper: false`
5. `docker pull localstack/localstack:3.8.1` (~15s warm, ~45s cold)
6. `python -m demo run --no-color --transcript demo-transcript.md` (timeout 5m)
7. `actions/upload-artifact@v4` of `demo-transcript.md` on success
8. On failure, upload bundle: transcript + `infra/localstack/terraform/terraform.tfstate` + `infra/localstack/.uvicorn.log`
9. Annotate failure with exit-code-appropriate severity (error for 1; warning for 2/3)
10. Soft-fail step: convert exit 2/3 workflow runs to `success` so branch protection doesn't block on infra issues

### 8.3 Required-for-merge

Yes. Added to branch protection.

Tolerance: exit codes 2/3 (infra failures) are soft-failed — the workflow returns success but writes an `::warning::` annotation. Branch protection checks `success` outcome only.

Concern: this could mask real platform regressions if the demo accidentally returns 2 instead of 1. Mitigation: every exit-2 path is explicitly enumerated in `errors.py`; PR review checks alignment.

### 8.4 Independent of existing workflows

No changes to `code-intake.yml`, `pipeline-factory.yml`, `manifest-signer.yml`, `pipeline-registry.yml`, `platform-contracts.yml`. They keep doing per-package gating. The new workflow runs in parallel — no shared concurrency group, no serial dependency.

## 9. Reviewer follow-ups (F0–F8)

Bundled here because the demo's CI run is the first thing that exercises them in concert.

### F0 — `pipeline-registry` /healthz + /readyz

**Today:** No readiness endpoint. uvicorn_runner can't poll until-ready.
**Fix:** Add `GET /healthz` (always `{"status": "ok"}`) and `GET /readyz` (checks DDB table exists, returns 503 if not). ~10 LOC in `pipeline-registry/src/pipeline_registry/app.py`.
**Test:** `test_healthz_returns_200`, `test_readyz_returns_503_when_table_absent`.

### F1 — Subprocess timeouts in code-intake checkers

**Today:** `static_python.py`, `tests.py` shell out to ruff/mypy/pytest with no timeout. A malformed fixture could hang indefinitely.
**Fix:** Wrap every `subprocess.run` with `timeout=120` (configurable per-checker). Catch `subprocess.TimeoutExpired` → emit `{CHECKER}998` finding (distinct from `999` crashed-checker).
**Tests:** `test_static_python_timeout_emits_998`, `test_tests_checker_timeout_emits_998` using fixture with `import time; time.sleep(200)` in conftest.

### F2 — `sign-all` strict on unknown `subject_type`

**Today:** `manifest-signer/src/manifest_signer/cli.py:149`: `subject_type = signed.get("subject_type", "pipeline")`. Future formats silently route to `pipelines/` prefix.
**Fix:** Raise `click.ClickException(f"unknown subject_type {subject_type!r}; signer needs upgrade")` if not in `{"package", "pipeline"}`.
**Test:** `test_sign_all_rejects_unknown_subject_type`.

### F3 — Compliance-matrix rows for ADR-0009 + ADR-0010

**Today:** `docs/compliance/policy-matrix.md` covers ADRs 0001-0008.
**Fix:** Append rows. ADR-0009 → ISO 27001 A.10 (Cryptography) + SOC2 CC6.1; ADR-0010 → A.12.1 (Operational procedures) + CC7.1.
**No code change** — markdown only.

### F4 — SCH002/SCH003 deferred-check markers

**Today:** Design commits to SCH002 (schema-version drift) and SCH003 (PIR referential integrity) being deferred to manifest-build time, but no in-code marker.
**Fix:** Add `# DEFERRED-CHECK: SCH002 …`, `# DEFERRED-CHECK: SCH003 …` comments at call sites in `code_intake/manifest.py`. Update `code-intake/README.md` "Findings reference" with both. No behavior change.

### F5 — `GeneratorError` ⇆ `PipelineDriftError` consolidation

**Today:** Both mean "generator can't produce; user must fix and re-run", handled in two different `except` branches in `pipeline-factory/.../cli.py`.
**Fix:** Keep `GeneratorError` as public type; derive `PipelineDriftError(GeneratorError)`. CLI has one `except GeneratorError` branch. Existing tests pass unchanged (subclass relationship invisible to them).

### F6 — mypy duplicate-module "score"

**Today:** Both `packages/credit-risk-pd/1.0.0/python/score.py` and `code-intake/tests/fixtures/valid_package/python/score.py` resolve to module name `score`. Warnings drift across per-file ignores.
**Fix:** `[[tool.mypy.overrides]]` with `module = "score"`, `ignore_errors = true` in root `pyproject.toml`. Remove scattered per-file ignores. Verify `uv run mypy` returns clean.

### F7 — `sign-all --continue-on-error` test coverage

**Today:** Flag exists in `cli.py:101`; nothing exercises it.
**Fix:** `test_sign_all_continue_on_error_reports_failed_count`: fixture with 3 manifests (one malformed). Without `--continue-on-error` → exits 1 on first failure. With → exits 1 at end, reports `errors=1 signed=2`, both good manifests in S3.

### F8 — `PirDataType.int` builtin shadow

**Today:** Generated enum has `PirDataType.int = "int"`. `pir_type = int` typo silently rebinds the Python builtin.
**Fix:** Wire format stays `"int"`. AST merger renames Python enum members to `INT_TYPE`, `FLOAT_TYPE`, `BOOL_TYPE`, `DATE_TYPE`, `DATETIME_TYPE`, `DECIMAL_TYPE`, `STRING_TYPE`. JSON schema unchanged. Update existing test/fixture references.

### Ordering and dependencies

- **F1, F7** land before the demo CI workflow so timeout regressions don't poison the demo runtime budget.
- **F2** lands before chain.py's `[signed]`/`[skip-existing]` assertion in §6.3 step 3.5.
- **F0** lands before uvicorn_runner.py — it polls `/healthz`.
- **F3, F4, F5, F6, F8** independent; land in any task slot.

## 10. Scope boundary

### 10.1 In scope

- `scripts/demo/` Click orchestrator (10 modules + 4 tests)
- `infra/localstack/docker-compose.yml` + `infra/localstack/terraform/`
- `.github/workflows/localstack-demo.yml`
- Root `Makefile` (5 targets)
- `docs/runbooks/localstack-demo.md` + sample transcript
- 9 reviewer follow-ups (F0–F8)
- Acceptance evidence: green `demo-transcript.md` committed under `docs/runbooks/sample-transcripts/`

### 10.2 Out of scope — deferred to later Phase 3 sprints

- Step Functions ASL runtime execution (needs LocalStack Pro)
- Per-package venv orchestration in Code Intake (ADR-0010 Negative §2)
- Stricter AST PIR column extraction — f-strings, dict aliases, dynamic dispatch (ADR-0010 Negative §3)
- Asymmetric CMK key rotation runbook + automation (ADR-0009 deferred)
- Multi-region KMS replica (Phase 4)
- Lambda packaging for `pipeline-registry`
- Real cross-account IAM with `sts:AssumeRole` chain
- `manifest-signer verify-from-bucket` CLI subcommand
- Promotion of `scripts/demo/` to `platform-demo/` workspace package
- Multi-package scenarios (package-A→package-B chaining)

### 10.3 Out of scope — blocked on ABSA inputs

- Real account onboarding (`terraform apply` against actual `exl-prod` / ABSA accounts)
- Real SAS validation (replace structural-only checker)
- PIR system integration (replace YAML file with feed/API)
- First REAL Track A scoring run
- CAB / IVU integration in the approval state machine

### 10.4 Near misses (look in-scope but aren't)

- `verifier.py` does NOT call `manifest-signer verify-offline`'s CLI — imports the library function so the cross-account session can be injected.
- The demo does NOT update `platform-contracts/.../models.py`. F8 touches codegen output via the AST merger; wire format stays identical, drift gate still passes.
- The demo does NOT change `pipeline-registry`'s public API. F0 is additive; existing routes are untouched.
- The demo does NOT add a "demo mode" to any production CLI. `AWS_ENDPOINT_URL_*` env vars are the only difference at the boto3 layer.
- The demo does NOT modify any existing CI workflow. New workflow runs alongside them.
- F0 does NOT mean we're adding observability. Just readiness probes.

## 11. Implementation order

21 tasks. Phase-grouped; same-row tasks parallelizable across subagents.

```
Row 1 — Prep follow-ups (no demo dependencies)
  T1.  F0 — pipeline-registry /healthz + /readyz             [0.5d]
  T2.  F2 — manifest-signer subject_type strict              [0.25d]
  T3.  F1 — code-intake subprocess timeouts                  [0.5d]

Row 2 — Demo primitives (pure-Python)
  T4.  scripts/demo/errors.py + transcript.py                [0.25d]
  T5.  scripts/demo/sessions.py + endpoints.py + tests       [0.5d]

Row 3 — Demo infrastructure (LocalStack + Terraform)
  T6.  scripts/demo/localstack.py                            [0.5d]
  T7.  scripts/demo/terraform_runner.py                      [0.5d]
  T8.  infra/localstack/{docker-compose.yml + terraform/}    [1d]

Row 4 — Demo runtime (depends T1, T8)
  T9.  scripts/demo/uvicorn_runner.py                        [0.5d]

Row 5 — Demo orchestration (depends T2, T9)
  T10. scripts/demo/chain.py (producer chain)                [1d]
  T11. scripts/demo/verifier.py (ABSA-side)                  [1d]

Row 6 — Demo entrypoint (depends T10, T11)
  T12. scripts/demo/__main__.py + Makefile                   [0.5d]

Row 7 — Independent follow-ups (any time after Row 1)
  T13. F7 — sign-all --continue-on-error test                [0.25d]
  T14. F5 — GeneratorError consolidation                     [0.25d]
  T15. F6 — mypy duplicate score fix                         [0.25d]
  T16. F8 — PirDataType.int rename + merger ext              [0.5d]
  T17. F4 — SCH002/SCH003 deferral docs                      [0.25d]
  T18. F3 — compliance matrix rows                           [0.25d]

Row 8 — CI gate (depends T12)
  T19. .github/workflows/localstack-demo.yml                 [0.5d]

Row 9 — Runbook + transcript (depends T19 green run)
  T20. docs/runbooks/localstack-demo.md + sample             [0.5d]

Row 10 — Final
  T21. Verification + PR                                     [0.5d]
```

**Total:** ~10 engineer-days serial; ~5-6 days with parallel subagents.
**Critical path:** T1 → T8 → T9 → T10/T11 → T12 → T19 → T20 → T21 ≈ 6 days.

### 11.1 TDD shape — first failing test per task

| Task | First failing test | What it proves |
|---|---|---|
| T1 (F0) | `test_healthz_returns_200`, `test_readyz_returns_503_when_table_absent` | shape of new endpoints |
| T2 (F2) | `test_sign_all_rejects_unknown_subject_type` | raise replaces silent fallback |
| T3 (F1) | `test_static_python_timeout_emits_998` (sleep-200 fixture) | timeout surfaces as finding not hang |
| T5 | `test_producer_session_injects_111_header`, `test_absa_session_injects_222_header` | header hook attached |
| T6 | `test_wait_healthy_polls_until_ready`, `test_wait_healthy_times_out` | bounded health-wait |
| T9 | `test_uvicorn_runner_kills_on_exit` (fake popen) | cleanup fires |
| T10 | `test_chain_calls_subprocesses_in_order` (mocked subprocess) | sequence + arg correctness |
| T11 | `test_verifier_uses_absa_session` | cross-account session is used |

The end-to-end "demo runs green" assertion is exercised by CI itself (T19). No separate integration test.

## 12. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| LocalStack 3.8.1 KMS asymmetric differs from moto's byte-stable output | Medium | T8 smoke test: `aws kms sign … RAW RSASSA_PKCS1_V1_5_SHA_256` against LocalStack. If diverges from moto, switch moto tests to fixed signature fixture. |
| `x-localstack-account-id` header injection breaks across boto3 versions | Low | Pin `boto3 >= 1.34.50` in root `pyproject.toml`. T5 tests assert header on request. |
| GH Actions runner can't pull 600MB image in budget | Low | If observed, switch to ghcr.io mirror or pre-baked runner image. Not preemptive. |
| Windows host: `docker compose`, `make` not on PATH | Medium | Runbook documents prereqs; `make demo` exits Phase 0 with clear hint if absent. |
| LocalStack KMS doesn't honor cross-account header for `kms:Verify` | Medium | Verified manually before T8; if not honored, fall back to verify-offline-only (the design's primary path is already offline; cross-account kms:Verify is a bonus). |
| F8 (`PirDataType.int` rename) breaks unseen consumers | Low | Grep before rename; only consumers are in-repo. Wire format unchanged. |

## 13. Acceptance criteria

For the sprint to ship:

1. `make demo` returns exit 0 on the implementer's machine.
2. `python -m demo run --no-cleanup` returns exit 0 in `localstack-demo.yml` on the PR.
3. `uv run pytest` returns no new failures (Sprint-4-tip baseline: 198 passing).
4. `uv run ruff check && uv run ruff format --check && uv run mypy` all clean across workspace.
5. `terraform -chdir=infra/localstack/terraform validate` clean.
6. `actionlint .github/workflows/localstack-demo.yml` clean.
7. Chain digest assertion holds:
   - `packages/credit-risk-pd/1.0.0/manifest.json:digest` (after sign)
   - == `pipelines/credit-risk-pd/1.0.0/manifest.json:payload.upstream_refs[0].digest`
   - == verifier-side computed digest after cross-account fetch
8. `demo-transcript.md` artifact exists; sample committed at `docs/runbooks/sample-transcripts/`.
9. All 9 follow-ups (F0–F8) have closing diffs visible in PR.
10. PR text includes transcript screenshot/excerpt and links to the runbook.

## 14. References

- ADR-0008 (Pipeline Factory): `docs/adr/0008-pipeline-factory-deterministic-rendering.md`
- ADR-0009 (Signing): `docs/adr/0009-signing-foundation-kms-asymmetric.md`
- ADR-0010 (Package contract): `docs/adr/0010-productized-package-contract.md`
- Sprint 3 spec §11 (cross-account verifier deferred): `docs/superpowers/specs/2026-06-02-absa-exl-phase-2-sprint-3-signing-design.md`
- Sprint 4 spec (chain-of-custody): `docs/superpowers/specs/2026-06-04-absa-exl-phase-2-sprint-4-code-intake-design.md`
- LocalStack multi-account docs: https://docs.localstack.cloud/references/credentials/#multi-account-setups
