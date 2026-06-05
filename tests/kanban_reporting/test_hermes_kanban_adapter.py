from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kanban_reporting.adapters.hermes_kanban import (
    _blocked_detail_from_task_show,
    _python_wrapped_if_needed,
    _resolve_hermes_command,
    build_snapshot_from_list_rows,
    collect_live_snapshot,
)


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


def test_collect_live_snapshot_enriches_blocked_tasks_with_show_reason(monkeypatch, tmp_path):
    hermes_cli = tmp_path / "hermes"
    hermes_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    calls = []

    def fake_run(args, check, text, stdout, stderr):
        calls.append(args)
        if args[-2:] == ["list", "--json"]:
            payload = [
                {
                    "id": "t_blocked",
                    "title": "Needs decision",
                    "assignee": "coder",
                    "status": "blocked",
                    "priority": 100,
                    "created_at": 1780480000,
                    "started_at": 1780480200,
                    "completed_at": None,
                },
                {
                    "id": "t_ready",
                    "title": "Not blocked",
                    "assignee": "coder",
                    "status": "ready",
                    "priority": 50,
                    "created_at": 1780480000,
                    "started_at": None,
                    "completed_at": None,
                },
            ]
        elif args[-3:] == ["show", "t_blocked", "--json"]:
            payload = {
                "task": {"id": "t_blocked"},
                "events": [
                    {"kind": "blocked", "created_at": 10, "payload": {"reason": "review-required: needs git push"}},
                    {"kind": "blocked", "created_at": 20, "payload": {"reason": "Human decision: choose API key owner"}},
                ],
            }
        else:  # pragma: no cover - failure path gives a clearer assertion below
            raise AssertionError(f"unexpected command: {args}")

        return type("Completed", (), {"stdout": __import__("json").dumps(payload), "stderr": ""})()

    monkeypatch.setattr("kanban_reporting.adapters.hermes_kanban.subprocess.run", fake_run)

    snapshot = collect_live_snapshot("neutral-board", hermes_cli=str(hermes_cli))

    blocked = snapshot["tasks"][0]
    assert blocked["blocked_reason"] == "Human decision: choose API key owner"
    assert blocked["needed_next"] == "Human decision: choose API key owner"
    assert calls[0][-2:] == ["list", "--json"]
    assert calls[1][-3:] == ["show", "t_blocked", "--json"]
    assert len(calls) == 2


def test_blocked_detail_prefers_latest_run_summary_or_error_when_no_block_event_reason():
    detail = _blocked_detail_from_task_show(
        {
            "runs": [
                {"id": 1, "summary": "older summary", "error": None, "ended_at": 10},
                {"id": 2, "summary": "", "error": "newer error", "ended_at": 20},
            ],
            "comments": [{"body": "comment fallback", "created_at": 30}],
            "events": [{"kind": "blocked", "payload": {}, "created_at": 40}],
        }
    )

    assert detail == "newer error"


def test_blocked_detail_uses_latest_comment_body_as_safe_fallback():
    long_body = "Human supplied context: " + ("choose deployment window carefully. " * 20)

    detail = _blocked_detail_from_task_show(
        {
            "runs": [],
            "comments": [
                {"body": "older comment", "created_at": 10},
                {"body": long_body, "created_at": 20},
            ],
            "events": [],
        },
        max_length=90,
    )

    assert detail.startswith("Human supplied context: choose deployment window carefully.")
    assert len(detail) <= 90
    assert detail.endswith("…")


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


def test_hermes_shell_wrapper_runs_directly_instead_of_python_wrapping(tmp_path):
    hermes = tmp_path / "hermes"
    hermes.write_text("#!/bin/sh\nunset PYTHONPATH\nexec hermes-real \"$@\"\n", encoding="utf-8")

    assert _python_wrapped_if_needed(str(hermes)) == [str(hermes)]


def test_hermes_python_script_is_python_wrapped(tmp_path, monkeypatch):
    python = tmp_path / "python3"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    hermes = tmp_path / "hermes"
    hermes.write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_CLI_PYTHON", str(python))

    assert _python_wrapped_if_needed(str(hermes)) == [str(python), str(hermes)]


def test_hermes_console_script_uses_absolute_python_shebang(tmp_path, monkeypatch):
    python = tmp_path / "venv" / "bin" / "python3"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    hermes = tmp_path / "hermes"
    hermes.write_text(f"#!{python}\nimport sys\n", encoding="utf-8")
    monkeypatch.delenv("HERMES_CLI_PYTHON", raising=False)

    assert _python_wrapped_if_needed(str(hermes)) == [str(python), str(hermes)]
