"""Render AWS architecture diagrams for the ABSA x EXL Model Hosting platform.

Uses the `diagrams` library (graphviz backend). Produces 4 focused section
diagrams as PNGs under docs/architecture/ rather than one unreadable mega-diagram:

  01-platform-overview   - cross-account topology + both tracks + security baseline
  02-track-a-onboarding  - Code Intake -> Sign -> Register -> Pipeline Factory
  03-track-b-scoring     - scheduled scoring -> compute -> DQ -> sign -> deliver
  04-chain-of-custody    - KMS asymmetric signing + cross-account verification

Run: `uv run --with diagrams python scripts/build_aws_diagrams.py`
Requires graphviz `dot` on PATH.
"""

from __future__ import annotations

import os
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECR, Fargate, Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.general import General, Users
from diagrams.aws.integration import Eventbridge, SNS, StepFunctions
from diagrams.aws.management import Cloudtrail, Cloudwatch, Organizations
from diagrams.aws.ml import Sagemaker
from diagrams.aws.network import APIGateway, TransitGateway
from diagrams.aws.security import Guardduty, IAMRole, KMS, SecurityHub
from diagrams.aws.storage import S3
from diagrams.onprem.ci import Jenkins

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture"
OUT.mkdir(parents=True, exist_ok=True)

# Edge colour conventions (from the AWS-diagram skill)
HTTP = "#0066CC"   # HTTPS / API
DATA = "#009900"   # data access / movement
SEC = "#DD344C"    # signing / verification / security
GRAY = "#545B64"   # internal / default
DASH = "#999999"   # replication / monitoring

GRAPH_ATTR = {
    "fontsize": "26",
    "bgcolor": "#FFFFFF",
    "pad": "0.6",
    "nodesep": "0.55",
    "ranksep": "0.8",
    "fontname": "Helvetica",
    "labelloc": "t",
    "fontcolor": "#232F3E",
    "dpi": "180",
}

