from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo


def load_snapshot(path: str | Path) -> dict[str, Any]:
    """Load an explicit Hermes Kanban snapshot JSON file.

    Live board extraction should normalize into the fixture shape consumed by
    kanban_reporting.generator before validation/rendering.
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))


def collect_live_snapshot(
    board_name: str,
    *,
    hermes_cli: str | None = None,
    project_name: str | None = None,
    timezone_name: str = "Europe/Zurich",
    job_id: str | None = None,
    window_minutes: int = 40,
    next_update_at_local: str | None = None,
) -> dict[str, Any]:
    """Collect `hermes kanban list --json` and normalize it for the reporter.

    The adapter only records facts returned by Hermes Kanban list output plus
    deterministic status-derived labels. It intentionally does not infer product
    domain details or create project-specific fields.
    """
    cli = _resolve_hermes_command(hermes_cli)
    result = subprocess.run(
        [*cli, "kanban", "--board", board_name, "list", "--json"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rows = json.loads(result.stdout)
    blocked_details = _collect_blocked_details(cli, board_name, rows)
    return build_snapshot_from_list_rows(
        rows,
        board_name=board_name,
        project_name=project_name,
        generated_at=datetime.now(timezone.utc),
        timezone_name=timezone_name,
        job_id=job_id,
        window_minutes=window_minutes,
        next_update_at_local=next_update_at_local,
        blocked_details_by_id=blocked_details,
    )


def build_snapshot_from_list_rows(
    rows: Sequence[dict[str, Any]],
    *,
    board_name: str,
    generated_at: datetime,
    timezone_name: str = "Europe/Zurich",
    project_name: str | None = None,
    job_id: str | None = None,
    window_minutes: int = 40,
    next_update_at_local: str | None = None,
    blocked_details_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    tz = ZoneInfo(timezone_name)
    generated_local = generated_at.astimezone(tz)
    window_start = generated_local - timedelta(minutes=window_minutes)
    tasks = [
        _normalize_task(
            row,
            generated_local,
            tz,
            blocked_detail=(blocked_details_by_id or {}).get(str(row.get("id"))),
        )
        for row in rows
    ]
    changes = _changes_from_tasks(tasks, window_start=window_start, window_end=generated_local)
    run_id = generated_local.strftime("%Y%m%d-%H%M%S")

    snapshot: dict[str, Any] = {
        "board_name": board_name,
        "timezone": timezone_name,
        "window_label": f"Last {window_minutes} minutes",
        "generated_at": generated_local.isoformat(),
        "generated_at_local": _display_dt(generated_local, timezone_name),
        "window_start": window_start.isoformat(),
        "window_end": generated_local.isoformat(),
        "window_start_local": _display_dt(window_start, timezone_name),
        "window_end_local": _display_dt(generated_local, timezone_name),
        "run_id": run_id,
        "tasks": tasks,
        "changes": changes,
    }
    if project_name:
        snapshot["project_name"] = project_name
    if job_id:
        snapshot["job_id"] = job_id
    if next_update_at_local:
        snapshot["next_update_at_local"] = next_update_at_local
    return snapshot


def _normalize_task(
    row: dict[str, Any],
    generated_local: datetime,
    tz: ZoneInfo,
    *,
    blocked_detail: str | None = None,
) -> dict[str, Any]:
    status = row["status"]
    last_update = _last_update(row, tz)
    task: dict[str, Any] = {
        "task_id": row["id"],
        "title": row["title"],
        "status": status,
        "assignee": row.get("assignee"),
        "priority": row.get("priority"),
        "last_update_local": _display_dt(last_update, tz.key),
        "last_update_age_label": _age_label(last_update, generated_local),
        "current_signal": _current_signal(status),
        "parent_ids": row.get("parent_ids") or row.get("parents") or [],
        "child_ids": row.get("child_ids") or row.get("children") or [],
    }
    if status == "blocked":
        fallback_reason = "Blocked in Hermes Kanban; no detailed reason was present in the list export."
        blocked_reason = blocked_detail or fallback_reason
        task.update(
            {
                "blocked_reason": blocked_reason,
                "blocked_since_local": _display_dt(last_update, tz.key),
                "blocked_age_label": _age_label(last_update, generated_local),
                "needed_next": blocked_reason
                if blocked_detail
                else "Open the task details and resolve the blocker or provide the missing decision.",
                "severity": "high",
            }
        )
    if status == "done":
        task["completed_at_local"] = _display_dt(last_update, tz.key)
        task["summary"] = "Completed in Hermes Kanban."
    return task


def _collect_blocked_details(
    cli: list[str],
    board_name: str,
    rows: Sequence[dict[str, Any]],
) -> dict[str, str]:
    details: dict[str, str] = {}
    for row in rows:
        if row.get("status") != "blocked":
            continue
        task_id = str(row.get("id") or "")
        if not task_id:
            continue
        detail = _fetch_blocked_detail(cli, board_name, task_id)
        if detail:
            details[task_id] = detail
    return details


def _fetch_blocked_detail(cli: list[str], board_name: str, task_id: str) -> str | None:
    try:
        result = subprocess.run(
            [*cli, "kanban", "--board", board_name, "show", task_id, "--json"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return _blocked_detail_from_task_show(json.loads(result.stdout))
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return None


def _blocked_detail_from_task_show(show_payload: dict[str, Any], *, max_length: int = 500) -> str | None:
    """Return the most actionable blocker text exposed by `hermes kanban show`."""
    for candidate in (
        _latest_block_event_reason(show_payload.get("events") or []),
        _latest_run_summary_or_error(show_payload.get("runs") or []),
        _latest_comment_body(show_payload.get("comments") or []),
    ):
        normalized = _safe_pdf_text(candidate, max_length=max_length)
        if normalized:
            return normalized
    return None


def _latest_block_event_reason(events: Sequence[dict[str, Any]]) -> str | None:
    blocked_events = [event for event in events if event.get("kind") == "blocked"]
    for event in sorted(blocked_events, key=_event_sort_key, reverse=True):
        payload = event.get("payload") or {}
        reason = payload.get("reason") if isinstance(payload, dict) else None
        if isinstance(reason, str) and reason.strip():
            return reason
    return None


def _latest_run_summary_or_error(runs: Sequence[dict[str, Any]]) -> str | None:
    for run in sorted(runs, key=_run_sort_key, reverse=True):
        for key in ("summary", "error"):
            value = run.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _latest_comment_body(comments: Sequence[dict[str, Any]]) -> str | None:
    for comment in sorted(comments, key=_event_sort_key, reverse=True):
        body = comment.get("body")
        if isinstance(body, str) and body.strip():
            return body
    return None


def _safe_pdf_text(value: str | None, *, max_length: int) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max(0, max_length - 1)].rstrip() + "…"


def _event_sort_key(item: dict[str, Any]) -> tuple[float, int]:
    return (_numeric_sort_value(item.get("created_at")), _integer_sort_value(item.get("id")))


def _run_sort_key(item: dict[str, Any]) -> tuple[float, float, int]:
    return (
        _numeric_sort_value(item.get("ended_at")),
        _numeric_sort_value(item.get("started_at")),
        _integer_sort_value(item.get("id")),
    )


def _integer_sort_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _numeric_sort_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _changes_from_tasks(
    tasks: list[dict[str, Any]],
    *,
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for task in tasks:
        last_update = _parse_display_dt(task["last_update_local"])
        if not (window_start <= last_update <= window_end):
            continue
        status = task["status"]
        if status == "done":
            event_type = "completed"
            severity = "success"
            summary = "Task completed during this reporting window."
        elif status == "blocked":
            event_type = "blocked"
            severity = "warning"
            summary = task.get("blocked_reason", "Task is blocked.")
        elif status == "running":
            event_type = "claimed"
            severity = "info"
            summary = "Task is running during this reporting window."
        else:
            continue
        changes.append(
            {
                "timestamp_local": task["last_update_local"],
                "event_type": event_type,
                "task_id": task["task_id"],
                "title": task["title"],
                "assignee": task.get("assignee"),
                "summary": summary,
                "severity": severity,
            }
        )
    return sorted(changes, key=lambda item: item["timestamp_local"], reverse=True)


def _resolve_hermes_command(explicit: str | None) -> list[str]:
    candidates = [
        explicit,
        os.environ.get("HERMES_CLI"),
        shutil.which("hermes"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return _python_wrapped_if_needed(candidate)
    raise FileNotFoundError("Could not find Hermes CLI; set HERMES_CLI=/absolute/path/to/hermes")


def _python_wrapped_if_needed(candidate: str) -> list[str]:
    path = Path(candidate)
    if path.name == "hermes" and path.is_file():
        python = _python_interpreter_for_script(path)
        if python:
            return [python, str(path)]
    return [candidate]


def _python_interpreter_for_script(path: Path) -> str | None:
    first_line = _first_line(path)
    if "python" not in first_line.lower():
        return None

    explicit_python = os.environ.get("HERMES_CLI_PYTHON")
    if explicit_python and Path(explicit_python).exists():
        return explicit_python

    shebang = first_line.removeprefix("#!").strip()
    executable = shebang.split(maxsplit=1)[0] if shebang else ""
    if executable.startswith("/") and Path(executable).exists():
        return executable

    default_python = "/usr/bin/python3"
    return default_python if Path(default_python).exists() else None


def _first_line(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except (OSError, IndexError):
        return ""


def _last_update(row: dict[str, Any], tz: ZoneInfo) -> datetime:
    value = row.get("completed_at") or row.get("started_at") or row.get("created_at")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).astimezone(tz)
    if isinstance(value, str) and value:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(tz)
    return datetime.now(timezone.utc).astimezone(tz)


def _display_dt(value: datetime, timezone_name: str) -> str:
    return f"{value.strftime('%Y-%m-%d %H:%M')} {timezone_name}"


def _parse_display_dt(value: str) -> datetime:
    date_part, time_part, zone_name = value.split(" ", 2)
    naive = datetime.fromisoformat(f"{date_part}T{time_part}")
    return naive.replace(tzinfo=ZoneInfo(zone_name))


def _age_label(last_update: datetime, generated_local: datetime) -> str:
    minutes = max(0, int((generated_local - last_update).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def _current_signal(status: str) -> str:
    return f"Status is {status}."
