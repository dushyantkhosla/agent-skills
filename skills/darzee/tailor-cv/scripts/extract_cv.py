#!/usr/bin/env python3
"""Minimal deterministic CV text extraction (Task 3).

CLI: python scripts/extract_cv.py INPUT --output TEXT
  --output is optional; without it, extracted text goes to stdout.

- PDF via pypdf (dependency owned/locked by Task 1).
- DOCX via stdlib zipfile + XML only. No new dependency.
- Minimal deterministic extraction only: no semantic tailoring, no OCR,
  no macro/field-code execution. Document content is treated as data.
- Preserves page/block separation in a readable form.
- Fails nonzero (never silent success) on: empty/scanned output, partial
  unreadable pages, encrypted/unreadable PDFs, malformed DOCX, missing /
  unsupported input, permission errors, output/source collisions, and
  existing destinations.

PDF reading-order limitation: page text follows the PDF content-stream
order returned by pypdf, which may differ from visual order for multi-column
or complex layouts. Tables are linearized in stream order. Resolving reading
order ambiguity is harness responsibility: the agent must verify extracted
text against the source document before building RenderCV YAML.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract readable text from a CV PDF or DOCX.",
        epilog=(
            "Limitations: PDF reading order follows the PDF content-stream order "
            "(pypdf) and may differ from visual order for multi-column or complex "
            "layouts; the harness must verify extraction. Scanned/image-only PDFs "
            "require OCR, which is not supported. DOCX macros and field codes are "
            "never executed; only plain paragraph/table text is read."
        ),
    )
    parser.add_argument("input", help="Input CV file (.pdf or .docx).")
    parser.add_argument(
        "--output",
        default=None,
        help="Destination text file. Refuses to overwrite an existing file or "
        "the source document. Omit to write to stdout.",
    )
    return parser


def fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def extract_pdf_text(path: Path) -> tuple[str | None, int]:
    """Return (text, exit_code). On failure text is None and message is on stderr."""
    try:
        import pypdf
    except ImportError:
        print(
            "Error: missing dependency 'pypdf' for PDF extraction. "
            "Reuse the Task 1 package-local uv environment (run 'uv sync' in "
            "darzee/tailor-cv once Task 1 lands it) and retry with "
            "'uv run python scripts/extract_cv.py ...'.",
            file=sys.stderr,
        )
        return None, 1
    try:
        reader = pypdf.PdfReader(str(path))
    except PermissionError as exc:
        print(f"Error: permission denied reading PDF '{path}': {exc}", file=sys.stderr)
        return None, 1
    except Exception as exc:
        print(f"Error: malformed/unreadable PDF '{path}': {exc}", file=sys.stderr)
        return None, 1

    if getattr(reader, "is_encrypted", False):
        print(
            f"Error: encrypted PDF '{path}': cannot extract text from encrypted "
            "documents. Provide an unencrypted PDF.",
            file=sys.stderr,
        )
        return None, 1

    try:
        n_pages = len(reader.pages)
    except Exception as exc:
        print(f"Error: unreadable PDF '{path}': {exc}", file=sys.stderr)
        return None, 1

    if n_pages == 0:
        print(
            f"Error: no extractable text in '{path}': PDF has no pages.",
            file=sys.stderr,
        )
        return None, 1

    page_texts: list[str] = []
    unreadable: list[int] = []
    for i, page in enumerate(reader.pages):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:
            print(
                f"Error: unreadable PDF page {i + 1} of {n_pages} in '{path}': {exc}",
                file=sys.stderr,
            )
            return None, 1
        if raw.strip() == "":
            unreadable.append(i + 1)
            page_texts.append("")
        else:
            page_texts.append(raw.strip())

    if len(unreadable) == n_pages:
        print(
            f"Error: no extractable text in '{path}': all {n_pages} page(s) yielded "
            "no text. This is often a scanned/image-only PDF, which requires OCR. "
            "OCR is not supported by this helper.",
            file=sys.stderr,
        )
        return None, 1
    if unreadable:
        listed = ", ".join(f"page {p}" for p in unreadable)
        print(
            f"Error: no extractable text on {listed} of {n_pages} in "
            f"'{path}': partial unreadable/scanned pages (page(s) {unreadable}). "
            "Refusing partial extraction. OCR is not supported; provide a "
            "text-based PDF.",
            file=sys.stderr,
        )
        return None, 1

    parts = [
        f"--- Page {i + 1} of {n_pages} ---\n{text}"
        for i, text in enumerate(page_texts)
    ]
    return "\n\n".join(parts) + "\n", 0


def _paragraph_text(p_elem: ET.Element) -> str:
    """Concatenate w:t runs; tabs/newlines for w:tab/w:br. Ignore instrText."""
    chunks: list[str] = []
    for node in p_elem.iter():
        tag = node.tag
        local = tag.split("}", 1)[1] if "}" in tag else tag
        if local == "t":
            chunks.append(node.text or "")
        elif local == "tab":
            chunks.append("\t")
        elif local in ("br", "cr"):
            chunks.append("\n")
    return "".join(chunks)


def extract_docx_text(path: Path) -> tuple[str | None, int]:
    try:
        zf = zipfile.ZipFile(path)
    except PermissionError as exc:
        print(f"Error: permission denied reading DOCX '{path}': {exc}", file=sys.stderr)
        return None, 1
    except zipfile.BadZipFile as exc:
        print(
            f"Error: malformed DOCX '{path}': not a valid ZIP/DOCX file ({exc}).",
            file=sys.stderr,
        )
        return None, 1
    except OSError as exc:
        print(f"Error: cannot read DOCX '{path}': {exc}", file=sys.stderr)
        return None, 1

    with zf:
        try:
            names = zf.namelist()
        except Exception as exc:
            print(
                f"Error: malformed DOCX '{path}': cannot list contents ({exc}).",
                file=sys.stderr,
            )
            return None, 1
        if "word/document.xml" not in names:
            print(
                f"Error: malformed DOCX '{path}': missing word/document.xml.",
                file=sys.stderr,
            )
            return None, 1
        try:
            data = zf.read("word/document.xml")
        except PermissionError as exc:
            print(
                f"Error: permission denied reading DOCX '{path}': {exc}",
                file=sys.stderr,
            )
            return None, 1
        except Exception as exc:
            print(
                f"Error: malformed DOCX '{path}': cannot read document XML ({exc}).",
                file=sys.stderr,
            )
            return None, 1
        # Note: vbaProject.bin / macros, if present, are ignored and never executed.
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            print(
                f"Error: malformed DOCX '{path}': invalid document XML ({exc}).",
                file=sys.stderr,
            )
            return None, 1

        body = root.find("w:body", NS)
        if body is None:
            print(
                f"Error: malformed DOCX '{path}': missing document body.",
                file=sys.stderr,
            )
            return None, 1

        blocks: list[str] = []
        for child in body:
            local = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
            if local == "p":
                text = _paragraph_text(child).strip()
                if text:
                    blocks.append(text)
            elif local == "tbl":
                rows: list[str] = []
                for tr in child.findall("w:tr", NS):
                    cells: list[str] = []
                    for tc in tr.findall("w:tc", NS):
                        paras = [
                            _paragraph_text(p).strip() for p in tc.findall("w:p", NS)
                        ]
                        paras = [p for p in paras if p]
                        cells.append(" ".join(paras))
                    if any(c for c in cells):
                        rows.append(" | ".join(cells))
                if rows:
                    blocks.append("\n".join(rows))
            # Other body children (e.g. sectPr) carry no CV text; ignore.

        full = "\n\n".join(blocks).strip()
        if not full:
            print(
                f"Error: no extractable text in '{path}': DOCX contains no readable "
                "paragraphs or tables.",
                file=sys.stderr,
            )
            return None, 1
        return full + "\n", 0


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 12):
        return fail(f"Python >=3.12 is required (running {sys.version.split()[0]}).")
    args = build_parser().parse_args(argv)
    input_path = Path(args.input)

    if not input_path.exists():
        return fail(f"input not found: '{input_path}'. No such file.")
    if not input_path.is_file():
        return fail(f"input is not a file: '{input_path}'.")

    output_path = Path(args.output) if args.output else None
    if output_path is not None:
        try:
            in_resolved = input_path.resolve()
            out_resolved = output_path.resolve()
        except OSError as exc:
            return fail(f"cannot resolve output path '{output_path}': {exc}")
        if out_resolved == in_resolved:
            return fail(
                f"output/source collision: output '{output_path}' is the same file "
                "as the source document. Refusing to overwrite the source."
            )
        if output_path.exists() or output_path.is_symlink():
            return fail(
                f"refusing to overwrite existing destination '{output_path}'. "
                "Remove it or choose a fresh path."
            )

    ext = input_path.suffix.lower()
    if ext == ".pdf":
        text, code = extract_pdf_text(input_path)
        if code != 0 or text is None:
            return 1
    elif ext == ".docx":
        text, code = extract_docx_text(input_path)
        if code != 0 or text is None:
            return 1
    else:
        return fail(
            f"unsupported file type '{input_path.suffix}' for '{input_path}'. "
            "Supported inputs: .pdf, .docx."
        )

    if text is None or text.strip() == "":
        return fail(f"no extractable text in '{input_path}'. Refusing empty output.")

    if output_path is None:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return 0

    try:
        parent = output_path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() or output_path.is_symlink():
            return fail(
                f"refusing to overwrite existing destination '{output_path}'. "
                "Remove it or choose a fresh path."
            )
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text if text.endswith("\n") else text + "\n")
    except PermissionError as exc:
        return fail(f"permission denied writing output '{output_path}': {exc}")
    except IsADirectoryError:
        return fail(f"output is a directory: '{output_path}'.")
    except OSError as exc:
        return fail(f"cannot write output '{output_path}': {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
