import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from kanban_reporting.generator import build_report_from_snapshot
from kanban_reporting.models import BoardReport

FIXTURE = Path(__file__).parents[1] / "fixtures" / "kanban_reporting" / "sample_board.json"


def test_board_report_rejects_unknown_fields():
    report = build_report_from_snapshot(json.loads(FIXTURE.read_text()))
    payload = report.model_dump(mode="json")
    payload["unexpected"] = "must fail fast"

    with pytest.raises(ValidationError):
        BoardReport.model_validate(payload)


def test_schema_exposes_required_report_sections():
    schema = BoardReport.model_json_schema()

    assert set(schema["required"]) >= {
        "schema_version",
        "generated_at",
        "report",
        "health",
        "metrics",
        "summary",
        "blockers",
        "changes",
        "active",
        "completed",
        "risks",
        "dependencies",
        "appendix",
        "delivery",
    }
