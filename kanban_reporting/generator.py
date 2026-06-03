from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    ActiveItem,
    ActiveSection,
    Appendix,
    AssigneeCount,
    BlockerItem,
    BlockersSection,
    BoardReport,
    ChangeItem,
    ChangesSection,
    CompletedItem,
    CompletedSection,
    DependenciesSection,
    DependencyItem,
    Delivery,
    ExecutiveSummary,
    GeneratorMetadata,
    Health,
    HealthLevel,
    Metrics,
    ReportMetadata,
    ReportWindow,
    RiskItem,
    RiskLevel,
    RiskThreshold,
    RisksSection,
    Severity,
    StatusCount,
    SummaryBullet,
    KanbanStatus,
)

ACTIVE_STATUSES = {
    KanbanStatus.triage,
    KanbanStatus.todo,
    KanbanStatus.ready,
    KanbanStatus.running,
    KanbanStatus.blocked,
}
STATUS_SORT = {
    KanbanStatus.blocked: 0,
    KanbanStatus.running: 1,
    KanbanStatus.ready: 2,
    KanbanStatus.todo: 3,
    KanbanStatus.triage: 4,
    KanbanStatus.done: 5,
    KanbanStatus.archived: 6,
}


def build_report_from_snapshot(snapshot: dict[str, Any], out_dir: str | Path | None = None) -> BoardReport:
    """Build a deterministic report from an explicit board snapshot fixture/export.

    The snapshot is intentionally small and project-agnostic: a list of tasks plus
    optional event changes. Live Hermes board extraction can normalize into this
    shape without giving the renderer permission to invent board facts.
    """
    generated_at = _parse_dt(snapshot["generated_at"])
    timezone = snapshot["timezone"]
    board_name = snapshot["board_name"]
    run_id = snapshot.get("run_id") or generated_at.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(out_dir or f"/tmp/kanban-report-{_slug(board_name)}-{run_id}").resolve()
    filename = _report_filename(board_name, generated_at, timezone, run_id)
    pdf_path = str(output_dir / filename)

    tasks = list(snapshot.get("tasks", []))
    status_counts = Counter(KanbanStatus(task["status"]) for task in tasks)
    changes = list(snapshot.get("changes", []))
    completed_tasks = [task for task in tasks if task.get("status") == KanbanStatus.done.value]
    blockers = [_blocker_from_task(task) for task in tasks if task.get("status") == KanbanStatus.blocked.value]
    active = [_active_from_task(task) for task in tasks if KanbanStatus(task["status"]) in ACTIVE_STATUSES]
    active.sort(key=lambda item: (STATUS_SORT[item.status], -(item.priority or 0), item.title.lower()))

    metrics = Metrics(
        total_tasks=len(tasks),
        running_count=status_counts[KanbanStatus.running],
        blocked_count=status_counts[KanbanStatus.blocked],
        ready_count=status_counts[KanbanStatus.ready],
        done_since_last_report_count=len(completed_tasks),
        changed_since_last_report_count=len(changes),
    )
    health = _health_from_metrics(metrics)
    risk_items = [_risk_from_blocker(blocker) for blocker in blockers]

    report = BoardReport(
        schema_version="1.0.0",
        generated_at=generated_at,
        report=ReportMetadata(
            project_name=snapshot.get("project_name"),
            board_name=board_name,
            generated_at_local=snapshot.get("generated_at_local") or _display_dt(generated_at, timezone),
            timezone=timezone,
            window=ReportWindow(
                since=_parse_optional_dt(snapshot.get("window_start")),
                until=_parse_dt(snapshot.get("window_end") or snapshot["generated_at"]),
                label=snapshot.get("window_label", "Current window"),
            ),
            window_label=snapshot.get("window_label", "Current window"),
            job_id=snapshot.get("job_id"),
            generator=GeneratorMetadata(run_id=run_id),
        ),
        health=health,
        metrics=metrics,
        summary=_summary(metrics, health, snapshot.get("next_update_at_local")),
        blockers=BlockersSection(items=blockers),
        changes=ChangesSection(
            window_start_local=snapshot.get("window_start_local") or snapshot.get("window_start"),
            window_end_local=snapshot.get("window_end_local") or snapshot.get("window_end") or snapshot["generated_at"],
            items=[ChangeItem.model_validate(change) for change in changes[:12]],
            omitted_count=max(0, len(changes) - 12),
        ),
        active=ActiveSection(items=active),
        completed=CompletedSection(items=[_completed_from_task(task) for task in completed_tasks[:10]], omitted_count=max(0, len(completed_tasks) - 10)),
        risks=RisksSection(thresholds=_default_thresholds(), items=risk_items),
        dependencies=_dependencies(tasks),
        appendix=_appendix(tasks, status_counts),
        delivery=Delivery(
            summary_line=_summary_line(board_name, metrics),
            primary_risk_line=_primary_risk_line(blockers),
            next_run_line=(f"Next run around {snapshot['next_update_at_local']}" if snapshot.get("next_update_at_local") else None),
            attachment_path=pdf_path,
            media_tag=f"MEDIA:{pdf_path}",
            filename=filename,
        ),
    )
    return report


