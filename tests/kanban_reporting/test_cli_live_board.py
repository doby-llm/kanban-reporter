from __future__ import annotations

from pathlib import Path

from kanban_reporting import cli


def test_cli_live_board_generates_pdf_from_hermes_list_json(tmp_path, monkeypatch, capsys):
    def fake_collect_live_snapshot(**kwargs):
        assert kwargs["board_name"] == "neutral-board"
        assert kwargs["project_name"] == "Neutral Project"
        assert kwargs["job_id"] == "job-123"
        assert kwargs["window_minutes"] == 40
        assert kwargs["timezone_name"] == "Europe/Zurich"
        return {
            "board_name": "neutral-board",
            "project_name": "Neutral Project",
            "timezone": "Europe/Zurich",
            "window_label": "Last 40 minutes",
            "generated_at": "2026-06-03T15:20:00+02:00",
            "window_start": "2026-06-03T14:40:00+02:00",
            "window_end": "2026-06-03T15:20:00+02:00",
            "run_id": "20260603-152000",
            "job_id": "job-123",
            "tasks": [
                {
                    "task_id": "t_a1b2c3",
                    "title": "Running task",
                    "status": "running",
                    "assignee": "coder",
                    "priority": 90,
                    "last_update_local": "2026-06-03 15:15 Europe/Zurich",
                    "last_update_age_label": "5m ago",
                    "current_signal": "Status is running.",
                }
            ],
            "changes": [],
        }

    monkeypatch.setattr(cli, "collect_live_snapshot", fake_collect_live_snapshot)

    assert cli.main([
        "--live-board",
        "neutral-board",
        "--project-name",
        "Neutral Project",
        "--job-id",
        "job-123",
        "--out-dir",
        str(tmp_path),
        "--format",
        "json,pdf",
    ]) == 0

    output = capsys.readouterr().out
    assert "\"ok\":true" in output
    assert "MEDIA:" in output
    assert Path(tmp_path, "report.json").exists()
    assert next(tmp_path.glob("*.pdf")).stat().st_size > 0
