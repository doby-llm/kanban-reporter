from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kanban_reporting.adapters.hermes_kanban import _resolve_hermes_command, build_snapshot_from_list_rows


def test_build_snapshot_from_list_rows_preserves_live_board_facts_without_branding():
    generated_at = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    completed_in_window = int(datetime(2026, 6, 3, 11, 50, tzinfo=timezone.utc).timestamp())
    rows = [
        {
            "id": "t_a1b2c3",
            "title": "Ship renderer",
            "assignee": "coder",
            "status": "running",
            "priority": 90,
            "created_at": 1780480000,
            "started_at": 1780480100,
            "completed_at": None,
        },
        {
            "id": "t_b2c3d4",
            "title": "Review handoff",
            "assignee": "reviewer",
            "status": "blocked",
            "priority": 80,
            "created_at": 1780480000,
            "started_at": 1780480200,
            "completed_at": None,
        },
        {
            "id": "t_c3d4e5",
            "title": "Architecture accepted",
            "assignee": "architect",
            "status": "done",
            "priority": 70,
            "created_at": 1780479000,
            "started_at": 1780479500,
            "completed_at": completed_in_window,
        },
    ]

    snapshot = build_snapshot_from_list_rows(
        rows,
        board_name="neutral-board",
        project_name="Neutral Project",
        generated_at=generated_at,
        timezone_name="Europe/Zurich",
        job_id="job-123",
        window_minutes=40,
        next_update_at_local="2026-06-03 14:40 Europe/Zurich",
    )

    assert snapshot["board_name"] == "neutral-board"
    assert snapshot["project_name"] == "Neutral Project"
    assert snapshot["job_id"] == "job-123"
    assert snapshot["window_label"] == "Last 40 minutes"
    assert snapshot["next_update_at_local"] == "2026-06-03 14:40 Europe/Zurich"
    assert [task["task_id"] for task in snapshot["tasks"]] == ["t_a1b2c3", "t_b2c3d4", "t_c3d4e5"]
    blocked = snapshot["tasks"][1]
    assert blocked["blocked_reason"] == "Blocked in Hermes Kanban; no detailed reason was present in the list export."
    assert blocked["needed_next"] == "Open the task details and resolve the blocker or provide the missing decision."
    assert any(change["event_type"] == "completed" and change["task_id"] == "t_c3d4e5" for change in snapshot["changes"])


def test_build_snapshot_uses_epoch_timestamps_for_local_display_and_age_labels():
    rows = [
        {
            "id": "t_a1b2c3",
            "title": "Ready task",
            "assignee": "coder",
            "status": "ready",
            "priority": 50,
            "created_at": 1780478400,
            "started_at": None,
            "completed_at": None,
        }
    ]

    snapshot = build_snapshot_from_list_rows(
        rows,
        board_name="neutral-board",
        generated_at=datetime.fromtimestamp(1780482000, tz=timezone.utc),
        timezone_name="Europe/Zurich",
        window_minutes=40,
    )

    task = snapshot["tasks"][0]
    assert task["last_update_local"].endswith("Europe/Zurich")
    assert task["last_update_age_label"] == "1h ago"
    assert task["current_signal"] == "Status is ready."


def test_resolve_hermes_command_uses_generic_candidates_only(monkeypatch):
    monkeypatch.delenv("HERMES_CLI", raising=False)
    monkeypatch.setattr("kanban_reporting.adapters.hermes_kanban.shutil.which", lambda _: None)

    with pytest.raises(FileNotFoundError, match="set HERMES_CLI"):
        _resolve_hermes_command(None)


def test_resolve_hermes_command_accepts_explicit_cli_path(tmp_path):
    cli = tmp_path / "custom-hermes"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")

    assert _resolve_hermes_command(str(cli)) == [str(cli)]