ABSA = {"bgcolor": "#FDECEA", "pencolor": "#DD344C", "style": "rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "16"}
EXL = {"bgcolor": "#EAF2FB", "pencolor": "#147EBA", "style": "rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "16"}
ONBOARD = {"bgcolor": "#FFF7EF", "pencolor": "#ED7100", "style": "rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "14"}
SCORE = {"bgcolor": "#E9F3E6", "pencolor": "#248814", "style": "rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "14"}
DATAC = {"bgcolor": "#EDE7F6", "pencolor": "#3F48CC", "style": "rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "14"}
SECC = {"bgcolor": "#F8F8F8", "pencolor": "#232F3E", "style": "dashed,rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "14"}
CICD = {"bgcolor": "#F3EAF8", "pencolor": "#8C4FFF", "style": "dashed,rounded", "penwidth": "2", "fontname": "Helvetica", "fontsize": "14"}


def overview():
    with Diagram(
        "ABSA x EXL Model Hosting - Platform Overview",
        filename=str(OUT / "01-platform-overview"),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
    ):
        with Cluster("ABSA Trust Boundary (source account)", graph_attr=ABSA):
            devs = Users("Model developers")
            src = S3("Model-ready data +\nsigned code\n(raw PII stays in ABSA)")
            pir = General("PIR system\n(input register)")
            cab = General("CAB / IVU\ngovernance")
            absa_verify = IAMRole("ABSA verifier\nprincipal")

        with Cluster("EXL AWS - exl-prod (eu-west-1)", graph_attr=EXL):
            with Cluster("Track A - Onboarding & Pipeline Factory", graph_attr=ONBOARD):
                intake = Lambda("Code Intake\n(5 checkers)")
                factory = Lambda("Pipeline Factory\n(ASL + Terraform)")
                signer = KMS("Manifest Signer\n(KMS asymmetric)")

            with Cluster("Registry", graph_attr=DATAC):
                api = APIGateway("Registry API\n(SigV4)")
                reg_fn = Lambda("Registry\nLambda")
                reg_db = Dynamodb("Registry +\naudit (DynamoDB)")
                api >> Edge(color=GRAY) >> reg_fn >> Edge(color=DATA) >> reg_db

            with Cluster("Track B - Scoring Runtime", graph_attr=SCORE):
                sched = Eventbridge("EventBridge\nschedule")
                sfn = StepFunctions("Step Functions\n(ASL)")
                compute = Lambda("Scoring compute\n(Lambda / SageMaker)")
                sched >> Edge(color=GRAY) >> sfn >> Edge(color=GRAY) >> compute

            with Cluster("Artifacts (S3)", graph_attr=DATAC):
                signed = S3("Signed\nmanifests")
                pubkeys = S3("Public keys\n(PEM)")
                scoredata = S3("Scoring I/O +\nsigned outputs")

            with Cluster("Security baseline (per account)", graph_attr=SECC):
                Cloudtrail("CloudTrail")
                Guardduty("GuardDuty")
                SecurityHub("Security Hub")

        # Cross-boundary + key internal flows
        devs >> Edge(color=GRAY) >> src
        src >> Edge(color=DATA, style="dashed", label="model-ready data (no raw PII), KMS") >> scoredata
        intake >> Edge(color=GRAY) >> signer >> Edge(color=SEC, label="kms:Sign") >> signed
        signed >> Edge(color=GRAY) >> factory >> Edge(color=HTTP, label="SigV4 register") >> api
        compute >> Edge(color=DATA) >> scoredata
        signer >> Edge(color=SEC, label="publish PEM") >> pubkeys
        pubkeys >> Edge(color=SEC, style="dashed", label="cross-account read") >> absa_verify
        scoredata >> Edge(color=DATA, style="dashed", label="signed outputs -> ABSA") >> absa_verify
        pir >> Edge(color=GRAY, style="dashed") >> intake
        cab >> Edge(color=GRAY, style="dashed", label="approve") >> reg_fn


def track_a():
    with Diagram(
        "Track A - Model Onboarding & Pipeline Factory (one-time per model)",
        filename=str(OUT / "02-track-a-onboarding"),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
    ):
        with Cluster("ABSA", graph_attr=ABSA):
            pkg = S3("Signed code\npackage")
            devdoc = General("Model dev\ndocumentation")

        with Cluster("EXL exl-prod", graph_attr=EXL):
            with Cluster("Code Intake", graph_attr=ONBOARD):
                intake = Lambda("validate\n(static_python, static_sas,\nschema, tests, pir)")
                manifest = General("Unsigned\nmanifest.json")
                intake >> Edge(color=GRAY) >> manifest

            with Cluster("Manifest Signer", graph_attr=SECC):
                cmk = KMS("Asymmetric CMK\n(RSA-3072 SIGN_VERIFY)")
                signed = S3("Signed manifest\n(S3)")
                cmk >> Edge(color=SEC, label="kms:Sign") >> signed

            with Cluster("Pipeline Factory", graph_attr=ONBOARD):
                gen = Lambda("Generate ASL +\nTerraform stub")
                tf = General("Pipeline manifest\n+ registration.json")
                gen >> Edge(color=GRAY) >> tf

            with Cluster("Impl Doc Generator (IDG, ADR-0012)", graph_attr=SECC):
                idg = Lambda("Impl Doc Generator\n(facts + LLM draft)")
                llm = General("Azure OpenAI /\nAnthropic (adapter)")
                impldoc = General("implementation.md\n(human-approved)")
                idg >> Edge(color=SEC, label="code+docs+metadata\n(no raw data / PII)") >> llm
                llm >> Edge(color=GRAY) >> idg
                idg >> Edge(color=GRAY) >> impldoc

            with Cluster("Registry", graph_attr=DATAC):
                api = APIGateway("Registry API")
                reg_fn = Lambda("Approval state\nmachine")
                reg_db = Dynamodb("Record +\naudit log")
                api >> Edge(color=GRAY) >> reg_fn >> Edge(color=DATA) >> reg_db

        pkg >> Edge(color=DATA, style="dashed", label="S3 replication") >> intake
        manifest >> Edge(color=SEC, label="sign") >> cmk
        signed >> Edge(color=GRAY, label="upstream_ref by digest") >> gen
        devdoc >> Edge(color=GRAY, label="dev doc") >> idg
        tf >> Edge(color=GRAY, label="pipeline facts") >> idg
        tf >> Edge(color=HTTP, label="SigV4 POST") >> api
        impldoc >> Edge(color=HTTP, label="implementation_doc_ref") >> api


def track_b():
    with Diagram(
        "Track B - Scoring Runtime & Output Delivery (recurring)",
        filename=str(OUT / "03-track-b-scoring"),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
    ):
        with Cluster("EXL exl-prod", graph_attr=EXL):
            with Cluster("Orchestration", graph_attr=SCORE):
                sched = Eventbridge("EventBridge\n(per-model cadence)")
                sfn = StepFunctions("Step Functions\n(ASL pipeline)")
                sched >> Edge(color=GRAY) >> sfn

            with Cluster("Compute", graph_attr=ONBOARD):
                compute = Lambda("Scoring compute\n(Lambda container)")
                sm = Sagemaker("or SageMaker\nProcessing")

            with Cluster("Data + Quality", graph_attr=DATAC):
                indata = S3("Scoring input\n(model-ready, replicated)")
                dq = Lambda("DQ checks\n(volume, PSI drift)")
                outdata = S3("Scoring outputs")

            with Cluster("Sign + Monitor", graph_attr=SECC):
                signer = KMS("Manifest Signer")
                signed_out = S3("Signed outputs")
                cw = Cloudwatch("CloudWatch")
                alerts = SNS("SNS alerts")
                cw >> Edge(color=DASH, style="dashed") >> alerts

        with Cluster("ABSA Trust Boundary", graph_attr=ABSA):
            absa_in = S3("ABSA receiving\nbucket")
            absa_verify = IAMRole("ABSA verify\n(offline)")
            absa_in >> Edge(color=SEC) >> absa_verify

        sfn >> Edge(color=GRAY) >> compute
        sfn >> Edge(color=GRAY, style="dashed") >> sm
        indata >> Edge(color=DATA) >> compute
        compute >> Edge(color=DATA) >> outdata
        outdata >> Edge(color=GRAY) >> dq
        dq >> Edge(color=SEC, label="sign output") >> signer
        signer >> Edge(color=SEC) >> signed_out
        signed_out >> Edge(color=DATA, style="dashed", label="cross-account delivery") >> absa_in
        sfn >> Edge(color=DASH, style="dashed", label="logs/metrics") >> cw


def chain_of_custody():
    with Diagram(
        "Chain of Custody - Signing & Cross-Account Verification",
        filename=str(OUT / "04-chain-of-custody"),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
    ):
        with Cluster("EXL exl-prod - Signing Foundation (ADR-0009)", graph_attr=EXL):
            producer = Lambda("Producer\n(Code Intake /\nPipeline Factory)")
            with Cluster("KMS", graph_attr=SECC):
                cmk = KMS("Asymmetric CMK\nRSASSA_PKCS1_V1_5_SHA_256")
            signed = S3("Signed manifests\n(envelope + signature)")
            pub = S3("Public-keys bucket\n(PEM, versioned)")
            producer >> Edge(color=SEC, label="canonical_json -> kms:Sign") >> cmk
            cmk >> Edge(color=SEC) >> signed
            cmk >> Edge(color=SEC, label="kms:GetPublicKey -> publish") >> pub

        with Cluster("ABSA Trust Boundary - Verifier", graph_attr=ABSA):
            principal = IAMRole("ABSA principal\n(cross-account)")
            verify = General("verify_offline\n(digest + signature)")
            principal >> Edge(color=GRAY) >> verify

        signed >> Edge(color=DATA, style="dashed", label="fetch manifest") >> principal
        pub >> Edge(color=SEC, style="dashed", label="s3:GetObject (PEM)") >> principal
        verify >> Edge(color=SEC, label="anchor: pkg.digest == pipeline.upstream_ref") >> signed


def cicd():
    with Diagram(
        "CI/CD - Jenkins Migration (ADR-0011)",
        filename=str(OUT / "05-cicd-jenkins"),
        outformat="png",
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
    ):
        with Cluster("Source", graph_attr=SECC):
            gh = General("GitHub\n(PR + branch protection)")

        with Cluster("EXL CI - standalone Jenkins", graph_attr=CICD):
            jenkins = Jenkins("Jenkins\n(absa-ci shared lib)")
            with Cluster("Pipelines", graph_attr=ONBOARD):
                pv = Fargate("python-validate")
                ci = Fargate("code-intake")
                tv = Fargate("terraform-validate")
                ld = Fargate("localstack-demo")
                pf = Fargate("pipeline-factory\n(sign + register)")
            jenkins >> Edge(color=GRAY) >> [pv, ci, tv, ld, pf]

        with Cluster("EXL exl-prod", graph_attr=EXL):
            cmk = KMS("Signing CMK")
            signed = S3("Signed manifests")
            reg = APIGateway("Registry API")

        gh >> Edge(color=HTTP, label="webhook") >> jenkins
        jenkins >> Edge(color=HTTP, style="dashed", label="commit status") >> gh
        pf >> Edge(color=SEC, label="IRSA / assume-role -> kms:Sign") >> cmk
        cmk >> Edge(color=SEC) >> signed
        pf >> Edge(color=HTTP, label="SigV4 register") >> reg


def main():
    overview()
    track_a()
    track_b()
    chain_of_custody()
    cicd()
    print("Wrote diagrams to", OUT)
    for p in sorted(OUT.glob("*.png")):
        print(" ", p.name, f"{p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
