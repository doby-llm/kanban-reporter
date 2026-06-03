# Project-Agnostic Kanban Reporting Architecture

## Goal

Create a reusable Hermes Kanban reporting mini-project that can be used by any repository, board, or cron job. The schema, CLI, generator, PDF renderer, and documentation must not contain product-specific branding, app-domain assumptions, product fields, or fixed board names.

The reporting pipeline emits:

1. a strict machine-readable JSON report for a Hermes Kanban board;
2. a polished operational-dashboard PDF rendered from the same JSON contract;
3. a concise delivery summary that can attach the PDF on media-capable channels such as Telegram.

Use `uv` for all Python dependency management and execution. Do not use OpenHands. Keep the solution deterministic, repo-friendly, and reusable across future projects.

## Architectural recommendation

Use deterministic extraction from Hermes Kanban data plus strict Pydantic models. Do not introduce Pydantic AI for the first version.

Preferred pattern: Clean Architecture with Hexagonal adapters around external IO.

```text
Cron job / Hermes prompt
  -> scripts/kanban_report/generate.py          # thin launcher, optional
  -> kanban_reporting/adapters/                 # Hermes board, git, CI, artifact inputs
  -> kanban_reporting/models.py                 # strict Pydantic contract + JSON Schema
  -> kanban_reporting/generator.py              # deterministic aggregation policies
  -> kanban_reporting/pdf.py                    # ReportLab renderer
  -> /tmp/kanban-report-*/                      # JSON + PDF runtime artifacts
```

The LLM can write a short human summary after reading validated JSON, but it must not invent counts, blockers, CI state, commits, or artifact paths. Correctness belongs to deterministic code and schema validation.

## Why Pydantic AI is not needed initially

Pydantic AI is not required for the core report because the primary inputs are already structured or can be normalized deterministically: Kanban task rows, status events, comments, run handoffs, git commits, CI status, and artifact metadata.

Use deterministic extraction plus Pydantic models because it gives:

- stable schema enforcement and generated JSON Schema;
- predictable diffs between report runs;
- fixture-based testing without model calls;
- lower latency and fewer moving parts on Raspberry Pi/Linux cron runs;
- lower cost and less prompt-injection exposure from task comments.

Consider Pydantic AI later only as an optional enrichment stage, for example grouping vague free-form risks. If added, it must write to optional fields such as `insights.llm_observations[]` and never be required to produce valid counts, blocker state, CI status, commits, or artifact links.

## Storage location recommendation

Recommended: keep the reusable reporting package in the consuming repository, under neutral package names.

```text
<repo>/
  pyproject.toml
  kanban_reporting/
    __init__.py
    models.py
    generator.py
    pdf.py
    cli.py
    adapters/
      hermes_kanban.py
      git.py
      ci.py
      artifacts.py
  scripts/
    kanban_report/
      generate.py
  tests/
    kanban_reporting/
      test_models.py
      test_generator.py
      test_cli_fixture.py
    fixtures/
      kanban_reporting/
        sample_board.json
  docs/
    kanban-reporting/
      architecture.md
      pdf-design.md
      schema/board-report.schema.json
```

Runtime JSON/PDF output does not need durable storage. Prefer timestamped temp directories, for example `/tmp/kanban-report-{board_slug}-{run_id}/`, and return absolute paths in the CLI envelope. Commit fixtures and docs, not generated reports.

| Location | Pros | Cons | Decision |
| --- | --- | --- | --- |
| Consuming repo | Versioned, reviewable, testable, works in CI/cron, easy to customize through config | Adds Python tooling to projects that may not otherwise use Python | Preferred |
| Shared standalone repo/package | Best long-term reuse across many projects | More packaging/release overhead before first consumer exists | Good future extraction once two projects use it |
| `~/.hermes/scripts` | Fast one-off wiring | Hidden from repo review, profile-specific, hard to reproduce, easy to drift | Avoid except for tiny wrappers |
| Hermes skill | Good for documenting agent procedure | Bad place for production code or artifacts | Do not store generator here |

## Separation of concerns

