#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pypdf==6.19.0",
# ]
# ///

"""Minimal deterministic CV text extraction.

Recipe invocation from any caller directory (project-independent):
    uv run --no-project /absolute/skill/scripts/extract_cv.py INPUT --output TEXT
  --output is optional; without it, extracted text goes to stdout.

Direct Python also works when pypdf is already installed:
    python scripts/extract_cv.py INPUT --output TEXT

- PDF via pypdf (pinned in this script's inline metadata).
- DOCX via stdlib zipfile + XML only. No new dependency.
- Minimal deterministic extraction only: no semantic tailoring, no OCR,
  no macro/field-code execution. Document content is treated as data.
- Preserves page/block separation in a readable form. DOCX headers and
  footers are appended as labeled blocks; body content controls and
  textboxes are read in document order. Office Math (m:t), footnotes,
  endnotes, and altChunk content are refused with a best-effort
  unsupported-layout error instead of silent partial extraction. Comments
  (word/comments.xml) are not body career text and are ignored.
- Fails nonzero (never silent success) on: empty/scanned output, partial
  unreadable pages, encrypted/unreadable PDFs, malformed DOCX, unsupported
  text-bearing layouts (including math/footnote/endnote/altChunk),
  missing/unsupported input, permission errors,
  output/source collisions, and existing destinations.
- Output files are created exclusively: existing files and symlinks are
  refused even if they appear after the pre-checks, and partial output is
  removed on write failure. The source document is never modified.

Reading-order limitation: extracted text follows the file's stored order
(PDF content-stream order via pypdf; DOCX document order), which may differ
from visual order for multi-column or complex layouts. Tables are linearized
in stored order. Resolving reading-order ambiguity is harness
responsibility: the agent must verify extracted text against the source
document before building RenderCV YAML.
"""

from __future__ import annotations

import argparse
import errno
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_RELS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": WORD_NS}
RID_ATTR = f"{{{DOC_RELS_NS}}}id"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract readable text from a CV PDF or DOCX.",
        epilog=(
            "Limitations: reading order follows the file's stored order "
            "(PDF content-stream order via pypdf; DOCX document order) and may "
            "differ from visual order for multi-column or complex layouts; the "
            "harness must verify extraction. Scanned/image-only PDFs require "
            "OCR, which is not supported. DOCX headers/footers are included in "
            "labeled blocks and content-control/textbox wrappers are read in "
            "document order; Office Math (m:t), footnotes/endnotes, and altChunk "
            "content are refused with an unsupported-layout error rather "
            "than silently dropped (best-effort helper: read the source "
            "document directly instead). Comments are not body career text and "
            "are ignored. Macros and field codes are never executed; "
            "document content is treated as data."
        ),
    )
    parser.add_argument("input", help="Input CV file (.pdf or .docx).")
    parser.add_argument(
        "--output",
        default=None,
        help="Destination text file. Created exclusively: an existing file or "
        "symlink is refused, never silently overwritten. Omit to write to stdout.",
    )
    return parser


def fail(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return 1


def missing_pypdf_message() -> str:
    script = Path(__file__).resolve()
    return (
        "missing dependency 'pypdf' for PDF extraction. "
        f"Re-run with `uv run --no-project {script} INPUT --output <absolute-path>.txt` "
        "so its inline dependencies install automatically."
    )


def write_output_file(output_path: Path | str, payload: str) -> int:
    """Create output_path with payload; refuse races, overwrites, symlinks.

    Creation is atomic (O_CREAT|O_EXCL, plus O_NOFOLLOW where available),
    so a file or symlink appearing after the pre-checks still cannot be
    silently overwritten or followed. A partially written file is removed
    on write failure. Only the destination is ever written; callers must
    keep it distinct from the source document.
    """
    path = Path(output_path)
    if path.is_symlink():
        return fail(f"refusing to write through symlink '{path}'. Choose a fresh path.")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o666)
    except FileExistsError:
        return fail(
            f"refusing to overwrite existing destination '{path}'. "
            "Remove it or choose a fresh path."
        )
    except PermissionError as exc:
        return fail(f"permission denied writing output '{path}': {exc}")
    except IsADirectoryError:
        return fail(f"output is a directory: '{path}'.")
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return fail(
                f"refusing to write through symlink '{path}'. Choose a fresh path."
            )
        return fail(f"cannot write output '{path}': {exc}")

    def _cleanup() -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    try:
        stream = os.fdopen(fd, "w", encoding="utf-8", newline="\n")
    except OSError as exc:
        try:
            os.close(fd)
        except OSError:
            pass
        _cleanup()
        return fail(f"cannot write output '{path}': {exc}. Partial output removed.")
    try:
        with stream:
            stream.write(payload)
    except OSError as exc:
        _cleanup()
        return fail(f"cannot write output '{path}': {exc}. Partial output removed.")
    return 0