def _blocker_from_task(task: dict[str, Any]) -> BlockerItem:
    return BlockerItem(
        task_id=task["task_id"],
        title=task["title"],
        assignee=task.get("assignee"),
        severity=RiskLevel(task.get("severity", "high")),
        blocked_reason=task.get("blocked_reason") or task.get("current_signal") or "Blocked; reason not specified in input snapshot.",
        blocked_since_local=task.get("blocked_since_local"),
        blocked_age_label=task.get("blocked_age_label") or task.get("last_update_age_label"),
        needed_next=task.get("needed_next") or "Review blocker and provide the required decision.",
        last_comment_excerpt=task.get("last_comment_excerpt"),
    )


def _active_from_task(task: dict[str, Any]) -> ActiveItem:
    return ActiveItem(
        task_id=task["task_id"],
        title=task["title"],
        status=KanbanStatus(task["status"]),
        assignee=task.get("assignee"),
        last_update_local=task.get("last_update_local", "unknown"),
        last_update_age_label=task.get("last_update_age_label", "unknown"),
        current_signal=task.get("current_signal", "No current signal provided."),
        priority=task.get("priority"),
        parent_ids=task.get("parent_ids", []),
        child_ids=task.get("child_ids", []),
    )


def _completed_from_task(task: dict[str, Any]) -> CompletedItem:
    return CompletedItem(
        task_id=task["task_id"],
        title=task["title"],
        assignee=task.get("assignee"),
        completed_at_local=task.get("completed_at_local") or task.get("last_update_local", "unknown"),
        summary=task.get("summary") or task.get("current_signal", "Completed."),
        metadata_highlights=task.get("metadata_highlights", [])[:3],
    )


def _risk_from_blocker(blocker: BlockerItem) -> RiskItem:
    return RiskItem(
        task_id=blocker.task_id,
        title=blocker.title,
        risk_level=blocker.severity,
        risk_reason=blocker.blocked_reason,
        age_label=blocker.blocked_age_label or "unknown",
        recommended_action=blocker.needed_next,
    )


def _health_from_metrics(metrics: Metrics) -> Health:
    if metrics.blocked_count:
        return Health(level=HealthLevel.blocked, summary=f"{metrics.blocked_count} task(s) are blocked and need operator attention.")
    if metrics.running_count or metrics.ready_count:
        return Health(level=HealthLevel.attention, summary="Board is moving; monitor active work and ready queue.")
    return Health(level=HealthLevel.ok, summary="No blocked tasks detected in this report window.")


