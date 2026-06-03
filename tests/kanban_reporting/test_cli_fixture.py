import json
import subprocess
from pathlib import Path

from pypdf import PdfReader

FIXTURE = Path(__file__).parents[1] / "fixtures" / "kanban_reporting" / "sample_board.json"


def test_cli_fixture_generates_json_pdf_and_envelope(tmp_path):
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "kanban_reporting.cli",
            "--fixture",
            str(FIXTURE),
            "--out-dir",
            str(tmp_path),
            "--format",
            "json,pdf",
        ],
        cwd=Path(__file__).parents[2],
        check=True,
        text=True,
        capture_output=True,
    )

    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True
    assert envelope["requires_human"] is True
    assert Path(envelope["json_path"]).is_file()
    pdf_path = Path(envelope["pdf_path"])
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 4_000
    assert envelope["media_tag"] == f"MEDIA:{pdf_path}"

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf_path)).pages)
    assert "Kanban status report" in text
    assert "Review generated PDF" in text
    assert "Blocked" in text
