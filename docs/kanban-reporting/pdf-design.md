# Project-Agnostic Kanban PDF Report Design

## Purpose

Create a Telegram-friendly PDF companion to a Hermes Kanban status summary. The PDF should let an operator quickly answer four questions from a phone screen:

1. What changed since the last report?
2. What is blocked or risky right now?
3. Which work is ready, running, or done?
4. What should happen next?

The Telegram message should be a very short notification: two or three sentences at most, naming what the PDF contains and any urgent human action. The PDF is the structured, scannable artifact for deeper review and forwarding. The design is intentionally project-agnostic: no product branding, app-domain assumptions, product-specific fields, or fixed board names. Any consumer must be configured through generic values only.

## Design principles

- Mobile-first reading: assume the PDF opens in Telegram's viewer on a narrow phone screen.
- Skimmable before detailed: health, blockers, and next actions must appear before full task tables.
- Operational dashboard aesthetic: clean, professional, neutral, and moderately polished without product branding.
- Statuses must work without color: every badge includes text, and risk is reinforced by labels or icons.
- Dense but not cramped: prefer short rows, grouped sections, and page breaks over tiny type.
- Reusable schema: every visual section maps to explicit required JSON fields so the generator can fail fast when data is missing.

## Page format

- Page size: A4 portrait.
- Margins: 18 mm top, 16 mm left/right, 18 mm bottom.
- Header height: 26-32 mm on page 1; 12-16 mm on continuation pages.
- Footer: page number, board name, report timestamp, and optional confidentiality label.
- Recommended maximum: 6 pages for routine reports. If more than 6 pages are needed, collapse done/archived detail and include only the most recent completed items.

## Visual treatment

### Typography

Use a reliable sans-serif stack for PDF generation:

- Primary: Inter, Plus Jakarta Sans, Noto Sans, or DejaVu Sans.
- Title: 20-22 pt, 700 weight, line-height 1.2.
- Section heading: 13-15 pt, 700 weight, line-height 1.25.
- Body/table text: 9.5-10.5 pt, 400 weight, line-height 1.35.
- Small metadata: 8-9 pt, 500 weight, line-height 1.3.
- Badge text: 8-9 pt, 700 weight, uppercase or title case.

Avoid body text below 9 pt because Telegram's PDF preview compresses pages.

### Color palette

Use neutral operational colors that remain readable in print/PDF and do not imply any product brand.

| Token | Use | Color | Text |
| --- | --- | --- | --- |
| `ink` | Primary text | `#172026` | n/a |
| `muted_ink` | Secondary text | `#5B6870` | n/a |
| `surface` | Page background | `#F6F8FA` | `#172026` |
| `card` | Section cards | `#FFFFFF` | `#172026` |
| `outline` | Rules/borders | `#DDE3EA` | n/a |
| `accent` | Primary operational accent | `#2457C5` | `#FFFFFF` |
| `accent_soft` | Soft accent chip | `#E8F0FF` | `#163B87` |
| `info` | Informational | `#006591` | `#FFFFFF` |
| `info_soft` | Soft info chip | `#E2F3FF` | `#004C6E` |
| `warning` | At risk / needs attention | `#A15C00` | `#FFFFFF` |
| `warning_soft` | Soft warning chip | `#FFF1D6` | `#6B4100` |
| `danger` | Blocked / failed | `#BA1A1A` | `#FFFFFF` |
| `danger_soft` | Soft danger chip | `#FFDAD6` | `#93000A` |
| `success` | Done / healthy | `#0B6B35` | `#FFFFFF` |
| `success_soft` | Soft success chip | `#DDF8E7` | `#084B27` |

### Status badges

Badges should be rounded pills with 4-5 px vertical padding and 8-10 px horizontal padding. Always include readable text.