```text
kanban_reporting/
  models.py
    Owns strict schema and validation. No shell calls or IO.

  adapters/
    hermes_kanban.py
      Reads board exports/tool output/CLI JSON and normalizes it.
    git.py
      Reads commits since a time, ref, or previous report state.
    ci.py
      Reads CI status and artifacts from provider-neutral inputs.
    artifacts.py
      Normalizes build/report artifact references.

  generator.py
    Pure transformation from normalized inputs to BoardReport.
    Owns deterministic aggregation and risk policies.

  pdf.py
    Presentation-only renderer from BoardReport to PDF path.
    Must not recalculate counts or reinterpret task state.

  cli.py
    Argument parsing, path handling, output writing, envelope printing.
```

Module boundaries:

- `models.py` forbids extra properties and exposes JSON Schema.
- Adapters may depend on external tools (`hermes`, `git`, `gh`, provider APIs), but return typed neutral inputs.
- `generator.py` has no network access and should be covered by fixture tests.
- `pdf.py` renders only validated `BoardReport` data.
- The cron job calls the CLI, reads the envelope/JSON, and attaches the PDF. It does not scrape or parse board data itself.

## Strict JSON schema shape

Generate the canonical schema from Pydantic models using JSON Schema draft 2020-12. Forbid additional properties on all objects. Use generic names so the same schema works for any Hermes board.

Top-level example:

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-06-03T15:20:00+02:00",
  "report": {
    "title": "Kanban status report",
    "project_name": "Example Project",
    "board_name": "example-board",
    "source": "hermes-kanban",
    "timezone": "Europe/Zurich",
    "window": {
      "since": "2026-06-03T14:40:00+02:00",
      "until": "2026-06-03T15:20:00+02:00",
      "label": "Since previous run"
    },
    "generator": {
      "name": "kanban-reporting",
      "version": "1.0.0",
      "run_id": "20260603-152000"
    }
  },
  "board": {
    "metadata": {
      "board_id": "example-board",
      "board_name": "example-board",
      "tenant": null,
      "repo_path": "/path/to/repo",
      "git_branch": "main",
      "git_head": "abc1234"
    },
    "status_counts": {
      "triage": 0,
      "todo": 3,
      "ready": 2,
      "running": 1,
      "blocked": 1,
      "done": 8,
      "archived": 0,
      "total_active": 7
    }
  },
  "changed_since_last_update": {
    "new_tasks": [],
    "completed_tasks": [],
    "blocked_tasks": [],
    "unblocked_tasks": [],
    "status_changes": [],
    "new_comments": [],
    "new_commits": []
  },
  "running": [],
  "recently_done": [],
  "pending_next": [],
  "blockers": [],
  "human_action_required": [],
  "ci": [],
  "artifacts": [],
  "commits": [],
  "risks": [],
  "delivery": {
    "summary_line": "1 running, 2 ready, 1 blocked; reviewer action required.",
    "attachment_path": "/tmp/kanban-report-example/report.pdf",
    "attachment_media_tag": "MEDIA:/tmp/kanban-report-example/report.pdf",
    "filename": "kanban-example-board-20260603-1520-Europe-Zurich.pdf"
  }
}
```

Required model set:

- `BoardReport`: root object and schema version.
- `ReportMetadata`: project/board names, timezone, report window, generator identity.
- `BoardMetadata`: board id/name, optional tenant, optional repo/git context.
- `StatusCounts`: one integer per Kanban status plus `total_active`.
- `ChangedSinceLastUpdate`: new/completed/blocked/unblocked/status/comment/commit deltas.
- `TaskRef`: reusable normalized task reference.
- `RunningTask`: running task plus assignee, started time, latest heartbeat, stale flag.
- `CompletedTask`: completion time, summary, changed files or artifact highlights when available.
- `PendingTask`: priority/dependency readiness and recommended next step.
- `Blocker`: blocked task, reason, age, owner, severity, and whether human input is required.
- `HumanActionRequired`: normalized action list for reviewer/operator/orchestrator decisions.
- `CiStatus`: provider-neutral CI status, conclusion, URL, checked time, warnings.
- `ArtifactRef`: local path or URL, type, label, creation time, safety flag.
- `CommitRef`: sha, subject, author, timestamp, touched paths.
- `Risk`: deterministic risk, severity, source, mitigation, related task IDs.
- `Delivery`: concise summary line, PDF path, optional media tag, filename, next run label.

Representative Pydantic skeleton:

```python
from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class KanbanStatus(StrEnum):
    triage = "triage"
    todo = "todo"
    ready = "ready"
    running = "running"
    blocked = "blocked"
    done = "done"
    archived = "archived"

