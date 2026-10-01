"""Tests for tailor-cv/scripts/extract_cv.py (Task 3).

TDD: written before product code. Uses tiny generated fixtures and the
public CLI only. No mocking of PDF parsing: PDF fixtures are real minimal
PDF bytes read through pypdf when available.

If pypdf is missing (e.g. Task 1 uv env not yet ready), PDF content tests
skip and a dependency-guidance test asserts the CLI fails with an actionable
message instead of silently succeeding.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax import saxutils

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "extract_cv.py"

try:
    import pypdf  # noqa: F401

    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False


def run_cli(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(path: Path, pages: list) -> None:
    """Write a minimal real PDF. Each page is a str or list[str] of lines.

    An empty string / empty list produces a blank (no-text) page to simulate
    a scanned/image-only page.
    """
    n = len(pages)
    objs: dict[int, bytes] = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode("ascii")
    objs[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for i, page in enumerate(pages):
        page_num = 4 + 2 * i
        content_num = 5 + 2 * i
        lines = [page] if isinstance(page, str) else list(page)
        if len(lines) == 0 or (len(lines) == 1 and lines[0] == ""):
            stream = b""
        else:
            parts: list[bytes] = [b"BT /F1 12 Tf 72 720 Td 14 TL "]
            for j, line in enumerate(lines):
                esc = pdf_escape(line).encode("latin-1", errors="replace")
                parts.append(b"(" + esc + b") Tj ")
                if j < len(lines) - 1:
                    parts.append(b"T* ")
            parts.append(b"ET")
            stream = b"".join(parts)
        objs[content_num] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
        objs[page_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_num} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode("ascii")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    max_obj = 3 + 2 * n
    for num in range(1, max_obj + 1):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode("ascii")
        out += objs[num] + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {max_obj + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for num in range(1, max_obj + 1):
        out += f"{offsets[num]:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {max_obj + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    path.write_bytes(bytes(out))


def make_docx(path: Path, blocks: list) -> None:
    """Write a minimal real DOCX. Blocks are ("p", text) or ("table", rows)."""
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body_parts: list[str] = []
    for kind, payload in blocks:
        if kind == "p":
            t = saxutils.escape(payload)
            body_parts.append(
                f'<w:p><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'
            )
        elif kind == "table":
            rows = []
            for row in payload:
                cells = "".join(
                    f'<w:tc><w:p><w:r><w:t xml:space="preserve">'
                    f"{saxutils.escape(c)}</w:t></w:r></w:p></w:tc>"
                    for c in row
                )
                rows.append(f"<w:tr>{cells}</w:tr>")
            body_parts.append(f'<w:tbl>{"".join(rows)}</w:tbl>')
        else:
            raise ValueError(f"unknown block kind: {kind}")
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{ns}"><w:body>'
        f'{"".join(body_parts)}</w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
        'content-types"><Default Extension="rels" ContentType="application/'
        'vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/'
        'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships"><Relationship Id="rId1" Type="http://schemas.'
        'openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestPdfExtraction(unittest.TestCase):
    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_text_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(src, [["John Doe", "Software Engineer", "Built forecasting tool"]])
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            text = out.read_text(encoding="utf-8")
            for expected in ("John Doe", "Software Engineer", "forecasting"):
                self.assertIn(expected, text)

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_linkedin_style_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "linkedin.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(
                src,
                [
                    [
                        "Jane Smith",
                        "LinkedIn Export",
                        "Experience: Data Analyst at ExampleCorp",
                        "Education: BSc Computer Science",
                    ]
                ],
            )
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Jane Smith", text)
            self.assertIn("ExampleCorp", text)

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_page_boundaries_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "multi.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(src, [["Page One Marker"], ["Page Two Marker"]])
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Page One Marker", text)
            self.assertIn("Page Two Marker", text)
            self.assertLess(text.index("Page One Marker"), text.index("Page Two Marker"))
            self.assertIn("Page", text)
            # A page separator mentioning both page numbers must exist.
            self.assertRegex(text, r"(?i)page\s*1.*page\s*2|---\s*Page|Page\s+1\s+of\s+2")

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_empty_fails_with_ocr_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "blank.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(src, [[""]])
            proc = run_cli(str(src), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(no.*text|empty|scanned|OCR)")
            self.assertFalse(out.exists() and out.read_text().strip() != "")

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_partial_unreadable_page_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "partial.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(src, [["Readable content here"], [""]])
            proc = run_cli(str(src), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(page\s*2|unreadable|scanned|no.*text)")

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_encrypted_fails(self) -> None:
        from pypdf import PdfReader, PdfWriter

        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / "plain.pdf"
            enc = Path(tmp) / "enc.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(plain, [["Secret content"]])
            reader = PdfReader(str(plain))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt("test-password")
            with open(enc, "wb") as f:
                writer.write(f)
            proc = run_cli(str(enc), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)encrypt")

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_malformed_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bad.pdf"
            out = Path(tmp) / "out.txt"
            src.write_bytes(b"%PDF-1.4\nthis is not a real pdf body\n%%EOF\n")
            proc = run_cli(str(src), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(malformed|unreadable|no.*text|invalid)")

    @unittest.skipUnless(HAVE_PYPDF, "pypdf not installed; Task 1 env pending")
    def test_pdf_input_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.pdf"
            out = Path(tmp) / "out.txt"
            make_pdf(src, [["Immutable check"]])
            before = sha256(src)
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertEqual(sha256(src), before)


class TestDocxExtraction(unittest.TestCase):
    def test_docx_text_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            out = Path(tmp) / "out.txt"
            make_docx(
                src,
                [
                    ("p", "John Doe"),
                    ("p", "Software Engineer"),
                    ("p", "Built forecasting tool, PostgreSQL contributor"),
                ],
            )
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            text = out.read_text(encoding="utf-8")
            for expected in ("John Doe", "Software Engineer", "PostgreSQL"):
                self.assertIn(expected, text)

    def test_docx_table_content_in_document_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            out = Path(tmp) / "out.txt"
            make_docx(
                src,
                [
                    ("p", "BEFORE-TABLE-MARKER"),
                    ("table", [["Cell A1", "Cell B1"], ["Cell A2", "Cell B2"]]),
                    ("p", "AFTER-TABLE-MARKER"),
                ],
            )
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            text = out.read_text(encoding="utf-8")
            for marker in (
                "BEFORE-TABLE-MARKER",
                "Cell A1",
                "Cell B1",
                "Cell A2",
                "AFTER-TABLE-MARKER",
            ):
                self.assertIn(marker, text)
            self.assertLess(text.index("BEFORE-TABLE-MARKER"), text.index("Cell A1"))
            self.assertLess(text.index("Cell B2"), text.index("AFTER-TABLE-MARKER"))

    def test_docx_empty_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "empty.docx"
            out = Path(tmp) / "out.txt"
            make_docx(src, [])
            proc = run_cli(str(src), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(no.*text|empty)")

    def test_docx_malformed_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bad.docx"
            out = Path(tmp) / "out.txt"
            src.write_bytes(b"not a zip file at all")
            proc = run_cli(str(src), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(malformed|invalid|not.*(zip|docx)|unreadable)")

    def test_docx_with_macro_blob_does_not_execute(self) -> None:
        # A DOCX containing a vbaProject.bin must be treated as inert data:
        # text extraction succeeds without executing anything.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "macro.docx"
            out = Path(tmp) / "out.txt"
            make_docx(src, [("p", "Macro safety check text")])
            with zipfile.ZipFile(src, "a", zipfile.ZIP_DEFLATED) as z:
                z.writestr("word/vbaProject.bin", b"MZ fake macro bytes")
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("Macro safety check text", out.read_text(encoding="utf-8"))

    def test_docx_stdout_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            make_docx(src, [("p", "Stdout marker text")])
            proc = run_cli(str(src))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("Stdout marker text", proc.stdout)

    def test_docx_input_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            out = Path(tmp) / "out.txt"
            make_docx(src, [("p", "Immutable docx check")])
            before = sha256(src)
            proc = run_cli(str(src), "--output", str(out))
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertEqual(sha256(src), before)


class TestCliSafety(unittest.TestCase):
    def test_missing_input_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.pdf"
            proc = run_cli(str(missing), "--output", str(Path(tmp) / "out.txt"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(not found|missing|no such)")

    def test_unsupported_extension_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "notes.txt"
            src.write_text("just text", encoding="utf-8")
            proc = run_cli(str(src), "--output", str(Path(tmp) / "out.txt"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)unsupported")

    def test_output_collision_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            make_docx(src, [("p", "Collision check")])
            before = sha256(src)
            proc = run_cli(str(src), "--output", str(src))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(collision|overwrite|source)")
            self.assertEqual(sha256(src), before)

    def test_existing_destination_not_silently_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            out = Path(tmp) / "out.txt"
            make_docx(src, [("p", "Fresh content")])
            out.write_text("SENTINEL existing content", encoding="utf-8")
            proc = run_cli(str(src), "--output", str(out))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(exists|overwrite|refus)")
            self.assertEqual(out.read_text(encoding="utf-8"), "SENTINEL existing content")

    def test_output_to_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.docx"
            make_docx(src, [("p", "Directory output check")])
            target_dir = Path(tmp) / "subdir"
            target_dir.mkdir()
            proc = run_cli(str(src), "--output", str(target_dir))
            self.assertNotEqual(proc.returncode, 0)

    def test_input_directory_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_cli(str(Path(tmp)), "--output", str(Path(tmp) / "out.txt"))
            self.assertNotEqual(proc.returncode, 0)

    def test_help_documents_limitations(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0)
        combined = proc.stdout + proc.stderr
        self.assertRegex(combined, r"(?i)reading order")
        self.assertRegex(combined, r"(?i)OCR|scanned")

    @unittest.skipIf(HAVE_PYPDF, "pypdf present; dependency path not exercised")
    def test_pdf_without_pypdf_reports_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "cv.pdf"
            src.write_bytes(b"%PDF-1.4 fake\n%%EOF\n")
            proc = run_cli(str(src), "--output", str(Path(tmp) / "out.txt"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertRegex(proc.stderr, r"(?i)(pypdf|dependency|Task 1|uv sync)")


if __name__ == "__main__":
    unittest.main()
