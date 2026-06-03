# Kanban reporting

This directory documents the project-agnostic Hermes Kanban reporting mini-project. The implementation lives in the neutral `kanban_reporting/` Python package and intentionally avoids product-specific branding, fields, or app-domain assumptions.

## Generate from the sample fixture

Use `uv` for every Python command:

```bash
uv run pytest tests/kanban_reporting -q
uv run python -m kanban_reporting.cli \
  --fixture tests/fixtures/kanban_reporting/sample_board.json \
  --out-dir /tmp/kanban-report-fixture \
  --format json,pdf
```

The CLI prints a one-line JSON envelope on stdout. On success it contains:

- `json_path`: absolute path to the validated report JSON.
- `pdf_path`: absolute path to the rendered PDF.
- `delivery_text`: concise text suitable for the normal status summary.
- `media_tag`: `MEDIA:/absolute/path.pdf` for Telegram or other Hermes media-capable gateways.

## Generate JSON Schema

```bash
uv run python -m kanban_reporting.cli \
  --schema \
  --out-dir docs/kanban-reporting/schema
```

The schema is generated from strict Pydantic models with `extra="forbid"` so unknown fields fail fast.

## Input contract

The current CLI accepts either:

- `--fixture <snapshot.json>`: a project-agnostic board snapshot containing board metadata, task rows, and change events; or
- `--input-report <report.json>`: an already validated `BoardReport` JSON payload to render/write; or
- `--live-board <board-slug>`: a live Hermes Kanban board collected from `hermes kanban --board <slug> list --json`, normalized into the same project-agnostic snapshot contract, then rendered.

Live Kanban facts must be normalized into explicit JSON before the renderer runs. The package should not invent counts, blockers, statuses, CI state, commits, or artifact paths.

## Generate from a live Hermes Kanban board

Use this form from cron jobs and operational reports. It writes temporary JSON/PDF artifacts under `/tmp` and prints a JSON envelope containing `delivery_text` and `media_tag`.

```bash
uv run python -m kanban_reporting.cli \
  --live-board example-board \
  --project-name "Example Project" \
  --job-id example-report-job \
  --window-minutes 40 \
  --timezone Europe/Zurich \
  --out-dir /tmp/kanban-report-example-board \
  --format json,pdf
```

If `hermes` is not on PATH, pass `--hermes-cli /absolute/path/to/hermes` or set `HERMES_CLI=/absolute/path/to/hermes`. The adapter resolves the command in this order: explicit CLI flag, `HERMES_CLI`, then `hermes` on PATH. When running under `uv`, a resolved Hermes launcher named `hermes` is wrapped with `/usr/bin/python3` by default so it does not accidentally import from the project virtualenv; override with `HERMES_CLI_PYTHON=/absolute/path/to/python3` if needed.

Cron delivery pattern:

1. Run the live-board command above with a unique `/tmp` output directory.
2. Parse stdout JSON.
3. If `ok=true` and `media_tag` is present, include a 2-3 sentence cover note plus the `MEDIA:/absolute/path.pdf` line in the final Hermes response.
4. If generation fails, send a concise text fallback with the command stderr and the key board actions/blockers observed by the normal cron inspection.

Rollback for cron integration: remove the live-board command from the cron prompt or restore cron job `6b9b2fb0665a` from the previous `~/.hermes/cron/jobs.json` backup, then restart/let the scheduler reload.

## Exit codes

- `0`: JSON/PDF generation succeeded.
- `2`: input or board extraction failed.
- `3`: strict schema validation failed.
- `4`: report generation or PDF rendering failed after validation.