class TaskRef(StrictModel):
    id: str = Field(pattern=r"^t_[0-9a-f]+$")
    title: str
    status: KanbanStatus
    assignee: str | None = None
    priority: int | None = None

class ReportWindow(StrictModel):
    since: datetime | None = None
    until: datetime
    label: str

class ReportMetadata(StrictModel):
    title: str = "Kanban status report"
    project_name: str | None = None
    board_name: str
    source: str = "hermes-kanban"
    timezone: str
    window: ReportWindow

class StatusCounts(StrictModel):
    triage: int = 0
    todo: int = 0
    ready: int = 0
    running: int = 0
    blocked: int = 0
    done: int = 0
    archived: int = 0
    total_active: int

class Delivery(StrictModel):
    summary_line: str
    attachment_path: str | None = None
    attachment_media_tag: str | None = None
    filename: str | None = None

class BoardReport(StrictModel):
    schema_version: str = "1.0.0"
    generated_at: datetime
    report: ReportMetadata
    board: dict
    changed_since_last_update: dict
    running: list[TaskRef]
    recently_done: list[TaskRef]
    pending_next: list[TaskRef]
    blockers: list[dict]
    human_action_required: list[dict]
    ci: list[dict]
    artifacts: list[dict]
    commits: list[dict]
    risks: list[dict]
    delivery: Delivery
```

The production implementation should replace remaining generic `dict` fields with dedicated strict models before release. The skeleton illustrates boundaries and naming, not the final type coverage.

## PDF library recommendation

Use ReportLab for the first implementation.

Rationale:

- It works well in cron without a display server.
- It has good Linux/aarch64 viability when installed and run via `uv`.
- Tables, headings, page breaks, badges, simple charts, and document metadata are enough for an operational Kanban report.
- It avoids WeasyPrint's Cairo/Pango/native dependency chain and avoids Playwright/Chromium weight on a Raspberry Pi.

| Library | Fit | Concern |
| --- | --- | --- |
| ReportLab | Best first choice for deterministic operational PDFs | Imperative layout API, less CSS-like |
| WeasyPrint | Best HTML/CSS visual fidelity | Native dependencies can be painful on Raspberry Pi/Linux cron hosts |
| xhtml2pdf | Simple HTML-to-PDF | Lower fidelity and frequent CSS/layout surprises |
| Playwright/Chromium print | High fidelity | Heavy install and browser lifecycle overhead |
| fpdf2 | Lightweight | Weaker table/page-flow primitives for polished reports |

PDF style should be generic operational dashboard style: clean typography, neutral palette, status/risk badges with text labels, KPI cards, clear page headers, and mobile-readable tables. Do not use project-specific branding unless passed explicitly through optional configuration.

Recommended sections: Cover Summary, Human Action Required, Board Counts, Changed Since Last Update, Running Work, Recently Done, Pending/Next, Blockers/Risks, CI/Artifacts, Commits, Appendix.

## Cron/script contract

The cron job should be a thin orchestrator. It calls the repo-owned CLI, then sends the concise summary and attaches the generated PDF when the delivery channel supports attachments.

Generic command shape:

```bash
cd /path/to/repo
uv run python -m kanban_reporting.cli \
  --board <board-slug> \
  --project-name "<optional display name>" \
  --since-state /tmp/kanban-report-state-<board-slug>.json \
  --out-dir /tmp/kanban-report-<board-slug>-$(date +%Y%m%d-%H%M%S) \
  --format json,pdf