| Status | Label | Background | Text color | Optional icon |
| --- | --- | --- | --- | --- |
| `triage` | Triage | `#EEE7FF` | `#3D1A78` | `?` |
| `todo` | Todo | `#E8ECEF` | `#3F4D56` | `•` |
| `ready` | Ready | `#E2F3FF` | `#004C6E` | `→` |
| `running` | Running | `#E8F0FF` | `#163B87` | `▶` |
| `blocked` | Blocked | `#FFDAD6` | `#93000A` | `!` |
| `done` | Done | `#DDF8E7` | `#084B27` | `✓` |
| `archived` | Archived | `#F0F1F2` | `#52615C` | `×` |

Risk/severity badges:

- `critical`: solid `danger`, white text, `CRITICAL`.
- `high`: `danger_soft`, `#93000A`, `HIGH`.
- `medium`: `warning_soft`, `#6B4100`, `MEDIUM`.
- `low`: `info_soft`, `#004C6E`, `LOW`.
- `none`: `success_soft`, `#084B27`, `OK`.

## Report hierarchy

### 1. Cover summary: report header + current health

Goal: communicate the board state in the first 10 seconds.

Layout:

- Left: title block.
- Right: generated timestamp and run metadata.
- Under title: 3-5 KPI cards.
- Health banner below KPI cards: one sentence summary with severity styling.

Required fields:

- `report.title`
- `report.project_name` optional
- `report.board_name`
- `report.generated_at_local`
- `report.timezone`
- `report.window_label`
- `report.job_id` optional
- `report.run_id` or stable generation identifier
- `health.level`: `ok | attention | blocked | critical`
- `health.summary`
- `metrics.total_tasks`
- `metrics.running_count`
- `metrics.blocked_count`
- `metrics.ready_count`
- `metrics.done_since_last_report_count`
- `metrics.changed_since_last_report_count`

KPI card layout:

| Card | Primary number | Secondary label | Styling |
| --- | --- | --- | --- |
| Board total | `total_tasks` | `tasks tracked` | neutral |
| Running | `running_count` | `in progress` | accent soft |
| Blocked | `blocked_count` | `need input` | danger if > 0, neutral if 0 |
| Ready | `ready_count` | `ready to pick up` | info soft |
| Done | `done_since_last_report_count` | `completed this window` | success soft |

### 2. Executive summary

Goal: provide the human-readable digest that pairs with the message body.

Layout:

- Card with 3-5 bullets.
- Each bullet starts with a label: `Progress`, `Risk`, `Decision`, `Next`, or `Note`.
- Keep bullets to one or two lines each.

Required fields:

- `summary.bullets[]`
  - `label`
  - `text`
  - `severity`: `info | success | warning | danger`
- `summary.next_update_at_local` if another scheduled run is known.

### 3. Blockers and decisions needed

Goal: make human intervention obvious. This section appears even when empty.

Layout:

- If blocked items exist: table grouped by severity, highest first.
- If none: quiet empty-state card: `No blocked tasks right now.`
- Each blocker row gets enough vertical spacing for a one-sentence reason.

Table columns:

| Column | Width guidance | Content |
| --- | --- | --- |
| Task | 22% | Short title, task ID in muted text below |
| Owner | 14% | Assignee/profile |
| Block reason | 36% | One-sentence reason, wrap up to 3 lines |
| Age | 10% | Time blocked or time since last event |
| Needed next | 18% | Decision/action required |

Required fields:

- `blockers.items[]`
  - `task_id`
  - `title`
  - `assignee`
  - `status`
  - `severity`
  - `blocked_reason`
  - `blocked_since_local` or `blocked_age_label`
  - `needed_next`
  - `last_comment_excerpt` optional
- `blockers.empty_message`

### 4. Changes since last report

Goal: answer what changed during the report window.

Layout:

- Timeline-style list for up to 12 high-signal events.
- If there are more, include a compact `+N more low-signal events` footer.
- Use event-type chips for completed, blocked, unblocked, created, reassigned, and failed.

Required fields:

- `changes.window_start_local`
- `changes.window_end_local`
- `changes.items[]`
  - `timestamp_local`
  - `event_type`: `created | claimed | completed | blocked | unblocked | failed | reassigned | commented | archived`
  - `task_id`
  - `title`
  - `assignee`
  - `summary`
  - `severity`
