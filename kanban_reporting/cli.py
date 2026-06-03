from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .adapters.hermes_kanban import collect_live_snapshot
from .generator import build_report_from_snapshot
from .models import BoardReport
from .pdf import render_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a project-agnostic Hermes Kanban JSON/PDF report.")
    parser.add_argument("--fixture", type=Path, help="Project-agnostic board snapshot JSON to transform into a report.")
    parser.add_argument("--live-board", help="Hermes Kanban board slug to collect live via `hermes kanban list --json`.")
    parser.add_argument("--input-report", type=Path, help="Already validated BoardReport JSON payload to render/write.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for report JSON/PDF artifacts.")
    parser.add_argument("--format", default="json,pdf", help="Comma-separated outputs: json,pdf")
    parser.add_argument("--schema", action="store_true", help="Write the BoardReport JSON Schema and exit.")
    parser.add_argument("--project-name", help="Optional display name for the project/board consumer.")
    parser.add_argument("--timezone", default="Europe/Zurich", help="IANA timezone for local report timestamps.")
    parser.add_argument("--job-id", help="Optional cron/job id to include in report metadata.")
    parser.add_argument("--window-minutes", type=int, default=40, help="Reporting window length used for live-board change derivation.")
    parser.add_argument("--next-update-at-local", help="Optional human-readable next scheduled run time.")
    parser.add_argument("--hermes-cli", help="Absolute path to Hermes CLI; defaults to HERMES_CLI, PATH, or the standard install path.")
    args = parser.parse_args(argv)

    try:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        formats = {part.strip() for part in args.format.split(",") if part.strip()}
        if args.schema:
            schema_path = args.out_dir / "board-report.schema.json"
            schema_path.write_text(json.dumps(BoardReport.model_json_schema(), indent=2), encoding="utf-8")
            print(json.dumps({"ok": True, "schema_path": str(schema_path.resolve())}, separators=(",", ":")))
            return 0

        report = _load_report(args)
        json_path = args.out_dir / "report.json"
        pdf_path: Path | None = None
        if "json" in formats:
            json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        if "pdf" in formats:
            pdf_path = render_pdf(report, report.delivery.attachment_path)

        envelope = {
            "ok": True,
            "schema_version": report.schema_version,
            "json_path": str(json_path.resolve()) if "json" in formats else None,
            "pdf_path": str(pdf_path.resolve()) if pdf_path else None,
            "requires_human": bool(report.blockers.items or report.risks.items),
            "headline": report.delivery.summary_line,
            "delivery_text": _delivery_text(report),
            "media_tag": f"MEDIA:{pdf_path.resolve()}" if pdf_path else None,
        }
        print(json.dumps(envelope, separators=(",", ":")))
        return 0
    except FileNotFoundError as exc:
        print(f"input/board extraction failed: {exc}", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print(f"schema validation failed: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # PDF rendering or filesystem failures after validation.
        print(f"report generation failed: {exc}", file=sys.stderr)
        return 4


def _load_report(args: argparse.Namespace) -> BoardReport:
    inputs = [bool(args.fixture), bool(args.input_report), bool(args.live_board)]
    if sum(inputs) > 1:
        raise ValueError("Use only one of --fixture, --input-report, or --live-board")
    if args.input_report:
        return BoardReport.model_validate_json(args.input_report.read_text(encoding="utf-8"))
    if args.live_board:
        snapshot = collect_live_snapshot(
            board_name=args.live_board,
            hermes_cli=args.hermes_cli,
            project_name=args.project_name,
            timezone_name=args.timezone,
            job_id=args.job_id,
            window_minutes=args.window_minutes,
            next_update_at_local=args.next_update_at_local,
        )
        return build_report_from_snapshot(snapshot, out_dir=args.out_dir)
    if args.fixture:
        snapshot: dict[str, Any] = json.loads(args.fixture.read_text(encoding="utf-8"))
        return build_report_from_snapshot(snapshot, out_dir=args.out_dir)
    raise ValueError("Either --fixture, --input-report, or --schema is required")


def _delivery_text(report: BoardReport) -> str:
    parts = [report.delivery.summary_line, report.delivery.primary_risk_line]
    if report.delivery.next_run_line:
        parts.append(report.delivery.next_run_line)
    if report.delivery.attachment_path:
        parts.append(f"PDF attached: {report.delivery.attachment_path}")
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
