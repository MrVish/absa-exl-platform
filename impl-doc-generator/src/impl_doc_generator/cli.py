"""Click CLI for the Implementation Document Generator.

    generate-impl-doc --package packages/credit-risk-pd/1.0.0 \
        --pipeline pipelines/credit-risk-pd/1.0.0/manifest.json \
        --dev-doc packages/credit-risk-pd/1.0.0/dev-doc.md \
        [--provider offline|azure_openai|anthropic] [--out path] [--approver name]

Flow: build context bundle -> raw-data/PII guard -> provider drafts narrative ->
render document. Prints the document digest (the ``implementation_doc_ref`` that
goes on the registry record). Exits 1 on any IDG error.
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import click

from .bundle import build_context_bundle
from .document import render_document
from .errors import IdgError
from .guard import guard_bundle
from .providers import get_provider


@click.command(help=__doc__)
@click.option(
    "--package",
    "package",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Productized package dir (contains manifest.json, model_config.yaml, pir.yaml)",
)
@click.option(
    "--pipeline",
    "pipeline",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Pipeline manifest JSON from Pipeline Factory",
)
@click.option(
    "--dev-doc",
    "dev_doc",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="ABSA model development document (markdown / text)",
)
@click.option(
    "--provider",
    "provider_name",
    default="offline",
    type=click.Choice(["offline", "azure_openai", "anthropic"]),
    help="LLM provider (default: offline, deterministic)",
)
@click.option(
    "--out",
    "out",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Output path (default: <package>/implementation.md)",
)
@click.option("--approver", default=None, help="Human approver (records status APPROVED)")
@click.option(
    "--generated-at",
    "generated_at",
    default=None,
    help="Override the generated_at timestamp (for reproducible output)",
)
def main(
    package: Path,
    pipeline: Path | None,
    dev_doc: Path | None,
    provider_name: str,
    out: Path | None,
    approver: str | None,
    generated_at: str | None,
) -> None:
    try:
        bundle = build_context_bundle(package, pipeline_manifest=pipeline, dev_doc=dev_doc)
        guard_bundle(bundle)  # hard rule: code + docs + metadata only, never raw data
        provider = get_provider(provider_name)
        ts = generated_at or _dt.datetime.now(_dt.UTC).isoformat()
        status = "APPROVED" if approver else "DRAFT"
        doc = render_document(bundle, provider, generated_at=ts, approver=approver, status=status)
    except IdgError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    out_path = out or (package / "implementation.md")
    out_path.write_text(doc.markdown, encoding="utf-8")
    click.echo(f"wrote {out_path}")
    click.echo(f"implementation_doc_ref (sha256): {doc.doc_digest}")
    click.echo(f"provider={doc.provenance['llm_provider']} status={doc.provenance['status']}")
    if not approver:
        click.echo(
            "NOTE: status=DRAFT — a human must review + approve (re-run with --approver) "
            "before this is platform evidence.",
            err=True,
        )


if __name__ == "__main__":
    main()
