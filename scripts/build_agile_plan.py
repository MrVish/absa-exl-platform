"""Build the Agile sprint-plan Excel for the ABSA x EXL delivery team.

Re-anchors the program plan to the real team start (Sprint 1 = 2026-06-15)
and decomposes it into EPIC -> Story -> Task with per-role assignment and
capacity-checked 2-week sprints.

Roles:
  AWS     - AWS / MLOps engineer
  DE      - Data engineer
  SAS     - SAS developer (model code optimization)
  DevOps  - DevOps engineer (Jenkins, CI/CD, monitoring)
  TL      - Tech lead / platform engineer (Vishnu)

Sheets:
  1. README          - how to use, capacity model, anchoring
  2. Backlog         - flat EPIC/Story/Task tree (Jira-importable)
  3. Sprint Plan     - dates, goal, milestone, per-role load formulas
  4. Role Load       - roles x sprints grid with capacity conditional fills
  5. Prerequisites   - internal setup + ABSA-blocked register
  6. Dashboard       - counts by epic / role / status (formula-driven)

Run from repo root: `uv run --with openpyxl python scripts/build_agile_plan.py`
Output: docs/absa-exl-agile-plan.xlsx
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ---------- Styling ----------

FONT_HEADER = Font(name="Arial", size=11, bold=True, color="FFFFFF")
FONT_BODY = Font(name="Arial", size=10)
FONT_BODY_BOLD = Font(name="Arial", size=10, bold=True)
FONT_TITLE = Font(name="Arial", size=14, bold=True, color="1F3864")
FONT_EPIC = Font(name="Arial", size=10, bold=True, color="FFFFFF")
FONT_STORY = Font(name="Arial", size=10, bold=True, color="1F3864")

FILL_HEADER = PatternFill("solid", start_color="1F3864")
FILL_EPIC = PatternFill("solid", start_color="2E4172")
FILL_STORY = PatternFill("solid", start_color="D9E2F3")
FILL_BLOCKED = PatternFill("solid", start_color="FFCDD2")
FILL_MILESTONE = PatternFill("solid", start_color="FFE0B2")
FILL_OK = PatternFill("solid", start_color="C8E6C9")
FILL_WARN = PatternFill("solid", start_color="FFF9C4")

BORDER_THIN = Border(
    left=Side(style="thin", color="BFBFBF"),
    right=Side(style="thin", color="BFBFBF"),
    top=Side(style="thin", color="BFBFBF"),
    bottom=Side(style="thin", color="BFBFBF"),
)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

ROLES = ["AWS", "DE", "SAS", "DevOps", "TL"]
ROLE_NAMES = {
    "AWS": "AWS / MLOps Engineer",
    "DE": "Data Engineer",
    "SAS": "SAS Developer",
    "DevOps": "DevOps Engineer",
    "TL": "Tech Lead (Vishnu)",
}
# Effective capacity in effort-days per 2-week sprint (10 working days x focus factor)
CAPACITY = {"AWS": 8.0, "DE": 8.0, "SAS": 8.0, "DevOps": 8.0, "TL": 6.0}

SPRINT_1_START = date(2026, 6, 15)
N_SPRINTS = 12


def sprint_dates(n: int) -> tuple[date, date]:
    start = SPRINT_1_START + timedelta(days=(n - 1) * 14)
    return start, start + timedelta(days=11)  # Mon -> Fri of week 2


SPRINT_GOALS = {
    1: ("Team onboarded; Jenkins identity decided; python-validate green on Jenkins; ABSA ask-list sent",
        ""),
    2: ("All no-AWS Jenkins jobs live; AWS bootstrap applied; data contracts started; SAS model-1 review done",
        ""),
    3: ("Jenkins cutover complete (GHA retired); signing foundation live on real AWS; model-1 optimized",
        "Jenkins is the sole CI gate"),
    4: ("Registry API live on Lambda (dev); replication path validated; model-1 packaged + validated",
        "Registry live in dev"),
    5: ("Step Functions executes model-1 in dev; PIR sync built; model-2 optimized",
        ""),
    6: ("DRESS REHEARSAL: full chain on real AWS for models 1-2; dashboards started",
        "Dress rehearsal pass"),
    7: ("Group 1 initial production scoring; reconciliation vs benchmarks; defect cycle",
        ""),
    8: ("GROUP 1 ABSA SIGN-OFF; Group 2 wave planning starts",
        "*** GROUP 1 SIGN-OFF ***"),
    9: ("Group 2 wave 1 (models 3-4) live; dashboards validated with ABSA",
        ""),
    10: ("Group 2 wave 2 (models 5-6) live; output delivery automated",
         ""),
    11: ("Group 2 wave 3 (models 7-8) live; runbooks + support rota",
         ""),
    12: ("Group 2 wave 4 (models 9-10) live; GROUP 2 SIGN-OFF; handover; steady-state go-live",
         "*** GROUP 2 SIGN-OFF + GO-LIVE ***"),
}

# ---------- Backlog data ----------

# EPICs: (id, title, owner, sprints, objective)
EPICS = [
    ("E01", "Team Onboarding & Governance", "TL", "S1",
     "Everyone productive in week 1: repo green locally, board live, ABSA dependency register running."),
    ("E02", "CI/CD on Existing Jenkins", "DevOps", "S1-S3",
     "Migrate all 6 CI gates from GitHub Actions to the standalone Jenkins per ADR-0011; retire GHA."),
    ("E03", "AWS Foundation (Real Accounts)", "AWS", "S1-S4",
     "Bootstrap real EXL accounts, landing zone, signing foundation, registry-on-Lambda, replication path."),
    ("E04", "Data Readiness & Quality", "DE", "S1-S7",
     "Data contracts, ingestion validation, DQ framework (volume + drift), PIR integration."),
    ("E05", "SAS Model Intake & Optimization", "SAS", "S1-S6",
     "SAS standards, real SAS linting, models 1-2 optimized + packaged, reconciliation tooling."),
    ("E06", "ML Compute & Pipeline Execution", "AWS", "S3-S6",
     "Compute platform decision (D04), real Step Functions execution, schedules, perf test."),
    ("E07", "Controls & Change Management", "TL", "S4-S7",
     "Change workflow (CAB/IVU), rotation cadence, retention, pre-go-live access audit."),
    ("E08", "Group 1 Go-Live (Models 1-2)", "TL", "S6-S8",
     "Dress rehearsal, production scoring, benchmark reconciliation, PIR, ABSA sign-off."),
    ("E09", "Dashboards & Output Delivery", "DevOps", "S4-S9",
     "Run-status dashboard, alerting, DQ/drift panels, automated signed output delivery to ABSA."),
    ("E10", "Group 2 Scale-Out (Models 3-10)", "SAS", "S8-S12",
     "Template-driven onboarding, 2 models per sprint across 4 waves, Group 2 sign-off."),
    ("E11", "Steady State & Handover", "TL", "S11-S12",
     "Runbooks, support rota, service review cadence, handover, steady-state go-live."),
]

# Stories: (id, epic, title, sprint_label, acceptance)
STORIES = [
    ("ST-0101", "E01", "Environment & platform onboarding", "S1",
     "All 4 engineers: 278-test suite green + `make demo` exit 0 locally; walkthrough attended."),
    ("ST-0102", "E01", "Agile working agreement & board", "S1",
     "Jira board mirrors this backlog; DoD + ceremony calendar published."),
    ("ST-0103", "E01", "ABSA dependency management", "S1",
     "7-item ask-list sent; weekly chase cadence running with named SPOC."),
    ("ST-0201", "E02", "Jenkins discovery & identity decision", "S1",
     "Topology documented; auth path chosen (instance profile / OIDC IdP / keys+rotation); ADR-0011 amended."),
    ("ST-0202", "E02", "Shared library proving ground", "S1-S2",
     "absa-ci registered; ci/python-validate status visible on a GitHub PR."),
    ("ST-0203", "E02", "No-AWS pipelines live", "S2",
     "code-intake, terraform-validate, localstack-demo jobs green on Jenkins."),
    ("ST-0204", "E02", "AWS-touching pipelines + cutover", "S3",
     "sign/register green vs real AWS; 1-week parallel run byte-identical; branch protection flipped; GHA disabled."),
    ("ST-0301", "E03", "Account bootstrap & state backends", "S1-S2",
     "CloudTrail/GuardDuty/SecurityHub live in 3 EXL accounts; TF state backends operational."),
    ("ST-0302", "E03", "Landing zone & connectivity", "S2-S3",
     "Landing zone applied; network path to ABSA implemented per their decision; IPs whitelisted."),
    ("ST-0303", "E03", "Signing foundation live", "S2-S4",
     "KMS CMK created in exl-prod; PEM published; cross-account verify passes with ABSA principal."),
    ("ST-0304", "E03", "Registry API on real AWS", "S3-S4",
     "registry-api on Lambda+APIGW in dev->prod; SigV4 register smoke passes."),
    ("ST-0305", "E03", "S3 replication path", "S4",
     "Replication modules applied; encrypted transfer validated end-to-end with ABSA test object."),
    ("ST-0401", "E04", "Data contracts per model", "S1-S2",
     "Data dictionary template + input schemas for models 1-2; volume/cadence matrix for all 10."),
    ("ST-0402", "E04", "Ingestion & arrival validation", "S2-S3",
     "Bucket layout convention; schema-on-arrival validation job; reject/return-to-ABSA workflow."),
    ("ST-0403", "E04", "Data quality framework", "S4-S5",
     "Volume band checks + PSI drift design (feeds decision D01); DQ report artifact per run."),
    ("ST-0404", "E04", "PIR integration", "S5-S6",
     "pir.yaml synced from ABSA PIR system; coverage report on real model inputs."),
    ("ST-0405", "E04", "Group 1 data operations", "S6-S7",
     "Dress-rehearsal data prepared; DQ tuned on first production runs."),
    ("ST-0501", "E05", "SAS standards & tooling", "S1-S3",
     "Prod-readiness standards published; SAS runtime obtained; static_sas upgraded to real lint."),
    ("ST-0502", "E05", "Model 1 optimization", "S2-S4",
     "Optimized code reconciles vs ABSA benchmarks; packaged per ADR-0010; code-intake green."),
    ("ST-0503", "E05", "Model 2 optimization", "S4-S6",
     "Same exit criteria as model 1."),
    ("ST-0504", "E05", "Reconciliation framework", "S4-S6",
     "Diff tool with tolerance bands + per-variable deltas; PIR-ready report template."),
    ("ST-0601", "E06", "Compute platform decision (D04)", "S3",
     "ADR records SFN+Lambda vs SageMaker choice with ABSA architecture board."),
    ("ST-0602", "E06", "Step Functions runtime execution", "S5-S6",
     "Model-1 ASL executes on real AWS in dev; compute layer built; EventBridge schedules set."),
    ("ST-0603", "E06", "Production pipeline infra + perf", "S6",
     "Prod promote done; load test meets SLA bands."),
    ("ST-0701", "E07", "Change workflow (D02)", "S5",
     "CAB/IVU mapped to registry approve route; production-change path documented."),
    ("ST-0702", "E07", "Rotation, retention & audit", "S4-S7",
     "Rotation cadence doc; S3 lifecycle policies; KMS rotation drill done; access audit pre-go-live."),
    ("ST-0801", "E08", "Dress rehearsal (full chain)", "S6",
     "Producer + verifier chain on real AWS for models 1-2; transcript archived; defects logged."),
    ("ST-0802", "E08", "Group 1 production scoring", "S7",
     "Initial scheduled runs in prod; outputs delivered; DQ green."),
    ("ST-0803", "E08", "Reconciliation & defect cycle", "S7-S8",
     "Outputs reconcile within tolerance; defects closed and re-run."),
    ("ST-0804", "E08", "PIR & ABSA sign-off", "S8",
     "PIR evidence pack submitted; written ABSA Risk Owner sign-off (THE program gate)."),
    ("ST-0901", "E09", "Dashboard tooling & build", "S4-S6",
     "D08 decided; run-status dashboard live for G1 runs."),
    ("ST-0902", "E09", "Alerting & notifications", "S5-S9",
     "Failure alerts routed (email/Slack); ABSA SPOC notification path tested."),
    ("ST-0903", "E09", "DQ / drift panels", "S8",
     "DQ + drift panels visible alongside run status."),
    ("ST-0904", "E09", "Output delivery automation (D09)", "S8-S9",
     "Signed outputs auto-delivered to ABSA with confirmation evidence; validated with recipients."),
    ("ST-1001", "E10", "Group 2 onboarding plan", "S8",
     "Per-model checklist derived from G1 lessons; wave allocation agreed."),
    ("ST-1002", "E10", "Wave 1: models 3-4", "S9", "Both models scoring in prod, reconciled, PIR'd."),
    ("ST-1003", "E10", "Wave 2: models 5-6", "S10", "Same exit criteria."),
    ("ST-1004", "E10", "Wave 3: models 7-8", "S11", "Same exit criteria."),
    ("ST-1005", "E10", "Wave 4: models 9-10 + Group 2 sign-off", "S12",
     "All 10 models live; written Group 2 sign-off."),
    ("ST-1101", "E11", "Runbooks & support model", "S11",
     "Incident/recovery/rollback runbooks; support rota + escalation matrix."),
    ("ST-1102", "E11", "Handover & go-live", "S12",
     "Handover sessions done; service review cadence scheduled; steady-state checklist complete."),
]

# Tasks: (id, story, title, role, sprint_n, est_days, deps, blocked_on, notes)
TASKS = [
    # ST-0101 Environment & platform onboarding
    ("T-0101", "ST-0101", "Clone repo, uv sync, run full 278-test suite locally", "AWS", 1, 0.5, "", "", ""),
    ("T-0102", "ST-0101", "Clone repo, uv sync, run full 278-test suite locally", "DE", 1, 0.5, "", "", ""),
    ("T-0103", "ST-0101", "Clone repo, uv sync, run full 278-test suite locally", "SAS", 1, 0.5, "", "", ""),
    ("T-0104", "ST-0101", "Clone repo, uv sync, run full 278-test suite locally", "DevOps", 1, 0.5, "", "", ""),
    ("T-0105", "ST-0101", "Run `make demo` (LocalStack chain) green locally", "AWS", 1, 0.5, "T-0101", "", ""),
    ("T-0106", "ST-0101", "Run `make demo` (LocalStack chain) green locally", "DE", 1, 0.5, "T-0102", "", ""),
    ("T-0107", "ST-0101", "Run `make demo` (LocalStack chain) green locally", "SAS", 1, 0.5, "T-0103", "", ""),
    ("T-0108", "ST-0101", "Run `make demo` (LocalStack chain) green locally", "DevOps", 1, 0.5, "T-0104", "", ""),
    ("T-0109", "ST-0101", "Host architecture walkthrough: chain-of-custody, repo tour, ADR index", "TL", 1, 1.0, "", "", "Record it for future joiners"),
    # ST-0102 Agile working agreement & board
    ("T-0110", "ST-0102", "Stand up Jira/ADO board; import this EPIC/Story/Task tree", "TL", 1, 1.0, "", "", "Backlog sheet is the import source"),
    ("T-0111", "ST-0102", "Publish Definition of Done + PR / branch-protection workflow", "TL", 1, 0.5, "", "", ""),
    ("T-0112", "ST-0102", "Ceremony calendar: daily standup, planning, review+demo, retro", "TL", 1, 0.5, "", "", ""),
    # ST-0103 ABSA dependency management
    ("T-0113", "ST-0103", "Send 7-item dependency ask-list to ABSA SPOC", "TL", 1, 0.5, "", "", "Account IDs, IAM ARNs, SAS runtime, PIR API, data movement, CAB/IVU, network"),
    ("T-0114", "ST-0103", "Stand up weekly dependency-chase cadence + escalation path", "TL", 1, 0.5, "T-0113", "", ""),
    # ST-0201 Jenkins discovery & identity
    ("T-0201", "ST-0201", "Document Jenkins topology: host, agents, executors, plugins, versions", "DevOps", 1, 1.0, "", "", "Standalone instance already running"),
    ("T-0202", "ST-0201", "Choose AWS auth path: instance profile / OIDC IdP plugin / keys+rotation", "DevOps", 1, 1.0, "T-0201", "", "Drives signing-foundation trust policy"),
    ("T-0203", "ST-0201", "Amend ADR-0011 with the standalone-Jenkins identity decision", "TL", 1, 0.5, "T-0202", "", ""),
    # ST-0202 Shared library proving ground
    ("T-0204", "ST-0202", "Register absa-ci as Global Pipeline Library", "DevOps", 1, 0.5, "T-0201", "", "ci/jenkins/ path in this repo"),
    ("T-0205", "ST-0202", "Create multibranch job for python-validate; first run", "DevOps", 1, 1.0, "T-0204", "", ""),
    ("T-0206", "ST-0202", "Verify ci/python-validate commit status lands on a GitHub PR", "DevOps", 1, 1.0, "T-0205", "", "Branch-protection sandbox check"),
    ("T-0207", "ST-0202", "Fix shared-library Groovy issues surfaced by first runs", "DevOps", 2, 2.0, "T-0206", "", "Expected: publishChecks plugin quirks, PATH handling"),
    # ST-0203 No-AWS pipelines
    ("T-0208", "ST-0203", "code-intake job live", "DevOps", 2, 0.5, "T-0207", "", ""),
    ("T-0209", "ST-0203", "terraform-validate job live (docker tflint/tfsec/checkov/gitleaks)", "DevOps", 2, 1.5, "T-0207", "", ""),
    ("T-0210", "ST-0203", "localstack-demo job live (Docker on agent, 0/1/2/3 exit-code gate)", "DevOps", 2, 2.0, "T-0207", "", "Needs Docker socket on agent"),
    ("T-0211", "ST-0203", "Wire 7 platform secrets into Jenkins credentials store", "DevOps", 2, 1.0, "T-0202", "", "Secrets Manager-backed if reachable"),
    # ST-0204 AWS-touching + cutover
    ("T-0212", "ST-0204", "pipeline-factory sign+register stages green against real AWS", "DevOps", 3, 2.0, "T-0309,T-0211", "", ""),
    ("T-0213", "ST-0204", "publish-signing-key job", "DevOps", 3, 1.0, "T-0310", "", ""),
    ("T-0214", "ST-0204", "1-week GHA-vs-Jenkins parallel run; byte-equivalence report", "DevOps", 3, 2.0, "T-0212", "", "Compare manifest digests + signatures"),
    ("T-0215", "ST-0204", "Flip branch protection to Jenkins contexts; GHA -> *.disabled.yml", "DevOps", 3, 0.5, "T-0214", "", ""),
    ("T-0216", "ST-0204", "Docs sweep: ADR-0003/0009 final edits; control-matrix rows -> Live", "TL", 3, 1.0, "T-0215", "", ""),
    # ST-0301 Account bootstrap
    ("T-0301", "ST-0301", "Module/stack review: gap notes vs real-AWS apply", "AWS", 1, 2.0, "", "", "terraform/ + account-bootstrap"),
    ("T-0302", "ST-0301", "tfvars templates per env (awaiting account IDs)", "AWS", 1, 1.0, "T-0301", "", ""),
    ("T-0303", "ST-0301", "State backend design: S3 + DynamoDB locks per account", "AWS", 1, 1.0, "T-0301", "", ""),
    ("T-0304", "ST-0301", "Apply account-bootstrap to exl-dev/stg/prod", "AWS", 2, 2.0, "T-0302", "ABSA: account IDs", "CloudTrail, GuardDuty, SecurityHub, CIS alarms"),
    ("T-0305", "ST-0301", "Apply state backends", "AWS", 2, 1.0, "T-0304", "", ""),
    # ST-0302 Landing zone & connectivity
    ("T-0306", "ST-0302", "Apply landing-zone module (dev first)", "AWS", 2, 2.0, "T-0304", "", ""),
    ("T-0307", "ST-0302", "Implement network connectivity per ABSA decision", "AWS", 3, 3.0, "T-0306", "ABSA: network choice", "VPC peering / TGW / PrivateLink"),
    ("T-0308", "ST-0302", "IP whitelisting coordination with ABSA network team", "AWS", 2, 1.0, "T-0306", "ABSA: network choice", ""),
    # ST-0303 Signing foundation
    ("T-0309", "ST-0303", "identity_provider variable in signing-foundation TF (per T-0202 decision)", "AWS", 2, 2.0, "T-0202", "", "Supports github_actions | jenkins variants during cutover"),
    ("T-0310", "ST-0303", "Apply signing stack to exl-prod; CMK + buckets + roles live", "AWS", 3, 1.0, "T-0309,T-0304", "", ""),
    ("T-0311", "ST-0303", "Run publish-key; PEM in public bucket", "AWS", 3, 0.5, "T-0310", "", ""),
    ("T-0312", "ST-0303", "Cross-account verify test with real ABSA principal", "AWS", 4, 1.0, "T-0311", "ABSA: IAM ARNs", ""),
    # ST-0304 Registry on real AWS
    ("T-0313", "ST-0304", "Lambda packaging for registry-api (adapter + artifact build)", "AWS", 3, 2.0, "T-0304", "", "Largest demo->prod gap per Phase 3 closeout"),
    ("T-0314", "ST-0304", "Finish Lambda packaging + tests", "AWS", 4, 1.0, "T-0313", "", ""),
    ("T-0315", "ST-0304", "Apply APIGW+Lambda+DynamoDB registry stack (dev) + smoke", "AWS", 4, 2.0, "T-0314", "", ""),
    ("T-0316", "ST-0304", "SigV4 register smoke from pipeline-factory", "TL", 4, 1.0, "T-0315", "", ""),
    ("T-0317", "ST-0304", "Promote registry to stg + prod", "AWS", 4, 1.0, "T-0316", "", ""),
    # ST-0305 Replication
    ("T-0318", "ST-0305", "Apply s3-replication source + destination modules", "AWS", 4, 1.5, "T-0306", "ABSA: data movement", ""),
    ("T-0319", "ST-0305", "Encrypted transfer validated end-to-end with ABSA test object", "AWS", 4, 1.0, "T-0318", "ABSA: data movement", ""),
    # ST-0401 Data contracts
    ("T-0401", "ST-0401", "Study platform-contracts schemas + PIR mapping + demo data flow", "DE", 1, 1.0, "", "", ""),
    ("T-0402", "ST-0401", "Data dictionary template (input schema, types, nullability, PIR link)", "DE", 1, 2.0, "T-0401", "", ""),
    ("T-0403", "ST-0401", "Input schemas for models 1-2", "DE", 2, 2.0, "T-0402", "ABSA: model docs", ""),
    ("T-0404", "ST-0401", "Volume/cadence matrix for all 10 models", "DE", 2, 1.0, "T-0402", "", "Daily / weekly / monthly per model"),
    # ST-0402 Ingestion
    ("T-0405", "ST-0402", "Bucket layout + partitioning convention for scoring inputs", "DE", 2, 1.0, "T-0402", "", ""),
    ("T-0406", "ST-0402", "Arrival validation job: schema check on landing", "DE", 3, 3.0, "T-0405", "", ""),
    ("T-0407", "ST-0402", "Reject / return-to-ABSA workflow for failed files", "DE", 3, 1.0, "T-0406", "", ""),
    # ST-0403 DQ framework
    ("T-0408", "ST-0403", "Volume checks: row-count expectation bands per model", "DE", 4, 2.0, "T-0406", "", ""),
    ("T-0409", "ST-0403", "Drift metric design (PSI per feature) -> D01 proposal to ABSA", "DE", 4, 2.0, "T-0406", "", "Feeds open decision D01"),
    ("T-0410", "ST-0403", "DQ report artifact published per scoring run", "DE", 5, 2.0, "T-0408", "", ""),
    # ST-0404 PIR
    ("T-0411", "ST-0404", "PIR feed/API contract session with ABSA", "DE", 5, 0.5, "", "ABSA: PIR contract", ""),
    ("T-0412", "ST-0404", "pir.yaml sync from ABSA PIR system", "DE", 5, 3.0, "T-0411", "ABSA: PIR contract", ""),
    ("T-0413", "ST-0404", "PIR coverage report on real model inputs", "DE", 6, 1.0, "T-0412", "", ""),
    # ST-0405 G1 data ops
    ("T-0414", "ST-0405", "Dress-rehearsal data preparation (models 1-2)", "DE", 6, 2.0, "T-0403", "", ""),
    ("T-0415", "ST-0405", "DQ on first production runs + threshold tuning", "DE", 7, 2.0, "T-0410", "", ""),
    # ST-0501 SAS standards & tooling
    ("T-0501", "ST-0501", "Study credit-risk-pd package + static_sas checker internals", "SAS", 1, 2.0, "", "", ""),
    ("T-0502", "ST-0501", "SAS prod-readiness standards doc (naming, macros, error handling, logging)", "SAS", 1, 2.0, "T-0501", "", ""),
    ("T-0503", "ST-0501", "Obtain SAS runtime image + license terms from ABSA", "SAS", 2, 0.5, "", "ABSA: SAS runtime", ""),
    ("T-0504", "ST-0501", "Upgrade static_sas checker from structural to real lint", "SAS", 3, 3.0, "T-0503", "ABSA: SAS runtime", "Pairs with TL on checker plumbing"),
    # ST-0502 Model 1
    ("T-0505", "ST-0502", "Model-1 dev-code review vs benchmark spec", "SAS", 2, 2.0, "T-0502", "ABSA: model docs", ""),
    ("T-0506", "ST-0502", "Benchmark spec gap notes; clarify with ABSA model owner", "SAS", 2, 1.0, "T-0505", "", ""),
    ("T-0507", "ST-0502", "Optimize + standardize model-1 scoring code", "SAS", 3, 4.0, "T-0505", "", ""),
    ("T-0508", "ST-0502", "Regression harness vs ABSA benchmark outputs", "SAS", 4, 2.0, "T-0507", "", ""),
    ("T-0509", "ST-0502", "Package model-1 per ADR-0010; code-intake validate green", "SAS", 4, 1.0, "T-0508", "", ""),
    # ST-0503 Model 2
    ("T-0510", "ST-0503", "Model-2 dev-code review vs benchmark spec", "SAS", 4, 2.0, "T-0502", "", ""),
    ("T-0511", "ST-0503", "Optimize + standardize model-2 scoring code", "SAS", 5, 4.0, "T-0510", "", ""),
    ("T-0512", "ST-0503", "Model-2 regression harness", "SAS", 5, 2.0, "T-0511", "", ""),
    ("T-0513", "ST-0503", "Package model-2 + code-intake green", "SAS", 6, 1.0, "T-0512", "", ""),
    # ST-0504 Reconciliation framework
    ("T-0514", "ST-0504", "Output diff tool: tolerance bands, per-variable deltas", "SAS", 4, 2.0, "T-0508", "", "Co-design with DE"),
    ("T-0515", "ST-0504", "Reconciliation report template (PIR-ready)", "SAS", 6, 1.0, "T-0514", "", ""),
    # ST-0601 Compute decision
    ("T-0601", "ST-0601", "ADR: D04 compute choice (SFN+Lambda vs SageMaker) w/ architecture board", "AWS", 3, 1.0, "", "", "Gates compute build in S5"),
    # ST-0602 SFN runtime
    ("T-0602", "ST-0602", "Deploy real ASL standard-batch for model-1 (dev)", "AWS", 5, 3.0, "T-0601,T-0509", "", ""),
    ("T-0603", "ST-0602", "Build compute layer (Lambda container / SM Processing per D04)", "AWS", 5, 4.0, "T-0601", "", ""),
    ("T-0604", "ST-0602", "EventBridge schedules per model cadence", "AWS", 6, 1.0, "T-0602", "", ""),
    # ST-0603 Prod infra + perf
    ("T-0605", "ST-0603", "Promote pipeline infra to prod", "AWS", 6, 2.0, "T-0602", "", ""),
    ("T-0606", "ST-0603", "Load/perf test vs SLA bands", "AWS", 6, 2.0, "T-0605", "", ""),
    # ST-0701 Change workflow
    ("T-0701", "ST-0701", "Map CAB/IVU contract onto registry approve/retire routes (D02)", "TL", 5, 2.0, "", "ABSA: CAB/IVU contract", ""),
    # ST-0702 Rotation/retention/audit
    ("T-0702", "ST-0702", "Rotation cadence doc: Jenkins creds, bot PAT, registrar tokens (D03)", "DevOps", 4, 1.0, "T-0211", "", ""),
    ("T-0703", "ST-0702", "S3 lifecycle/retention policies per retention rules", "AWS", 7, 1.0, "T-0318", "", ""),
    ("T-0704", "ST-0702", "KMS rotation drill per docs/runbooks/kms-key-rotation.md", "DevOps", 7, 1.0, "T-0311", "", "AWS supports 0.5d"),
    ("T-0705", "ST-0702", "Pre-go-live access review + least-privilege audit", "AWS", 7, 1.0, "T-0310", "", ""),
    # ST-0801 Dress rehearsal
    ("T-0801", "ST-0801", "Dress rehearsal orchestration: full chain on real AWS, models 1-2", "TL", 6, 2.0, "T-0513,T-0602,T-0317", "", "Producer + verifier, archived transcript"),
    ("T-0802", "ST-0801", "Dress rehearsal infra support + fixes", "AWS", 6, 2.0, "T-0801", "", ""),
    ("T-0803", "ST-0801", "Dress rehearsal model runs + output checks", "SAS", 6, 2.0, "T-0801", "", ""),
    ("T-0804", "ST-0801", "Dress rehearsal CI/pipeline ops", "DevOps", 6, 1.0, "T-0801", "", ""),
    # ST-0802 G1 production scoring
    ("T-0805", "ST-0802", "Initial production scoring runs (models 1-2)", "AWS", 7, 2.0, "T-0801", "", ""),
    ("T-0806", "ST-0802", "Production run monitoring + incident handling", "DevOps", 7, 1.0, "T-0805", "", ""),
    # ST-0803 Reconciliation & defects
    ("T-0807", "ST-0803", "Reconcile G1 outputs vs benchmarks (tolerance report)", "SAS", 7, 3.0, "T-0805,T-0514", "", ""),
    ("T-0808", "ST-0803", "Defect triage + fix cycle", "SAS", 7, 3.0, "T-0807", "", "TL triages 1d"),
    ("T-0809", "ST-0803", "Defect triage facilitation + ABSA comms", "TL", 7, 1.0, "T-0807", "", ""),
    ("T-0810", "ST-0803", "Defect closure + re-run + final reconciliation", "SAS", 8, 2.0, "T-0808", "", ""),
    # ST-0804 PIR & sign-off
    ("T-0811", "ST-0804", "PIR evidence pack (reconciliation, DQ, audit trail)", "SAS", 8, 2.0, "T-0810", "", ""),
    ("T-0812", "ST-0804", "PIR data evidence: lineage + DQ reports", "DE", 8, 1.0, "T-0810", "", ""),
    ("T-0813", "ST-0804", "ABSA sign-off review meeting + written sign-off", "TL", 8, 2.0, "T-0811", "", "*** THE program gate ***"),
    ("T-0814", "ST-0804", "G1 production schedules confirmed live", "AWS", 8, 0.5, "T-0813", "", ""),
    # ST-0901 Dashboards
    ("T-0901", "ST-0901", "D08 tooling decision: CloudWatch / Grafana / QuickSight", "DevOps", 4, 1.5, "", "", ""),
    ("T-0902", "ST-0901", "Run-status dashboard build (runs, exceptions, durations)", "DevOps", 6, 3.0, "T-0901", "", ""),
    # ST-0902 Alerting
    ("T-0903", "ST-0902", "Alert routing: SNS -> email/Slack; severity mapping", "DevOps", 5, 2.0, "T-0901", "", ""),
    ("T-0904", "ST-0902", "Failure notifications to ABSA SPOC path tested", "DevOps", 9, 1.0, "T-0903", "", ""),
    # ST-0903 DQ panels
    ("T-0905", "ST-0903", "DQ + drift panels alongside run status", "DE", 8, 2.0, "T-0410,T-0902", "", ""),
    # ST-0904 Delivery automation
    ("T-0906", "ST-0904", "Automated signed output delivery to ABSA + confirmation evidence", "DevOps", 8, 2.0, "T-0319", "ABSA: data movement", ""),
    ("T-0907", "ST-0904", "Delivery validation with ABSA recipients", "DevOps", 9, 1.0, "T-0906", "", ""),
    ("T-0908", "ST-0904", "Dashboard access + validation with ABSA recipients", "DevOps", 9, 1.0, "T-0902", "", ""),
    # ST-1001 G2 plan
    ("T-1001", "ST-1001", "Group 2 onboarding plan + per-model checklist from G1 lessons", "TL", 8, 1.0, "T-0813", "", ""),
    # ST-1002 Wave 1 (models 3-4)
    ("T-1002", "ST-1002", "Models 3-4: contracts + input schemas", "DE", 9, 1.5, "T-1001", "", ""),
    ("T-1003", "ST-1002", "Models 3-4: review + optimize + package", "SAS", 9, 5.0, "T-1001", "", ""),
    ("T-1004", "ST-1002", "Models 3-4: pipeline configs + schedules", "AWS", 9, 1.0, "T-1003", "", ""),
    ("T-1005", "ST-1002", "Models 3-4: CI + monitoring wiring", "DevOps", 9, 0.5, "T-1003", "", ""),
    ("T-1006", "ST-1002", "Models 3-4: reconcile + PIR", "SAS", 9, 1.5, "T-1004", "", ""),
    ("T-1007", "ST-1002", "Models 3-4: DQ verification", "DE", 9, 0.5, "T-1004", "", ""),
    # ST-1003 Wave 2 (models 5-6)
    ("T-1008", "ST-1003", "Models 5-6: contracts + input schemas", "DE", 10, 1.5, "T-1001", "", ""),
    ("T-1009", "ST-1003", "Models 5-6: review + optimize + package", "SAS", 10, 5.0, "T-1001", "", ""),
    ("T-1010", "ST-1003", "Models 5-6: pipeline configs + schedules", "AWS", 10, 1.0, "T-1009", "", ""),
    ("T-1011", "ST-1003", "Models 5-6: CI + monitoring wiring", "DevOps", 10, 0.5, "T-1009", "", ""),
    ("T-1012", "ST-1003", "Models 5-6: reconcile + PIR", "SAS", 10, 1.5, "T-1010", "", ""),
    ("T-1013", "ST-1003", "Models 5-6: DQ verification", "DE", 10, 0.5, "T-1010", "", ""),
    # ST-1004 Wave 3 (models 7-8)
    ("T-1014", "ST-1004", "Models 7-8: contracts + input schemas", "DE", 11, 1.5, "T-1001", "", ""),
    ("T-1015", "ST-1004", "Models 7-8: review + optimize + package", "SAS", 11, 5.0, "T-1001", "", ""),
    ("T-1016", "ST-1004", "Models 7-8: pipeline configs + schedules", "AWS", 11, 1.0, "T-1015", "", ""),
    ("T-1017", "ST-1004", "Models 7-8: CI + monitoring wiring", "DevOps", 11, 0.5, "T-1015", "", ""),
    ("T-1018", "ST-1004", "Models 7-8: reconcile + PIR", "SAS", 11, 1.5, "T-1016", "", ""),
    ("T-1019", "ST-1004", "Models 7-8: DQ verification", "DE", 11, 0.5, "T-1016", "", ""),
    # ST-1005 Wave 4 (models 9-10) + sign-off
    ("T-1020", "ST-1005", "Models 9-10: contracts + input schemas", "DE", 12, 1.5, "T-1001", "", ""),
    ("T-1021", "ST-1005", "Models 9-10: review + optimize + package", "SAS", 12, 5.0, "T-1001", "", ""),
    ("T-1022", "ST-1005", "Models 9-10: pipeline configs + schedules", "AWS", 12, 1.0, "T-1021", "", ""),
    ("T-1023", "ST-1005", "Models 9-10: CI + monitoring wiring", "DevOps", 12, 0.5, "T-1021", "", ""),
    ("T-1024", "ST-1005", "Models 9-10: reconcile + PIR", "SAS", 12, 1.5, "T-1022", "", ""),
    ("T-1025", "ST-1005", "Group 2 sign-off pack + ABSA meeting", "TL", 12, 2.0, "T-1024", "", "Closes initial onboarding scope"),
    # ST-1101 Runbooks & support
    ("T-1101", "ST-1101", "Runbooks: incident, recovery, rollback per model family", "DevOps", 11, 3.0, "T-0806", "", ""),
    ("T-1102", "ST-1101", "Support rota + escalation matrix", "TL", 11, 1.0, "T-1101", "", ""),
    ("T-1103", "ST-1101", "Cost review + right-sizing pass", "AWS", 11, 2.0, "T-0814", "", ""),
    # ST-1102 Handover & go-live
    ("T-1104", "ST-1102", "Quarterly service review template + first review scheduled", "TL", 12, 1.0, "T-1102", "", ""),
    ("T-1105", "ST-1102", "Handover sessions: ops team + ABSA", "TL", 12, 2.0, "T-1101", "", ""),
    ("T-1106", "ST-1102", "Handover support + docs finalization", "DevOps", 12, 1.0, "T-1105", "", ""),
    ("T-1107", "ST-1102", "Steady-state go-live checklist + cutover", "TL", 12, 1.0, "T-1105", "", "Go-live ~Dec 1, 2026"),
]

PREREQS_INTERNAL = [
    ("PRE-01", "Jira/ADO project + board created", "TL", "Before S1 planning"),
    ("PRE-02", "GitHub repo access for all 4 engineers (write) + CODEOWNERS updated", "TL", "Before S1 day 1"),
    ("PRE-03", "Jenkins admin access for DevOps engineer", "DevOps", "Before S1 day 1"),
    ("PRE-04", "AWS sandbox account access for AWS engineer", "AWS", "Before S1 day 1"),
    ("PRE-05", "Dev machines: uv, Docker Desktop, Terraform 1.9.5, Python 3.12", "All", "S1 day 1-2"),
    ("PRE-06", "Slack/Teams channel + meeting invites for ceremonies", "TL", "Before S1 planning"),
    ("PRE-07", "SAS desktop/dev license for SAS developer (interim until ABSA runtime)", "SAS", "S1"),
]

PREREQS_ABSA = [
    ("DEP-01", "AWS account IDs (3 EXL accounts + ABSA receiving)", "T-0304 (S2)", "Bootstrap blocked; everything downstream slips day-for-day"),
    ("DEP-02", "IAM principal ARNs needing kms:Verify / s3:GetObject", "T-0312 (S4)", "Cross-account verify untestable"),
    ("DEP-03", "SAS runtime Docker image + license terms", "T-0503 (S2), T-0504 (S3)", "SAS validation stays structural-only"),
    ("DEP-04", "PIR system API/feed contract", "T-0411 (S5)", "pir.yaml stays hand-maintained"),
    ("DEP-05", "Data movement decision: S3 replication vs SFTP", "T-0318 (S4), T-0906 (S8)", "Transfer + delivery automation blocked"),
    ("DEP-06", "CAB/IVU API contract", "T-0701 (S5)", "Change workflow stays manual"),
    ("DEP-07", "Network connectivity choice: peering / TGW / PrivateLink", "T-0307 (S3)", "Data plane to ABSA blocked"),
    ("DEP-08", "Approved model docs + code + benchmarks (models 1-2 first)", "T-0403/T-0505 (S2)", "SAS + DE work on models blocked"),
]


# ---------- Validation ----------

def validate_capacity() -> list[str]:
    load: dict[tuple[str, int], float] = {}
    for t in TASKS:
        key = (t[3], t[4])
        load[key] = load.get(key, 0.0) + t[5]
    warnings = []
    for (role, sprint), days in sorted(load.items(), key=lambda x: (x[0][1], x[0][0])):
        if days > CAPACITY[role]:
            warnings.append(f"OVERLOAD {role} S{sprint}: {days:.1f}d > {CAPACITY[role]:.1f}d cap")
    return warnings


# ---------- Sheet builders ----------

def _header(ws, row, cols):
    for i, label in enumerate(cols, start=1):
        c = ws.cell(row=row, column=i, value=label)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = ALIGN_CENTER
        c.border = BORDER_THIN


def _widths(ws, widths):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def build_readme(wb):
    ws = wb.create_sheet("README")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "ABSA x EXL — Agile Sprint Plan"
    ws["A1"].font = FONT_TITLE
    lines = [
        "",
        "Anchoring: Sprint 1 starts Monday 2026-06-15. 12 sprints x 2 weeks ~ 6 months.",
        "Group 1 ABSA sign-off targeted end of Sprint 8 (2026-10-02). Steady-state go-live ~2026-12-01.",
        "",
        "Team & capacity (effort-days per 2-week sprint, 10 working days x 0.8 focus factor):",
        "  AWS    — AWS / MLOps Engineer       — 8.0 d/sprint",
        "  DE     — Data Engineer              — 8.0 d/sprint",
        "  SAS    — SAS Developer              — 8.0 d/sprint",
        "  DevOps — DevOps Engineer            — 8.0 d/sprint",
        "  TL     — Tech Lead (Vishnu)         — 6.0 d/sprint (splits with program management)",
        "",
        "How to use:",
        "  1. 'Backlog' is the source of truth: EPIC -> Story -> Task with role, sprint, estimate.",
        "     Import into Jira (CSV) or mirror manually; IDs are stable.",
        "  2. 'Sprint Plan' shows goal + milestone per sprint and per-role load (formula-driven).",
        "  3. 'Role Load' is the capacity heat grid — red means overloaded, fix before planning.",
        "  4. 'Prerequisites' lists internal setup + the 8 ABSA dependencies with impact points.",
        "  5. Update Status on Backlog as work moves; Dashboard recalculates.",
        "",
        "Context: the platform itself (registry, pipeline-factory, signer, code-intake, LocalStack demo)",
        "is already built and CI-regression-tested — see docs/phase-3-closeout.md. This plan covers",
        "real-AWS deployment, Jenkins CI migration, model onboarding (10 models), and go-live.",
    ]
    for i, line in enumerate(lines, start=2):
        ws.cell(row=i, column=1, value=line).font = FONT_BODY
    ws.column_dimensions["A"].width = 110


def build_backlog(wb):
    ws = wb.create_sheet("Backlog")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Backlog — EPIC / Story / Task"
    ws["A1"].font = FONT_TITLE

    cols = ["Type", "ID", "Parent", "Epic", "Title", "Role", "Sprint", "Est (d)",
            "Depends On", "Blocked On (ABSA)", "Status", "Acceptance / Notes"]
    _header(ws, 3, cols)

    stories_by_epic: dict[str, list] = {}
    for s in STORIES:
        stories_by_epic.setdefault(s[1], []).append(s)
    tasks_by_story: dict[str, list] = {}
    for t in TASKS:
        tasks_by_story.setdefault(t[1], []).append(t)

    row = 4
    for epic in EPICS:
        eid, etitle, eowner, esprints, eobj = epic
        vals = ["EPIC", eid, "", eid, f"{etitle} — {eobj}", eowner, esprints, "", "", "", "", ""]
        for ci, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=ci, value=v)
            c.font = FONT_EPIC
            c.fill = FILL_EPIC
            c.alignment = ALIGN_LEFT
            c.border = BORDER_THIN
        row += 1
        for st in stories_by_epic.get(eid, []):
            sid, _, stitle, ssprint, sacc = st
            vals = ["Story", sid, eid, eid, stitle, "", ssprint, "", "", "", "", sacc]
            for ci, v in enumerate(vals, start=1):
                c = ws.cell(row=row, column=ci, value=v)
                c.font = FONT_STORY
                c.fill = FILL_STORY
                c.alignment = ALIGN_LEFT
                c.border = BORDER_THIN
            row += 1
            for t in tasks_by_story.get(sid, []):
                tid, _, ttitle, trole, tsprint, test_d, tdeps, tblocked, tnotes = t
                vals = ["Task", tid, sid, eid, ttitle, trole, f"S{tsprint}", test_d,
                        tdeps, tblocked, "Planned", tnotes]
                for ci, v in enumerate(vals, start=1):
                    c = ws.cell(row=row, column=ci, value=v)
                    c.font = FONT_BODY
                    c.alignment = ALIGN_LEFT
                    c.border = BORDER_THIN
                if tblocked:
                    ws.cell(row=row, column=10).fill = FILL_BLOCKED
                row += 1

    _widths(ws, {"A": 7, "B": 9, "C": 9, "D": 6, "E": 62, "F": 8, "G": 8,
                 "H": 8, "I": 16, "J": 20, "K": 10, "L": 48})
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:L{row - 1}"
    return row - 1


def build_sprint_plan(wb):
    ws = wb.create_sheet("Sprint Plan")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Sprint Plan — 12 x 2-week sprints"
    ws["A1"].font = FONT_TITLE

    cols = ["Sprint", "Start", "End", "Goal", "Milestone"] + [f"{r} (d)" for r in ROLES] + ["Total (d)"]
    _header(ws, 3, cols)

    row = 4
    for n in range(1, N_SPRINTS + 1):
        s, e = sprint_dates(n)
        goal, milestone = SPRINT_GOALS[n]
        ws.cell(row=row, column=1, value=f"S{n}").font = FONT_BODY_BOLD
        ws.cell(row=row, column=2, value=s).number_format = "yyyy-mm-dd"
        ws.cell(row=row, column=3, value=e).number_format = "yyyy-mm-dd"
        ws.cell(row=row, column=4, value=goal).font = FONT_BODY
        mc = ws.cell(row=row, column=5, value=milestone)
        mc.font = FONT_BODY_BOLD
        if milestone:
            for ci in range(1, 12):
                ws.cell(row=row, column=ci).fill = FILL_MILESTONE
        for ri, role in enumerate(ROLES):
            col = 6 + ri
            ws.cell(row=row, column=col,
                    value=f'=SUMIFS(Backlog!$H:$H,Backlog!$F:$F,"{role}",Backlog!$G:$G,"S{n}",Backlog!$A:$A,"Task")')
        ws.cell(row=row, column=11, value=f"=SUM(F{row}:J{row})").font = FONT_BODY_BOLD
        for ci in range(1, 12):
            c = ws.cell(row=row, column=ci)
            c.border = BORDER_THIN
            c.alignment = ALIGN_LEFT
        row += 1

    _widths(ws, {"A": 7, "B": 11, "C": 11, "D": 72, "E": 28,
                 "F": 8, "G": 8, "H": 8, "I": 10, "J": 8, "K": 9})
    ws.freeze_panes = "A4"


def build_role_load(wb):
    ws = wb.create_sheet("Role Load")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Role Load vs Capacity (effort-days per sprint)"
    ws["A1"].font = FONT_TITLE

    cols = ["Role", "Capacity"] + [f"S{n}" for n in range(1, N_SPRINTS + 1)]
    _header(ws, 3, cols)

    row = 4
    for role in ROLES:
        ws.cell(row=row, column=1, value=f"{role} — {ROLE_NAMES[role]}").font = FONT_BODY_BOLD
        ws.cell(row=row, column=2, value=CAPACITY[role]).font = FONT_BODY
        for n in range(1, N_SPRINTS + 1):
            col = 2 + n
            ws.cell(row=row, column=col,
                    value=f'=SUMIFS(Backlog!$H:$H,Backlog!$F:$F,"{role}",Backlog!$G:$G,"S{n}",Backlog!$A:$A,"Task")')
        for ci in range(1, 15):
            c = ws.cell(row=row, column=ci)
            c.border = BORDER_THIN
            c.alignment = ALIGN_CENTER if ci > 1 else ALIGN_LEFT
        row += 1

    # Conditional fills: red when load exceeds capacity, green when within
    data_range = f"C4:N{row - 1}"
    ws.conditional_formatting.add(
        data_range,
        FormulaRule(formula=["C4>$B4"], fill=FILL_BLOCKED, stopIfTrue=True),
    )
    ws.conditional_formatting.add(
        data_range,
        FormulaRule(formula=["AND(C4>0,C4<=$B4)"], fill=FILL_OK),
    )

    ws.cell(row=row + 1, column=1,
            value="Red = over capacity (re-plan). Green = loaded within capacity. Blank/0 = free.").font = FONT_BODY

    _widths(ws, {"A": 34, "B": 10})
    for n in range(1, N_SPRINTS + 1):
        ws.column_dimensions[chr(ord("C") + n - 1)].width = 7


def build_prereqs(wb):
    ws = wb.create_sheet("Prerequisites")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Prerequisites & Dependencies"
    ws["A1"].font = FONT_TITLE

    ws["A3"] = "Internal — must be in place before / during Sprint 1"
    ws["A3"].font = FONT_BODY_BOLD
    _header(ws, 4, ["ID", "Item", "Owner", "When"])
    row = 5
    for p in PREREQS_INTERNAL:
        for ci, v in enumerate(p, start=1):
            c = ws.cell(row=row, column=ci, value=v)
            c.font = FONT_BODY
            c.border = BORDER_THIN
            c.alignment = ALIGN_LEFT
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Blocked on ABSA — the 8-item dependency register").font = FONT_BODY_BOLD
    row += 1
    _header(ws, row, ["ID", "Dependency", "First impacted task (sprint)", "Impact if late"])
    row += 1
    for p in PREREQS_ABSA:
        for ci, v in enumerate(p, start=1):
            c = ws.cell(row=row, column=ci, value=v)
            c.font = FONT_BODY
            c.border = BORDER_THIN
            c.alignment = ALIGN_LEFT
        ws.cell(row=row, column=1).fill = FILL_BLOCKED
        row += 1

    _widths(ws, {"A": 9, "B": 58, "C": 26, "D": 52})


def build_dashboard(wb):
    ws = wb.create_sheet("Dashboard")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Delivery Dashboard"
    ws["A1"].font = FONT_TITLE

    ws["A3"] = "Tasks by Status"
    ws["A3"].font = FONT_BODY_BOLD
    _header(ws, 4, ["Status", "Count"])
    statuses = ["Planned", "In Progress", "Done", "Blocked"]
    row = 5
    for s in statuses:
        ws.cell(row=row, column=1, value=s).font = FONT_BODY
        ws.cell(row=row, column=2,
                value=f'=COUNTIFS(Backlog!$K:$K,"{s}",Backlog!$A:$A,"Task")')
        for ci in (1, 2):
            ws.cell(row=row, column=ci).border = BORDER_THIN
        row += 1

    ws["D3"] = "Effort by Role (d)"
    ws["D3"].font = FONT_BODY_BOLD
    for i, label in enumerate(["Role", "Days"], start=4):
        c = ws.cell(row=4, column=i, value=label)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.border = BORDER_THIN
    row = 5
    for role in ROLES:
        ws.cell(row=row, column=4, value=role).font = FONT_BODY
        ws.cell(row=row, column=5,
                value=f'=SUMIFS(Backlog!$H:$H,Backlog!$F:$F,"{role}",Backlog!$A:$A,"Task")')
        for ci in (4, 5):
            ws.cell(row=row, column=ci).border = BORDER_THIN
        row += 1

    ws["A12"] = "Tasks + Effort by Epic"
    ws["A12"].font = FONT_BODY_BOLD
    _header(ws, 13, ["Epic", "Title", "Tasks", "Effort (d)", "Done"])
    row = 14
    for eid, etitle, _, _, _ in EPICS:
        ws.cell(row=row, column=1, value=eid).font = FONT_BODY_BOLD
        ws.cell(row=row, column=2, value=etitle).font = FONT_BODY
        ws.cell(row=row, column=3,
                value=f'=COUNTIFS(Backlog!$D:$D,"{eid}",Backlog!$A:$A,"Task")')
        ws.cell(row=row, column=4,
                value=f'=SUMIFS(Backlog!$H:$H,Backlog!$D:$D,"{eid}",Backlog!$A:$A,"Task")')
        ws.cell(row=row, column=5,
                value=f'=COUNTIFS(Backlog!$D:$D,"{eid}",Backlog!$A:$A,"Task",Backlog!$K:$K,"Done")')
        for ci in range(1, 6):
            ws.cell(row=row, column=ci).border = BORDER_THIN
        row += 1

    _widths(ws, {"A": 9, "B": 38, "C": 8, "D": 10, "E": 8, "F": 5, "G": 10, "H": 8})


def main():
    warnings = validate_capacity()
    if warnings:
        print("CAPACITY WARNINGS:")
        for w in warnings:
            print(" ", w)
        raise SystemExit(1)

    # Print load table for the log
    print("Per-role load (d/sprint):")
    header = "role   " + " ".join(f"S{n:<4}" for n in range(1, N_SPRINTS + 1))
    print(header)
    for role in ROLES:
        cells = []
        for n in range(1, N_SPRINTS + 1):
            days = sum(t[5] for t in TASKS if t[3] == role and t[4] == n)
            cells.append(f"{days:<5.1f}")
        print(f"{role:<6} " + " ".join(cells) + f"  (cap {CAPACITY[role]})")

    repo_root = Path(__file__).resolve().parent.parent
    out = repo_root / "docs" / "absa-exl-agile-plan.xlsx"

    wb = Workbook()
    wb.remove(wb.active)
    build_readme(wb)
    build_backlog(wb)
    build_sprint_plan(wb)
    build_role_load(wb)
    build_prereqs(wb)
    build_dashboard(wb)
    wb.save(out)
    n_tasks = len(TASKS)
    n_stories = len(STORIES)
    print(f"\nWrote {out}")
    print(f"  {len(EPICS)} epics, {n_stories} stories, {n_tasks} tasks, "
          f"{sum(t[5] for t in TASKS):.1f} effort-days across {N_SPRINTS} sprints")


if __name__ == "__main__":
    main()
