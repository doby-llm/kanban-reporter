from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import BoardReport, KanbanStatus, RiskLevel, Severity

PALETTE = {
    "ink": colors.HexColor("#172026"),
    "muted": colors.HexColor("#5B6870"),
    "surface": colors.HexColor("#F6F8FA"),
    "card": colors.white,
    "outline": colors.HexColor("#DDE3EA"),
    "accent": colors.HexColor("#2457C5"),
    "accent_soft": colors.HexColor("#E8F0FF"),
    "info_soft": colors.HexColor("#E2F3FF"),
    "warning_soft": colors.HexColor("#FFF1D6"),
    "danger_soft": colors.HexColor("#FFDAD6"),
    "success_soft": colors.HexColor("#DDF8E7"),
}

STATUS_COLORS = {
    KanbanStatus.triage: (colors.HexColor("#EEE7FF"), colors.HexColor("#3D1A78")),
    KanbanStatus.todo: (colors.HexColor("#E8ECEF"), colors.HexColor("#3F4D56")),
    KanbanStatus.ready: (PALETTE["info_soft"], colors.HexColor("#004C6E")),
    KanbanStatus.running: (PALETTE["accent_soft"], colors.HexColor("#163B87")),
    KanbanStatus.blocked: (PALETTE["danger_soft"], colors.HexColor("#93000A")),
    KanbanStatus.done: (PALETTE["success_soft"], colors.HexColor("#084B27")),
    KanbanStatus.archived: (colors.HexColor("#F0F1F2"), colors.HexColor("#52615C")),
}

RISK_COLORS = {
    RiskLevel.critical: (colors.HexColor("#BA1A1A"), colors.white),
    RiskLevel.high: (PALETTE["danger_soft"], colors.HexColor("#93000A")),
    RiskLevel.medium: (PALETTE["warning_soft"], colors.HexColor("#6B4100")),
    RiskLevel.low: (PALETTE["info_soft"], colors.HexColor("#004C6E")),
    RiskLevel.none: (PALETTE["success_soft"], colors.HexColor("#084B27")),
}


def render_pdf(report: BoardReport, output_path: str | Path | None = None) -> Path:
    """Render a validated BoardReport to a text-layer ReportLab PDF."""
    path = Path(output_path or report.delivery.attachment_path or report.delivery.filename or "kanban-report.pdf").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=report.report.title,
        author="kanban-reporting",
        subject=f"Kanban report for {report.report.board_name}",
    )
    styles = _styles()
    story = [
        _header(report, styles),
        Spacer(1, 8),
        _kpi_table(report, styles),
        Spacer(1, 8),
        _health_banner(report, styles),
        Spacer(1, 10),
        _section_title("Executive summary", styles),
        _bullets(report, styles),
        Spacer(1, 8),
        _section_title("Blockers and decisions needed", styles),
        _blockers(report, styles),
        Spacer(1, 8),
        _section_title("Changes since last report", styles),
        _changes(report, styles),
        Spacer(1, 8),
        _section_title("Active work", styles),
        _active(report, styles),
        Spacer(1, 8),
        _section_title("Completed work", styles),
        _completed(report, styles),
        Spacer(1, 8),
        _section_title("Risks and dependency snapshot", styles),
        _risks_and_dependencies(report, styles),
        Spacer(1, 8),
        _section_title("Appendix: raw board counts", styles),
        _appendix(report, styles),
    ]
    doc.build(story, onFirstPage=_footer(report), onLaterPages=_footer(report))
    return path