- `changes.omitted_count`

### 5. Active work table

Goal: show current running/ready/todo work in a compact operational view.

Layout:

- Sort order: blocked, running, ready, todo, triage.
- Split into subsections if there are more than 18 active rows.
- Repeat header row after page breaks.
- Keep task titles to two lines; include details in notes only when critical.

Table columns:

| Column | Width guidance | Content |
| --- | --- | --- |
| Status | 13% | Badge |
| Task | 30% | Title + task ID below |
| Assignee | 14% | Profile/person |
| Last update | 13% | Relative age, e.g. `12m ago` |
| Current signal | 30% | Latest summary/comment/error excerpt |

Required fields:

- `active.items[]`
  - `task_id`
  - `title`
  - `status`
  - `assignee`
  - `last_update_local`
  - `last_update_age_label`
  - `current_signal`
  - `priority` optional
  - `parent_ids` optional
  - `child_ids` optional

### 6. Completed work

Goal: show progress while keeping the report short.

Layout:

- Table of tasks completed during the reporting window.
- Limit to the most recent 10 by default.
- If no completed work: compact empty state.

Required fields:

- `completed.items[]`
  - `task_id`
  - `title`
  - `assignee`
  - `completed_at_local`
  - `summary`
  - `metadata_highlights[]` optional, max 3 short strings
- `completed.omitted_count`
- `completed.empty_message`

### 7. Risks, aging, and SLA cues

Goal: surface tasks that may not be blocked yet but need attention.

Suggested deterministic risk rules:

- Running for more than 60 minutes without heartbeat: high.
- Ready for more than 2 reporting windows: medium.
- Blocked for more than 1 hour: high.
- Failed/crashed/timed out in latest run: high or critical.
- Parent done but child not ready: medium.

Required fields:

- `risks.thresholds[]`
  - `label`
  - `description`
- `risks.items[]`
  - `task_id`
  - `title`
  - `risk_level`
  - `risk_reason`
  - `age_label`
  - `recommended_action`

### 8. Dependency snapshot

Goal: show whether board flow is logically moving.

Layout:

- Small summary row with counts: root tasks, tasks with children, waiting on parents.
- Optional compact dependency table for tasks waiting on relationships.
- Avoid full graph rendering unless the board is tiny.

Required fields:

- `dependencies.root_count`
- `dependencies.with_children_count`
- `dependencies.waiting_on_parents_count`
- `dependencies.items[]`
  - `task_id`
  - `title`
  - `waiting_on_task_ids[]`
  - `unblocked_when`

### 9. Appendix: raw board counts

Goal: provide complete counts without cluttering the main narrative.

Required fields:

- `appendix.status_counts[]`
  - `status`
  - `count`
- `appendix.assignee_counts[]`
  - `assignee`
  - `todo`
  - `ready`
  - `running`
  - `blocked`
  - `done`
  - `total`

## Mobile readability rules

- Use portrait pages and single-column content except for KPI cards and small risk cards.
- Avoid landscape tables. If a table needs more columns, remove lower-value columns or move details into a second line inside the same cell.
- Keep prose line length around 55-75 characters.
- Use row striping with subtle contrast (`#FFFFFF` / `#F3F6FA`) for tables over 6 rows.
- Repeat table headers after page breaks.
- Avoid splitting a task row across pages when the PDF library supports it.
- Keep first page self-contained: the reader should understand overall health without scrolling.
- Put IDs in muted smaller text below titles, not as the primary label.

## Accessibility and readability constraints

- Text contrast should meet WCAG AA: 4.5:1 for body text and 3:1 for large/bold text.
- Badge foreground/background pairs must meet at least 3:1 and include text labels.
- Do not encode status by icon or color alone.
- Use semantic headings in the PDF generation layer if the renderer supports tagged PDFs.
- Include document metadata: title, author/tool, creation date, and board name.
- Avoid red/green-only comparisons; pair status with labels like `Blocked` and `Done`.
- Avoid dense all-caps outside short badges.
- Ensure every generated PDF has a text layer, not screenshot-only pages.
- Use local timezone labels explicitly, e.g. `Europe/Zurich`.