```

The CLI prints a strict one-line JSON envelope to stdout:

```json
{
  "ok": true,
  "schema_version": "1.0.0",
  "json_path": "/tmp/kanban-report-example/report.json",
  "pdf_path": "/tmp/kanban-report-example/report.pdf",
  "requires_human": true,
  "headline": "1 running, 2 ready, 1 blocked; reviewer action required",
  "delivery_text": "Kanban report: 1 running, 2 ready, 1 blocked. PDF attached.",
  "media_tag": "MEDIA:/tmp/kanban-report-example/report.pdf"
}
```

Contract rules:

- Exit code `0`: JSON and PDF were written and schema validation passed.
- Exit code `2`: input/board extraction failed; cron reports failure and does not invent data.
- Exit code `3`: schema validation failed; cron reports validation failure and blocks for investigation.
- Exit code `4`: PDF rendering failed after valid JSON; cron may send JSON-derived text and flag missing PDF.
- stdout is the envelope only; logs go to stderr.
- `pdf_path` must be an absolute path.
- `media_tag` is included only for platforms that support `MEDIA:` attachment interception, especially Telegram. CLI/terminal logs should show the plain path.
- The generator updates `--since-state` only after successful JSON and PDF writes.

## Migration path for an existing cron job

1. Commit this project-agnostic architecture spec.
2. Implement neutral package paths (`kanban_reporting/...`), Pydantic models, fixture tests, deterministic generator, ReportLab renderer, and CLI using `uv` only.
3. Use `/tmp` for generated JSON/PDF by default. Keep persistent state either in `/tmp` for ephemeral reporting or in a repo/gitignored path only if deltas must survive reboot.
4. Run local validation:
   - `uv run pytest tests/kanban_reporting -q`
   - `uv run python -m kanban_reporting.cli --fixture tests/fixtures/kanban_reporting/sample_board.json --out-dir /tmp/kanban-report-fixture --format json,pdf`
   - `git diff --check`
5. Update the target cron job so its prompt/script runs the CLI first, reads the validated JSON/envelope, writes a very short Telegram message from the JSON, and includes the PDF media tag in Telegram delivery.
6. Keep the existing schedule and target workdir initially; pass the board slug, project label, and output directory as configuration instead of hardcoding them.
7. Run the cron job once manually and verify Telegram receives concise text plus the PDF attachment.
8. After two successful runs, remove old prose-only extraction instructions from the cron prompt.

Note: the implementation worker or orchestrator should confirm the target cron job id/profile before editing it.

## Scalability and bottlenecks

- Board size: consume exported/paginated board snapshots instead of rendering full event history in prompts.
- Data volume: keep raw snapshots separate from compact reports; cap comments and move long evidence to appendices.
- Concurrency: write into unique `/tmp/kanban-report-*` directories and update since-state with atomic rename.
- CI/API limits: query CI once per report run, not once per task.
- PDF growth: cap routine reports to a small page count and omit low-signal completed/archived detail by default.
- Multi-project reuse: keep all project-specific labels in CLI options/config, never hardcoded in schema or renderer.
- LLM reliability: the LLM consumes validated JSON only; deterministic code owns counts and risk rules.

## Implementation plan

1. Create the neutral Python package and `uv` configuration.
2. Add strict Pydantic models and JSON Schema export.
3. Add fixtures for empty, active, blocked, and recently completed boards.
4. Build deterministic generator tests before implementation.
5. Add Hermes Kanban, git, CI, and artifact adapters behind interfaces.
6. Add ReportLab PDF renderer with smoke checks: file exists, non-empty, at least one page/text marker.
7. Add CLI envelope behavior and Telegram media-tag support.
8. Update a target cron job only after fixture generation succeeds.

## Recommended committed paths and modules

Recommended paths:

- `pyproject.toml`
- `kanban_reporting/models.py`
- `kanban_reporting/generator.py`
- `kanban_reporting/pdf.py`
- `kanban_reporting/cli.py`
- `kanban_reporting/adapters/hermes_kanban.py`
- `kanban_reporting/adapters/git.py`
- `kanban_reporting/adapters/ci.py`
- `kanban_reporting/adapters/artifacts.py`
- `scripts/kanban_report/generate.py`
- `tests/kanban_reporting/test_models.py`
- `tests/kanban_reporting/test_generator.py`
- `tests/kanban_reporting/test_cli_fixture.py`
- `tests/fixtures/kanban_reporting/sample_board.json`
- `docs/kanban-reporting/architecture.md`
- `docs/kanban-reporting/schema/board-report.schema.json`

Schema modules:

- `BoardReport`
- `ReportMetadata`
- `BoardMetadata`
- `StatusCounts`
- `ChangedSinceLastUpdate`
- `TaskRef`
- `RunningTask`
- `CompletedTask`
- `PendingTask`
- `Blocker`
- `HumanActionRequired`
- `CiStatus`
- `ArtifactRef`
- `CommitRef`
- `Risk`
- `Delivery`
