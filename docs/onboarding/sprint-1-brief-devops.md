# Sprint 1 Brief — DevOps Engineer

**Sprint 1: Mon Jun 15 → Fri Jun 26, 2026 · Your load: 5.5 effort-days**

## Your mission on this program

You own the CI/CD layer. EXL's enterprise standard is Jenkins, not GitHub
Actions — and we have a standalone Jenkins already running. Your job across
Sprints 1–3 is to migrate all six CI gates onto it per
[ADR-0011](../adr/0011-ci-platform-jenkins.md) and retire GHA without
breaking the platform's signing/verification guarantees. After that you own
monitoring, alerting, dashboards (Sprints 4–9) and the operational runbooks
(Sprint 11).

You are the **pace-setter of Sprint 1**: the auth decision you make this
sprint (task T-0202) unblocks the AWS engineer's trust-policy work and the
entire Sprint 3 cutover.

## Sprint 1 outcome (your slice of the sprint goal)

> `python-validate` runs green on the standalone Jenkins, and its
> `ci/python-validate` commit status appears on a GitHub PR. The AWS auth
> path for Jenkins is decided and written into ADR-0011.

## Your tasks

| ID | Task | Est | Acceptance |
|---|---|---|---|
| T-0104 | Clone repo, `uv sync`, full test suite green locally | 0.5 | 278 tests pass on your machine |
| T-0108 | `make demo` green locally | 0.5 | LocalStack chain exits 0 |
| T-0201 | Document Jenkins topology | 1.0 | Doc covers: host/OS, controller version, agent fleet, executors, installed plugins (esp. GitHub Branch Source, Checks API, Credentials), network reachability to GitHub + AWS |
| T-0202 | Choose the AWS auth path | 1.0 | One of: EC2 instance profile / Jenkins-as-OIDC-IdP plugin / access keys + 90-day rotation. Decision note with rationale, reviewed by TL + AWS engineer |
| T-0204 | Register `absa-ci` shared library | 0.5 | Global Pipeline Library pointing at `ci/jenkins/` in this repo |
| T-0205 | Multibranch job for python-validate | 1.0 | First run completes (green or with diagnosed failures) |
| T-0206 | Commit status lands on a GitHub PR | 1.0 | `ci/python-validate` visible in PR checks; a sandbox branch-protection rule can require it |

## Suggested day-by-day

| Day | Plan |
|---|---|
| Mon 15 | Sprint planning (AM). Access verification: Jenkins admin, GitHub write. Start T-0104. |
| Tue 16 | Architecture walkthrough (AM, TL hosts). Finish T-0104 + T-0108. |
| Wed 17 | T-0201 — inventory the Jenkins instance. Output: topology doc PR. |
| Thu 18 | T-0202 — auth-path decision session with TL + AWS engineer. Where does Jenkins run (EC2? on-prem VM?) — that answer picks the path. |
| Fri 19 | T-0204 register the shared library. Start T-0205 (create the multibranch job). |
| Mon 22 | T-0205 — first run. Expect shared-library Groovy issues (`publishChecks` plugin quirks, PATH assumptions); log them — fixes are budgeted in S2 (T-0207). |
| Tue 23 | T-0206 — open a test PR, confirm the status arrives, wire a sandbox branch-protection rule that requires it. |
| Wed 24 | Buffer: debug whatever Mon/Tue surfaced. |
| Thu 25 | Write up findings; draft the S2 plan (remaining 3 no-AWS jobs + credentials wiring). |
| Fri 26 | Sprint review: demo the green Jenkins run + the PR status. Retro. |

## Day-1 access checklist

- [ ] Jenkins admin (or enough to install plugins + create jobs + register libraries)
- [ ] GitHub repo write access + ability to create a test PR
- [ ] Docker available on at least one Jenkins agent (needed in S2 for localstack-demo)
- [ ] Network: Jenkins → GitHub API, Jenkins → AWS endpoints (verify, don't assume)

## Who depends on you / who you depend on

- **AWS engineer depends on T-0202** — the trust-policy variant in
  `signing-foundation` Terraform can't be written until you pick the auth path.
- **You depend on TL** for the ADR-0011 amendment (T-0203) and decision review.
- Nothing you do this sprint is blocked on ABSA.

## Reading list (in order)

1. [ADR-0011](../adr/0011-ci-platform-jenkins.md) — the whole migration plan; §"Open questions" is your T-0202 homework
2. [`ci/jenkins/README.md`](../../ci/jenkins/README.md) — library wiring, credentials table, migration map
3. The 5 Jenkinsfiles in [`ci/jenkins/examples/`](../../ci/jenkins/examples/) — you'll run all of them by S3
4. [`.github/workflows/`](../../.github/workflows/) — what you're replacing; note the localstack-demo exit-code gate semantics
5. [`docs/runbooks/localstack-demo.md`](../runbooks/localstack-demo.md) — troubleshooting for the S2 port

## What's next for you (S2–S3 preview)

- **S2:** fix shared-library issues (2d), bring up code-intake / terraform-validate / localstack-demo jobs, wire the 7 platform secrets into Jenkins credentials.
- **S3:** the cutover — sign/register stages against real AWS, 1-week GHA-vs-Jenkins parallel run with byte-equivalence comparison, flip branch protection, retire GHA. After S3, Jenkins is the only CI gate.