## Visual states for the generator

### Empty board state

If no tasks exist:

- Header health: `ok`.
- KPI cards show zero counts.
- Executive summary states: `No Kanban tasks are currently tracked on board <board_name>.`
- Hide blockers, changes, active, completed, risks, and dependencies behind compact empty cards.

### No-change state

If the board exists but nothing changed since the last report:

- Keep KPI cards and active work table.
- Changes section empty card: `No task events during this reporting window.`
- Delivery summary should still state the next scheduled run when known.

### Error state

If report generation fails:

- Do not attach a broken or partial PDF.
- Delivery text should include board name, timestamp, failure category, and fallback prose summary if available.
- Save failing JSON payload and generator logs locally when safe.

Required error fields for a fallback summary:

- `error.generated_at_local`
- `error.board_name`
- `error.error_type`
- `error.error_message_safe`
- `error.fallback_summary`
- `error.debug_artifact_path` optional local path only, never a media tag unless intentionally attaching a safe log.

### Success state

Telegram delivery should include:

- concise prose summary;
- PDF attachment;
- filename that makes board and run window obvious;
- next scheduled run when relevant.

## Suggested PDF filename

Use a stable, sortable, human-readable filename:

`kanban-{board_slug}-{YYYYMMDD-HHMM}-{timezone_slug}.pdf`

Example:

`kanban-example-board-20260603-1730-Europe-Zurich.pdf`

Rules:

- Use local report time, not UTC, unless the board explicitly operates in UTC.
- Replace `/` in timezone names with `-`.
- Keep filename under 80 characters for Telegram readability.
- If multiple reports can be generated in the same minute, append a short run ID: `-r{run_id}`.

## Suggested Telegram message with attachment

Short format:

`Kanban report for example-board: 2 running, 1 blocked, 3 ready, 4 done since last update. Main risk: release approval is blocking a review task. Next run around 18:10 Europe/Zurich.`

With PDF attachment:

`MEDIA:/tmp/kanban-report-example-board/report.pdf`

In the cron implementation, the media line should be included only on messaging platforms that intercept `MEDIA:` attachments. For CLI logs or non-media channels, use the plain absolute file path instead.

Required delivery fields:

- `delivery.summary_line`
- `delivery.primary_risk_line`
- `delivery.next_run_line`
- `delivery.attachment_path`
- `delivery.media_tag`
- `delivery.filename`

## Recommended JSON coverage checklist

The schema worker should ensure the payload can populate these top-level objects:

- `report`
- `health`
- `metrics`
- `summary`
- `blockers`
- `changes`
- `active`
- `completed`
- `risks`
- `dependencies`
- `appendix`
- `delivery`

Minimum viable PDF requires: `report`, `health`, `metrics`, `summary`, `blockers`, `changes`, `active`, and `delivery`.

## Acceptance criteria for the coder

- The PDF first page includes header metadata, health banner, KPI cards, executive summary, and blockers or blocker empty state.
- The generator maps every section to explicit JSON fields and fails with a clear validation error when minimum viable fields are missing.
- Status and risk badges use text labels with non-color cues.
- Tables repeat headers across page breaks and avoid splitting task rows when supported.
- Routine reports remain readable in Telegram mobile preview: body text is at least 9 pt, margins are not excessive, and important content appears on page 1.
- Empty, no-change, error, and success states are handled intentionally.
- PDF filename follows `kanban-{board_slug}-{YYYYMMDD-HHMM}-{timezone_slug}.pdf` and delivery text references the attachment clearly.
- Generated PDFs include a real text layer and basic document metadata.
- The implementation uses `uv` for Python dependency management and running scripts.
- The cron job can send concise prose summary and attach the generated PDF when the target platform supports media attachments.