def _summary(metrics: Metrics, health: Health, next_update: str | None) -> ExecutiveSummary:
    bullets = [
        SummaryBullet(label="Progress", text=f"{metrics.done_since_last_report_count} task(s) completed and {metrics.changed_since_last_report_count} notable change(s) recorded.", severity=Severity.success if metrics.done_since_last_report_count else Severity.info),
        SummaryBullet(label="Risk", text=health.summary, severity=Severity.danger if health.level in {HealthLevel.blocked, HealthLevel.critical} else Severity.info),
        SummaryBullet(label="Next", text=f"{metrics.ready_count} task(s) are ready and {metrics.running_count} task(s) are running.", severity=Severity.info),
    ]
    return ExecutiveSummary(bullets=bullets, next_update_at_local=next_update)


def _dependencies(tasks: list[dict[str, Any]]) -> DependenciesSection:
    root_count = 0
    with_children_count = 0
    waiting: list[DependencyItem] = []
    for task in tasks:
        parents = task.get("parent_ids", [])
        children = task.get("child_ids", [])
        if not parents:
            root_count += 1
        if children:
            with_children_count += 1
        if parents and task.get("status") in {"todo", "triage"}:
            waiting.append(DependencyItem(task_id=task["task_id"], title=task["title"], waiting_on_task_ids=parents, unblocked_when="All parent tasks are done."))
    return DependenciesSection(root_count=root_count, with_children_count=with_children_count, waiting_on_parents_count=len(waiting), items=waiting)


def _appendix(tasks: list[dict[str, Any]], counts: Counter[KanbanStatus]) -> Appendix:
    by_assignee: dict[str, Counter[KanbanStatus]] = defaultdict(Counter)
    for task in tasks:
        by_assignee[task.get("assignee") or "unassigned"][KanbanStatus(task["status"])] += 1
    assignee_counts = []
    for assignee, assignee_counter in sorted(by_assignee.items()):
        assignee_counts.append(AssigneeCount(
            assignee=assignee,
            todo=assignee_counter[KanbanStatus.todo],
            ready=assignee_counter[KanbanStatus.ready],
            running=assignee_counter[KanbanStatus.running],
            blocked=assignee_counter[KanbanStatus.blocked],
            done=assignee_counter[KanbanStatus.done],
            total=sum(assignee_counter.values()),
        ))
    return Appendix(status_counts=[StatusCount(status=status, count=counts[status]) for status in KanbanStatus], assignee_counts=assignee_counts)


def _default_thresholds() -> list[RiskThreshold]:
    return [
        RiskThreshold(label="Blocked > 1h", description="Blocked tasks older than one hour should be escalated."),
        RiskThreshold(label="Running stale", description="Running tasks without recent heartbeat may need a check-in."),
        RiskThreshold(label="Ready aging", description="Ready work sitting across multiple windows may indicate staffing bottlenecks."),
    ]


def _summary_line(board_name: str, metrics: Metrics) -> str:
    return (
        f"Kanban report for {board_name}: {metrics.running_count} running, "
        f"{metrics.blocked_count} blocked, {metrics.ready_count} ready, "
        f"{metrics.done_since_last_report_count} done since last update."
    )


def _primary_risk_line(blockers: list[BlockerItem]) -> str:
    if not blockers:
        return "Main risk: no blocked tasks right now."
    first = blockers[0]
    return f"Main risk: {first.title} is blocked — {first.needed_next}"


def _report_filename(board_name: str, generated_at: datetime, timezone: str, run_id: str) -> str:
    base = f"kanban-{_slug(board_name)}-{generated_at.strftime('%Y%m%d-%H%M')}-{timezone.replace('/', '-')}"
    if len(base) < 72:
        base = f"{base}-r{_slug(run_id)[:8]}"
    return f"{base[:76]}.pdf"


def _slug(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in normalized.split("-") if part) or "report"


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_optional_dt(value: str | None) -> datetime | None:
    return _parse_dt(value) if value else None


def _display_dt(value: datetime, timezone: str) -> str:
    return f"{value.strftime('%Y-%m-%d %H:%M')} {timezone}"
