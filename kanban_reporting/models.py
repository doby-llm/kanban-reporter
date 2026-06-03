from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


class KanbanStatus(StrEnum):
    triage = "triage"
    todo = "todo"
    ready = "ready"
    running = "running"
    blocked = "blocked"
    done = "done"
    archived = "archived"


class Severity(StrEnum):
    info = "info"
    success = "success"
    warning = "warning"
    danger = "danger"


class RiskLevel(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    none = "none"


class HealthLevel(StrEnum):
    ok = "ok"
    attention = "attention"
    blocked = "blocked"
    critical = "critical"


class ChangeEventType(StrEnum):
    created = "created"
    claimed = "claimed"
    completed = "completed"
    blocked = "blocked"
    unblocked = "unblocked"
    failed = "failed"
    reassigned = "reassigned"
    commented = "commented"
    archived = "archived"


class ReportWindow(StrictModel):
    since: datetime | None = None
    until: datetime
    label: str = Field(min_length=1)


class GeneratorMetadata(StrictModel):
    name: str = "kanban-reporting"
    version: str = "1.0.0"
    run_id: str = Field(min_length=1)


class ReportMetadata(StrictModel):
    title: str = "Kanban status report"
    project_name: str | None = None
    board_name: str = Field(min_length=1)
    source: str = "hermes-kanban"
    generated_at_local: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    window: ReportWindow
    window_label: str = Field(min_length=1)
    job_id: str | None = None
    generator: GeneratorMetadata


class Health(StrictModel):
    level: HealthLevel
    summary: str = Field(min_length=1)


class Metrics(StrictModel):
    total_tasks: int = Field(ge=0)
    running_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    done_since_last_report_count: int = Field(ge=0)
    changed_since_last_report_count: int = Field(ge=0)


class SummaryBullet(StrictModel):
    label: Literal["Progress", "Risk", "Decision", "Next", "Note"]
    text: str = Field(min_length=1)
    severity: Severity


class ExecutiveSummary(StrictModel):
    bullets: list[SummaryBullet] = Field(min_length=1, max_length=5)
    next_update_at_local: str | None = None


class BlockerItem(StrictModel):
    task_id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str = Field(min_length=1)
    assignee: str | None = None
    status: KanbanStatus = KanbanStatus.blocked
    severity: RiskLevel
    blocked_reason: str = Field(min_length=1)
    blocked_since_local: str | None = None
    blocked_age_label: str | None = None
    needed_next: str = Field(min_length=1)
    last_comment_excerpt: str | None = None


class BlockersSection(StrictModel):
    items: list[BlockerItem]
    empty_message: str = "No blocked tasks right now."


class ChangeItem(StrictModel):
    timestamp_local: str = Field(min_length=1)
    event_type: ChangeEventType
    task_id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str = Field(min_length=1)
    assignee: str | None = None
    summary: str = Field(min_length=1)
    severity: Severity


class ChangesSection(StrictModel):
    window_start_local: str | None = None
    window_end_local: str = Field(min_length=1)
    items: list[ChangeItem]
    omitted_count: int = Field(default=0, ge=0)


class ActiveItem(StrictModel):
    task_id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str = Field(min_length=1)
    status: KanbanStatus
    assignee: str | None = None
    last_update_local: str = Field(min_length=1)
    last_update_age_label: str = Field(min_length=1)
    current_signal: str = Field(min_length=1)
    priority: int | None = None
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)


class ActiveSection(StrictModel):
    items: list[ActiveItem]


class CompletedItem(StrictModel):
    task_id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str = Field(min_length=1)
    assignee: str | None = None
    completed_at_local: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    metadata_highlights: list[str] = Field(default_factory=list, max_length=3)


class CompletedSection(StrictModel):
    items: list[CompletedItem]
    omitted_count: int = Field(default=0, ge=0)
    empty_message: str = "No completed tasks during this reporting window."


class RiskThreshold(StrictModel):
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)


class RiskItem(StrictModel):
    task_id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str = Field(min_length=1)
    risk_level: RiskLevel
    risk_reason: str = Field(min_length=1)
    age_label: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class RisksSection(StrictModel):
    thresholds: list[RiskThreshold]
    items: list[RiskItem]


class DependencyItem(StrictModel):
    task_id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str = Field(min_length=1)
    waiting_on_task_ids: list[str]
    unblocked_when: str = Field(min_length=1)


class DependenciesSection(StrictModel):
    root_count: int = Field(ge=0)
    with_children_count: int = Field(ge=0)
    waiting_on_parents_count: int = Field(ge=0)
    items: list[DependencyItem]


class StatusCount(StrictModel):
    status: KanbanStatus
    count: int = Field(ge=0)


class AssigneeCount(StrictModel):
    assignee: str = Field(min_length=1)
    todo: int = Field(ge=0)
    ready: int = Field(ge=0)
    running: int = Field(ge=0)
    blocked: int = Field(ge=0)
    done: int = Field(ge=0)
    total: int = Field(ge=0)


class Appendix(StrictModel):
    status_counts: list[StatusCount]
    assignee_counts: list[AssigneeCount]


class Delivery(StrictModel):
    summary_line: str = Field(min_length=1)
    primary_risk_line: str = Field(min_length=1)
    next_run_line: str | None = None
    attachment_path: str | None = None
    media_tag: str | None = None
    filename: str | None = None

    @model_validator(mode="after")
    def media_tag_matches_attachment(self) -> "Delivery":
        if self.media_tag and self.attachment_path and self.media_tag != f"MEDIA:{self.attachment_path}":
            raise ValueError("media_tag must be MEDIA:<attachment_path>")
        return self


class BoardReport(StrictModel):
    schema_version: Literal["1.0.0"]
    generated_at: datetime
    report: ReportMetadata
    health: Health
    metrics: Metrics
    summary: ExecutiveSummary
    blockers: BlockersSection
    changes: ChangesSection
    active: ActiveSection
    completed: CompletedSection
    risks: RisksSection
    dependencies: DependenciesSection
    appendix: Appendix
    delivery: Delivery

    @field_validator("schema_version")
    @classmethod
    def schema_version_is_supported(cls, value: str) -> str:
        if value != "1.0.0":
            raise ValueError("schema_version must be 1.0.0")
        return value