def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=PALETTE["ink"], alignment=TA_LEFT, spaceAfter=4))
    base.add(ParagraphStyle("Meta", parent=base["Normal"], fontSize=8.5, leading=11, textColor=PALETTE["muted"]))
    base.add(ParagraphStyle("Section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=PALETTE["ink"], spaceBefore=4, spaceAfter=5))
    base.add(ParagraphStyle("Body", parent=base["Normal"], fontSize=9.6, leading=13, textColor=PALETTE["ink"]))
    base.add(ParagraphStyle("Small", parent=base["Normal"], fontSize=8.4, leading=11, textColor=PALETTE["muted"]))
    base.add(ParagraphStyle("Badge", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, alignment=TA_CENTER))
    return base


def _header(report: BoardReport, styles) -> Table:
    left = [Paragraph(report.report.title, styles["ReportTitle"]), Paragraph(f"Board: <b>{report.report.board_name}</b>", styles["Body"])]
    if report.report.project_name:
        left.append(Paragraph(f"Project: {report.report.project_name}", styles["Meta"]))
    right = Paragraph(
        f"Generated: <b>{report.report.generated_at_local}</b><br/>Timezone: {report.report.timezone}<br/>Window: {report.report.window_label}<br/>Run: {report.report.generator.run_id}",
        styles["Meta"],
    )
    table = Table([[left, right]], colWidths=[112 * mm, 54 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALETTE["card"]), ("BOX", (0, 0), (-1, -1), 0.7, PALETTE["outline"]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return table


def _kpi_table(report: BoardReport, styles) -> Table:
    cards = [
        (report.metrics.total_tasks, "tasks tracked", PALETTE["card"]),
        (report.metrics.running_count, "in progress", PALETTE["accent_soft"]),
        (report.metrics.blocked_count, "need input", PALETTE["danger_soft"] if report.metrics.blocked_count else PALETTE["card"]),
        (report.metrics.ready_count, "ready", PALETTE["info_soft"]),
        (report.metrics.done_since_last_report_count, "done this window", PALETTE["success_soft"]),
    ]
    row = []
    for number, label, bg in cards:
        row.append(Paragraph(f"<font size='17'><b>{number}</b></font><br/><font color='#5B6870'>{label}</font>", styles["Body"]))
    table = Table([row], colWidths=[33.2 * mm] * 5)
    commands = [("BOX", (0, 0), (-1, -1), 0.7, PALETTE["outline"]), ("GRID", (0, 0), (-1, -1), 0.4, PALETTE["outline"]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]
    for idx, (_, _, bg) in enumerate(cards):
        commands.append(("BACKGROUND", (idx, 0), (idx, 0), bg))
    table.setStyle(TableStyle(commands))
    return table


def _health_banner(report: BoardReport, styles) -> Table:
    bg = {"ok": PALETTE["success_soft"], "attention": PALETTE["warning_soft"], "blocked": PALETTE["danger_soft"], "critical": colors.HexColor("#BA1A1A")}[report.health.level.value]
    table = Table([[Paragraph(f"<b>{report.health.level.value.title()}</b>: {report.health.summary}", styles["Body"])]], colWidths=[166 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 0.7, PALETTE["outline"]), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return table


def _section_title(title: str, styles) -> Paragraph:
    return Paragraph(title, styles["Section"])


def _bullets(report: BoardReport, styles):
    rows = [[_severity_badge(b.severity, styles), Paragraph(f"<b>{b.label}</b> — {b.text}", styles["Body"])] for b in report.summary.bullets]
    if report.summary.next_update_at_local:
        rows.append([_severity_badge(Severity.info, styles), Paragraph(f"<b>Next</b> — {report.summary.next_update_at_local}", styles["Body"])])
    return _card_table(rows, [24 * mm, 142 * mm])


def _blockers(report: BoardReport, styles):
    if not report.blockers.items:
        return _empty(report.blockers.empty_message, styles)
    rows = [[Paragraph("Task", styles["Small"]), Paragraph("Owner", styles["Small"]), Paragraph("Reason", styles["Small"]), Paragraph("Age", styles["Small"]), Paragraph("Needed next", styles["Small"])] ]
    for item in report.blockers.items:
        rows.append([
            Paragraph(f"<b>{item.title}</b><br/><font color='#5B6870'>{item.task_id}</font>", styles["Body"]),
            Paragraph(item.assignee or "unassigned", styles["Body"]),
            Paragraph(item.blocked_reason, styles["Body"]),
            Paragraph(item.blocked_age_label or "unknown", styles["Body"]),
            Paragraph(item.needed_next, styles["Body"]),
        ])
    return _table(rows, [37 * mm, 22 * mm, 52 * mm, 16 * mm, 39 * mm])


def _changes(report: BoardReport, styles):
    if not report.changes.items:
        return _empty("No task events during this reporting window.", styles)
    rows = []
    for change in report.changes.items:
        rows.append([_severity_badge(change.severity, styles), Paragraph(f"<b>{change.event_type.value.title()}</b> {change.title}<br/><font color='#5B6870'>{change.timestamp_local} · {change.task_id} · {change.assignee or 'unassigned'}</font><br/>{change.summary}", styles["Body"])])
    if report.changes.omitted_count:
        rows.append([Paragraph("+", styles["Badge"]), Paragraph(f"{report.changes.omitted_count} additional low-signal event(s) omitted.", styles["Body"])])
    return _card_table(rows, [18 * mm, 148 * mm])


def _active(report: BoardReport, styles):
    if not report.active.items:
        return _empty("No active tasks right now.", styles)
    rows = [[Paragraph("Status", styles["Small"]), Paragraph("Task", styles["Small"]), Paragraph("Assignee", styles["Small"]), Paragraph("Last update", styles["Small"]), Paragraph("Current signal", styles["Small"])] ]
    for item in report.active.items:
        rows.append([_status_badge(item.status, styles), Paragraph(f"<b>{item.title}</b><br/><font color='#5B6870'>{item.task_id}</font>", styles["Body"]), Paragraph(item.assignee or "unassigned", styles["Body"]), Paragraph(item.last_update_age_label, styles["Body"]), Paragraph(item.current_signal, styles["Body"])])
    return _table(rows, [24 * mm, 50 * mm, 24 * mm, 24 * mm, 44 * mm])


def _completed(report: BoardReport, styles):
    if not report.completed.items:
        return _empty(report.completed.empty_message, styles)
    rows = [[Paragraph("Task", styles["Small"]), Paragraph("Owner", styles["Small"]), Paragraph("Completed", styles["Small"]), Paragraph("Summary", styles["Small"])] ]
    for item in report.completed.items:
        highlights = f"<br/><font color='#5B6870'>{', '.join(item.metadata_highlights)}</font>" if item.metadata_highlights else ""
        rows.append([Paragraph(f"<b>{item.title}</b><br/><font color='#5B6870'>{item.task_id}</font>", styles["Body"]), Paragraph(item.assignee or "unassigned", styles["Body"]), Paragraph(item.completed_at_local, styles["Body"]), Paragraph(item.summary + highlights, styles["Body"])])
    return _table(rows, [45 * mm, 25 * mm, 34 * mm, 62 * mm])


def _risks_and_dependencies(report: BoardReport, styles):
    risk_rows = [[_risk_badge(item.risk_level, styles), Paragraph(f"<b>{item.title}</b> — {item.risk_reason}<br/><font color='#5B6870'>{item.age_label}; {item.recommended_action}</font>", styles["Body"])] for item in report.risks.items]
    if not risk_rows:
        risk_rows = [[_risk_badge(RiskLevel.none, styles), Paragraph("No deterministic risks detected beyond normal board flow.", styles["Body"])]]
    dep = report.dependencies
    risk_rows.append([Paragraph("Deps", styles["Badge"]), Paragraph(f"{dep.root_count} root tasks, {dep.with_children_count} with children, {dep.waiting_on_parents_count} waiting on parents.", styles["Body"])])
    return _card_table(risk_rows, [22 * mm, 144 * mm])


def _appendix(report: BoardReport, styles):
    rows = [[Paragraph("Status", styles["Small"]), Paragraph("Count", styles["Small"])] ]
    rows.extend([[Paragraph(count.status.value.title(), styles["Body"]), Paragraph(str(count.count), styles["Body"])] for count in report.appendix.status_counts])
    return _table(rows, [70 * mm, 30 * mm])


def _empty(message: str, styles):
    return _card_table([[Paragraph("OK", styles["Badge"]), Paragraph(message, styles["Body"])]], [18 * mm, 148 * mm])


def _severity_badge(severity: Severity, styles) -> Table:
    mapping = {Severity.info: (PALETTE["info_soft"], colors.HexColor("#004C6E"), "INFO"), Severity.success: (PALETTE["success_soft"], colors.HexColor("#084B27"), "OK"), Severity.warning: (PALETTE["warning_soft"], colors.HexColor("#6B4100"), "WARN"), Severity.danger: (PALETTE["danger_soft"], colors.HexColor("#93000A"), "RISK")}
    return _badge(*mapping[severity], styles=styles)


def _status_badge(status: KanbanStatus, styles) -> Table:
    bg, fg = STATUS_COLORS[status]
    return _badge(bg, fg, status.value.title(), styles)


def _risk_badge(level: RiskLevel, styles) -> Table:
    bg, fg = RISK_COLORS[level]
    return _badge(bg, fg, level.value.upper(), styles)


def _badge(bg, fg, label: str, styles) -> Table:
    p = Paragraph(f"<font color='{fg.hexval()}'><b>{label}</b></font>", styles["Badge"])
    table = Table([[p]])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), 0.5, bg), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    return table


def _card_table(rows, col_widths):
    table = Table(rows, colWidths=col_widths, repeatRows=0)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALETTE["card"]), ("BOX", (0, 0), (-1, -1), 0.7, PALETTE["outline"]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether(table)


def _table(rows, col_widths):
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PALETTE["surface"]), ("TEXTCOLOR", (0, 0), (-1, 0), PALETTE["muted"]), ("GRID", (0, 0), (-1, -1), 0.35, PALETTE["outline"]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    for row_index in range(1, len(rows), 2):
        table.setStyle(TableStyle([("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#FBFCFE"))]))
    return table


def _footer(report: BoardReport):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(PALETTE["muted"])
        footer = f"Page {doc.page} · {report.report.board_name} · {report.report.generated_at_local}"
        canvas.drawCentredString(A4[0] / 2, 10 * mm, footer)
        canvas.restoreState()
    return draw
