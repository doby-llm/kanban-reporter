import json
from pathlib import Path

from kanban_reporting.generator import build_report_from_snapshot
from kanban_reporting.models import HealthLevel

FIXTURE = Path(__file__).parents[1] / "fixtures" / "kanban_reporting" / "sample_board.json"


def test_snapshot_generator_computes_counts_and_delivery_lines():
    report = build_report_from_snapshot(json.loads(FIXTURE.read_text()), out_dir="/tmp/kanban-report-test")

    assert report.health.level is HealthLevel.blocked
    assert report.metrics.total_tasks == 4
    assert report.metrics.running_count == 1
    assert report.metrics.blocked_count == 1
    assert report.metrics.ready_count == 1
    assert report.metrics.done_since_last_report_count == 1
    assert report.blockers.items[0].needed_next == "Review the PDF artifact and approve push."
    assert report.delivery.filename.startswith("kanban-example-board-20260603-1520-Europe-Zurich")
    assert report.delivery.media_tag == "MEDIA:/tmp/kanban-report-test/" + report.delivery.filename
