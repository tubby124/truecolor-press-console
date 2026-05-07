"""CLI for diagnostics and dry-run job submission.

  python -m backend.cli probe
  python -m backend.cli preflight path/to/file.pdf
  python -m backend.cli dry-run plain-print path/to/file.pdf
  python -m backend.cli rates
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import preflight
from .printer import PrintOptions, probe_status, submit
from .settings import click_rates, settings


def cmd_probe(args: argparse.Namespace) -> int:
    result = probe_status(host=args.host)
    print(json.dumps({k: v for k, v in result.items() if k != "raw"}, indent=2))
    if args.verbose and "raw" in result:
        print("\n--- raw response ---")
        print(result["raw"])
    return 0 if result.get("reachable") else 2


def cmd_preflight(args: argparse.Namespace) -> int:
    rep = preflight.run(Path(args.file), expect_bleed_in=args.bleed)
    print(f"File: {rep.file}")
    print(f"Pages: {rep.page_count}")
    if rep.page_sizes:
        first = rep.page_sizes[0]
        print(f"First page: {first[0] / 72:.2f}\" × {first[1] / 72:.2f}\"")
    if rep.findings:
        for f in rep.findings:
            tag = "BLOCK" if f.severity == "block" else "WARN"
            page = f" page {f.page}" if f.page else ""
            print(f"  [{tag}]{page} {f.code}: {f.message}")
    else:
        print("  No findings.")
    return 0 if rep.can_send else 1


def cmd_dry_run(args: argparse.Namespace) -> int:
    pdf_path = Path(args.file)
    if not pdf_path.exists():
        print(f"Not found: {pdf_path}", file=sys.stderr)
        return 2
    pdl = pdf_path.read_bytes()
    opts = PrintOptions(
        job_name=f"{args.workflow}-{pdf_path.stem}",
        paper=args.paper,
        media_source=args.tray,
        duplex=args.duplex,
        copies=args.copies,
    )
    result = submit(pdl, opts, language="POSTSCRIPT")
    print(json.dumps(result, indent=2))
    return 0


def cmd_rates(_: argparse.Namespace) -> int:
    print(json.dumps(click_rates(), indent=2))
    print(f"Source: {settings.estimator_config_csv}")
    print(f"Source exists: {settings.estimator_config_csv.exists()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="press-console", description="C3070 press console CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_probe = sub.add_parser("probe", help="Query printer status (read-only)")
    sp_probe.add_argument("--host", default=None)
    sp_probe.add_argument("-v", "--verbose", action="store_true")
    sp_probe.set_defaults(fn=cmd_probe)

    sp_pf = sub.add_parser("preflight", help="Validate a PDF before sending")
    sp_pf.add_argument("file")
    sp_pf.add_argument("--bleed", type=float, default=0.0, help="Expected bleed in inches")
    sp_pf.set_defaults(fn=cmd_preflight)

    sp_dry = sub.add_parser("dry-run", help="Build the PJL bundle and write to tmp/")
    sp_dry.add_argument("workflow")
    sp_dry.add_argument("file")
    sp_dry.add_argument("--paper", default="LETTER")
    sp_dry.add_argument("--tray", default="AUTO")
    sp_dry.add_argument("--duplex", action="store_true")
    sp_dry.add_argument("--copies", type=int, default=1)
    sp_dry.set_defaults(fn=cmd_dry_run)

    sp_rates = sub.add_parser("rates", help="Show current click rates")
    sp_rates.set_defaults(fn=cmd_rates)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