def extract_pdf_text(path: Path) -> tuple[str | None, int]:
    """Return (text, exit_code). On failure text is None and message is on stderr."""
    try:
        import pypdf
    except ImportError:
        print(f"Error: {missing_pypdf_message()}", file=sys.stderr)
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


def _split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        ns, _, local = tag[1:].partition("}")
        return ns, local
    return "", tag


class _UnsupportedLayout(Exception):
    """A text-bearing wrapper with no reliable reading-order placement."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class _DocxError(Exception):
    """A DOCX failure with its user-facing message already composed."""


def _paragraph_text(p_elem: ET.Element) -> str:
    """Concatenate w:t runs; tabs/newlines for w:tab/w:br. Ignore instrText.

    Only the primary (mc:Choice) representation is read: mc:Fallback
    subtrees duplicate the same content for compatibility and are skipped
    so text is not counted twice.
    """
    chunks: list[str] = []

    def visit(elem: ET.Element) -> None:
        ns, local = _split_tag(elem.tag)
        if ns == MC_NS and local == "Fallback":
            return
        if ns == WORD_NS and local == "t":
            chunks.append(elem.text or "")
        elif ns == WORD_NS and local == "tab":
            chunks.append("\t")
        elif ns == WORD_NS and local in ("br", "cr"):
            chunks.append("\n")
        for child in elem:
            visit(child)

    visit(p_elem)
    return "".join(chunks)


def _paragraph_unsupported_detail(p_elem: ET.Element) -> str | None:
    """Return an unsupported-layout detail if a paragraph needs loud failure."""
    for node in p_elem.iter():
        ns, local = _split_tag(node.tag)
        if ns == WORD_NS and local == "footnoteReference":
            return "w:footnoteReference (footnotes)"
        if ns == WORD_NS and local == "endnoteReference":
            return "w:endnoteReference (endnotes)"
        if ns == MATH_NS and local == "t" and (node.text or "").strip():
            return "m:t (Office Math)"
    # Math without a direct m:t text node (e.g. oMath/oMathPara wrappers)
    # still means visible math content would be lost.
    for node in p_elem.iter():
        ns, local = _split_tag(node.tag)
        if ns == MATH_NS and local in ("oMath", "oMathPara", "oMathBox"):
            return "m:oMath (Office Math)"
    return None


def _contains_math_text(elem: ET.Element) -> bool:
    return any(
        ns == MATH_NS and local == "t" and (node.text or "").strip()
        for node in elem.iter()
        for ns, local in [_split_tag(node.tag)]
    )


def _contains_text(elem: ET.Element) -> bool:
    return any(
        ns == WORD_NS and local == "t" and (node.text or "").strip()
        for node in elem.iter()
        for ns, local in [_split_tag(node.tag)]
    )


def _unsupported_message(path: Path, detail: str, part_label: str) -> str:
    return (
        f"unsupported DOCX layout in '{path}': text inside '<{detail}>' "
        f"in {part_label} cannot be placed in reading order; "
        "this is a best-effort helper that does not implement "
        "Office Math, footnotes/endnotes, or altChunk extraction — "
        "read the source document directly instead."
    )


def _blocks_from_parent(parent: ET.Element) -> list[str]:
    """Extract readable text blocks from a body/hdr/ftr/sdtContent/tc element.

    Paragraphs, tables, and structured-document-tag wrappers are read in
    document order. Section properties, comment references/markers, and other
    text-free markup are ignored (comments live in word/comments.xml and are
    not body career text). Office Math (m:t), footnote/endnote references,
    altChunk, and any other wrapper holding readable text have no reliable
    placement, so they raise _UnsupportedLayout instead of being silently
    dropped.
    """
    blocks: list[str] = []
    for child in parent:
        ns, local = _split_tag(child.tag)
        if ns == WORD_NS and local == "p":
            detail = _paragraph_unsupported_detail(child)
            if detail:
                raise _UnsupportedLayout(detail)
            text = _paragraph_text(child).strip()
            if text:
                blocks.append(text)
        elif ns == MATH_NS:
            if _contains_math_text(child) or _contains_text(child):
                raise _UnsupportedLayout("m:oMath (Office Math)")
            continue
        elif ns == WORD_NS and local == "altChunk":
            raise _UnsupportedLayout("w:altChunk (embedded content)")
        elif ns == WORD_NS and local == "tbl":
            rows: list[str] = []
            for tr in child.findall("w:tr", NS):
                cells = [
                    " ".join(_blocks_from_parent(tc)) for tc in tr.findall("w:tc", NS)
                ]
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append("\n".join(rows))
        elif ns == WORD_NS and local == "sdt":
            content = child.find("w:sdtContent", NS)
            if content is not None:
                blocks.extend(_blocks_from_parent(content))
        elif ns == WORD_NS and local == "sectPr":
            continue
        elif _contains_text(child):
            raise _UnsupportedLayout(local or child.tag)
        # Text-free markup (bookmarks, proof errors, properties) is ignored.
    return blocks


def _resolve_part(base_dir: str, target: str) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return target.lstrip("/")
    return f"{base_dir}/{target}" if base_dir else target


def _read_part_blocks(
    zf: zipfile.ZipFile, path: Path, name: str, kind_label: str
) -> list[str]:
    """Read a referenced header/footer part; raise _DocxError on any problem."""
    try:
        data = zf.read(name)
    except KeyError:
        raise _DocxError(
            f"malformed DOCX '{path}': referenced {kind_label} part "
            f"'{name}' is missing."
        )
    except OSError as exc:
        raise _DocxError(
            f"malformed DOCX '{path}': cannot read {kind_label} part '{name}' ({exc})."
        )
    try:
        part_root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise _DocxError(
            f"malformed DOCX '{path}': invalid XML in {kind_label} part "
            f"'{name}' ({exc})."
        )
    try:
        return _blocks_from_parent(part_root)
    except _UnsupportedLayout as exc:
        raise _DocxError(
            _unsupported_message(path, exc.detail, f"{kind_label} part '{name}'")
        )


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

        try:
            sections: list[str] = []
            try:
                body_blocks = _blocks_from_parent(body)
            except _UnsupportedLayout as exc:
                raise _DocxError(
                    _unsupported_message(path, exc.detail, "document body")
                )
            body_text = "\n\n".join(body_blocks).strip()
            if body_text:
                sections.append(body_text)

            # Footnotes/endnotes live outside word/document.xml body text.
            # If those parts carry readable text, it would be silently lost.
            for note_part, note_label in (
                ("word/footnotes.xml", "footnotes"),
                ("word/endnotes.xml", "endnotes"),
            ):
                if note_part in names:
                    try:
                        note_data = zf.read(note_part)
                    except OSError:
                        continue
                    try:
                        note_root = ET.fromstring(note_data)
                    except ET.ParseError:
                        continue
                    if _contains_text(note_root):
                        raise _DocxError(
                            _unsupported_message(
                                path,
                                f"word/{note_label} ({note_label})",
                                f"'{note_part}'",
                            )
                        )
                    if _contains_math_text(note_root):
                        raise _DocxError(
                            _unsupported_message(
                                path, "m:t (Office Math)", f"'{note_part}'"
                            )
                        )

            refs: list[tuple[str, str]] = []
            for sect in root.iter(f"{{{WORD_NS}}}sectPr"):
                for ref in sect:
                    ref_ns, ref_local = _split_tag(ref.tag)
                    if ref_ns != WORD_NS or ref_local not in (
                        "headerReference",
                        "footerReference",
                    ):
                        continue
                    rid = ref.get(RID_ATTR)
                    if rid:
                        kind = "header" if ref_local == "headerReference" else "footer"
                        refs.append((kind, rid))

            header_targets: list[str] = []
            footer_targets: list[str] = []
            if refs:
                try:
                    rels_data = zf.read("word/_rels/document.xml.rels")
                except KeyError:
                    raise _DocxError(
                        f"malformed DOCX '{path}': sections reference "
                        "headers/footers but 'word/_rels/document.xml.rels' "
                        "is missing."
                    )
                except OSError as exc:
                    raise _DocxError(
                        f"malformed DOCX '{path}': cannot read document "
                        f"relationships ({exc})."
                    )
                try:
                    rels_root = ET.fromstring(rels_data)
                except ET.ParseError as exc:
                    raise _DocxError(
                        f"malformed DOCX '{path}': invalid document "
                        f"relationships XML ({exc})."
                    )
                rel_map: dict[str, tuple[str, str]] = {}
                for rel in rels_root.iter():
                    _, rel_local = _split_tag(rel.tag)
                    if rel_local != "Relationship":
                        continue
                    rid = rel.get("Id")
                    rtype = rel.get("Type")
                    target = rel.get("Target")
                    if not (rid and rtype and target):
                        continue
                    kind = rtype.rsplit("/", 1)[-1]
                    if kind in ("header", "footer"):
                        if rel.get("TargetMode") == "External":
                            raise _DocxError(
                                f"unsupported DOCX layout in '{path}': external "
                                f"{kind} content is not supported; read the "
                                "source document directly instead."
                            )
                        rel_map[rid] = (kind, _resolve_part("word", target))
                seen: set[str] = set()
                for kind, rid in refs:
                    entry = rel_map.get(rid)
                    if entry is None:
                        raise _DocxError(
                            f"malformed DOCX '{path}': {kind} reference "
                            f"'{rid}' cannot be resolved to a document part."
                        )
                    target = entry[1]
                    if target not in seen:
                        seen.add(target)
                        if kind == "header":
                            header_targets.append(target)
                        else:
                            footer_targets.append(target)

            if header_targets:
                header_blocks: list[str] = []
                for target in header_targets:
                    header_blocks.extend(_read_part_blocks(zf, path, target, "header"))
                header_text = "\n\n".join(header_blocks).strip()
                if header_text:
                    sections.append(f"--- Header ---\n{header_text}")
            if footer_targets:
                footer_blocks: list[str] = []
                for target in footer_targets:
                    footer_blocks.extend(_read_part_blocks(zf, path, target, "footer"))
                footer_text = "\n\n".join(footer_blocks).strip()
                if footer_text:
                    sections.append(f"--- Footer ---\n{footer_text}")

            full = "\n\n".join(sections).strip()
            if not full:
                raise _DocxError(
                    f"no extractable text in '{path}': DOCX contains no readable "
                    "paragraphs, tables, headers, or footers."
                )
            return full + "\n", 0
        except _DocxError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return None, 1


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
    except PermissionError as exc:
        return fail(
            f"permission denied creating output directory '{output_path.parent}': {exc}"
        )
    except OSError as exc:
        return fail(f"cannot create output directory '{output_path.parent}': {exc}")
    # Atomic exclusive creation is the real guard: pre-checks above only fail
    # fast, while write_output_file refuses anything that appeared since.
    return write_output_file(output_path, text if text.endswith("\n") else text + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
