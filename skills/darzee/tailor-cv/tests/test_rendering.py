"""Rendering CLI tests for Task 1 (stdlib unittest only).

Covers public contracts:
  python scripts/validate_rendercv.py INPUT
  python scripts/render_cv.py INPUT --output PDF

Uses real RenderCV 2.8, temporary files, and actual PDF generation.
No test-only production entry points.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_SCRIPT = PACKAGE_ROOT / "scripts" / "validate_rendercv.py"
RENDER_SCRIPT = PACKAGE_ROOT / "scripts" / "render_cv.py"
FIXTURE = PACKAGE_ROOT / "examples" / "source_cv.yaml"

VALID_MINIMAL = """\
cv:
  name: Jane Doe
  sections:
    education:
      - institution: Example University
        area: Computer Science
        degree: BS
        start_date: 2020-09
        end_date: 2024-06
        location: Example City
        highlights:
          - Built forecasting models for customer demand.
"""

# Subprocess timeouts are finite so the suite cannot hang.
CLI_TIMEOUT = 120
RENDER_TIMEOUT = 180


def run_cli(args, **kwargs):
    """Run a CLI with finite timeout and captured output."""
    timeout = kwargs.pop("timeout", CLI_TIMEOUT)
    env = kwargs.pop("env", None)
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        **kwargs,
    )


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_temp_yaml(directory, name, content):
    path = Path(directory) / name
    path.write_text(content, encoding="utf-8")
    return path


class ValidateCliTests(unittest.TestCase):
    def test_valid_fixture_succeeds_without_writes(self):
        self.assertTrue(FIXTURE.exists(), f"fixture missing: {FIXTURE}")
        before = sha256_of(FIXTURE)
        before_listing = sorted(p.name for p in FIXTURE.parent.iterdir())
        result = run_cli(
            [sys.executable, str(VALIDATE_SCRIPT), str(FIXTURE)],
            timeout=CLI_TIMEOUT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"validate should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertEqual(sha256_of(FIXTURE), before, "input bytes changed")
        after_listing = sorted(p.name for p in FIXTURE.parent.iterdir())
        self.assertEqual(before_listing, after_listing, "validator wrote output files")

    def test_valid_minimal_inline_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_temp_yaml(tmp, "valid.yaml", VALID_MINIMAL)
            before = sha256_of(target)
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            self.assertEqual(sha256_of(target), before)

    def test_malformed_yaml_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_temp_yaml(tmp, "bad.yaml", "cv: [unclosed\n  name: : :\n")
            before = sha256_of(target)
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip(), "stderr must be actionable")
            self.assertEqual(sha256_of(target), before)

    def test_invalid_schema_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "cv:\n  name: 12345\n  sections:\n    experience:\n      - bogus_field: oops\n"
            target = write_temp_yaml(tmp, "schema-bad.yaml", content)
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())

    def test_missing_input_fails_actionably(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.yaml"
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(missing)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())

    def test_unsafe_custom_theme_rejected_before_rendercv(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "cv:\n  name: Jane Doe\ndesign:\n  theme: eviltheme\n"
            target = write_temp_yaml(tmp, "evil.yaml", content)
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("theme", result.stderr.lower())
            self.assertIn("built-in", result.stderr.lower())

    def test_unsafe_settings_include_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "cv:\n  name: Jane Doe\n"
                "settings:\n  render_command:\n    design: /tmp/external-design.yaml\n"
            )
            target = write_temp_yaml(tmp, "include.yaml", content)
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stderr + result.stdout).lower()
            self.assertTrue(
                "design" in combined
                and ("not allowed" in combined or "self-contained" in combined),
                f"expected include rejection, got: {result.stderr}",
            )

    def test_unsafe_output_path_override_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "cv:\n  name: Jane Doe\n"
                "settings:\n  render_command:\n    pdf_path: /tmp/evil.pdf\n"
            )
            target = write_temp_yaml(tmp, "out-override.yaml", content)
            result = run_cli(
                [sys.executable, str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())

    def test_dependency_failure_reports_actionably(self):
        # -S disables site packages so `import rendercv` fails.
        # The wrapper must still exit nonzero with actionable stderr.
        with tempfile.TemporaryDirectory() as tmp:
            target = write_temp_yaml(tmp, "valid.yaml", VALID_MINIMAL)
            result = run_cli(
                [sys.executable, "-S", str(VALIDATE_SCRIPT), str(target)],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertIn("rendercv", result.stderr.lower())


class RenderCliTests(unittest.TestCase):
    def test_successful_render_produces_extractable_pdf(self):
        self.assertTrue(FIXTURE.exists(), f"fixture missing: {FIXTURE}")
        before = sha256_of(FIXTURE)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "tailored_cv.pdf"
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(FIXTURE),
                    "--output",
                    str(output),
                ],
                timeout=RENDER_TIMEOUT,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"render should succeed.\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )
            self.assertTrue(output.exists(), "PDF was not published")
            data = output.read_bytes()
            self.assertTrue(len(data) > 1000, f"PDF suspiciously small: {len(data)}")
            self.assertTrue(data.startswith(b"%PDF"), "missing PDF header")
            # Extraction proof with locked pypdf dependency.
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                self.fail(f"pypdf must be installed via uv lock: {exc}")
            reader = PdfReader(str(output))
            self.assertGreaterEqual(len(reader.pages), 1)
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            self.assertTrue(text.strip(), "rendered PDF has no extractable text")
            for expected in (
                "Alex Rivera",
                "Northstar Retail",
                "PostgreSQL",
                "forecasting",
            ):
                self.assertIn(expected, text, f"expected {expected!r} in PDF text")
            self.assertEqual(sha256_of(FIXTURE), before, "input bytes changed")

    def test_render_missing_input_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.yaml"
            output = Path(tmp) / "out.pdf"
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(missing),
                    "--output",
                    str(output),
                ],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertFalse(output.exists(), "no output on failure")

    def test_render_invalid_yaml_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_temp_yaml(tmp, "bad.yaml", "cv: [unclosed\n")
            output = Path(tmp) / "out.pdf"
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(target),
                    "--output",
                    str(output),
                ],
                timeout=RENDER_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertFalse(output.exists(), "must not publish on render failure")

    def test_render_invalid_schema_fails_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = "cv:\n  name: 12345\n"
            target = write_temp_yaml(tmp, "schema-bad.yaml", content)
            output = Path(tmp) / "out.pdf"
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(target),
                    "--output",
                    str(output),
                ],
                timeout=RENDER_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_render_existing_output_rejected_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "exists.pdf"
            output.write_bytes(b"%PDF-1.4 sentinel")
            sentinel = sha256_of(output)
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(FIXTURE),
                    "--output",
                    str(output),
                ],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertEqual(
                sha256_of(output), sentinel, "existing output was overwritten"
            )

    def test_render_source_output_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = write_temp_yaml(tmp, "src.yaml", VALID_MINIMAL)
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(target),
                    "--output",
                    str(target),
                ],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            # Source must remain valid YAML, not replaced by a PDF.
            self.assertIn("cv:", target.read_text(encoding="utf-8"))

    def test_render_unsafe_custom_theme_rejected_without_executing(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A hostile theme folder exists; the wrapper must reject before RenderCV loads it.
            hostile = Path(tmp) / "eviltheme"
            hostile.mkdir()
            (hostile / "__init__.py").write_text(
                "raise SystemExit('hostile code executed')\n", encoding="utf-8"
            )
            (hostile / "theme.j2.typ").write_text("hostile", encoding="utf-8")
            content = "cv:\n  name: Jane Doe\ndesign:\n  theme: eviltheme\n"
            target = write_temp_yaml(tmp, "evil.yaml", content)
            output = Path(tmp) / "out.pdf"
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(target),
                    "--output",
                    str(output),
                ],
                timeout=CLI_TIMEOUT,
                # Run with cwd=tmp so a naive implementation would find ./eviltheme.
            )
            # Re-run with cwd set via subprocess cwd argument.
            # (run_cli above used default cwd; repeat correctly below if needed.)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertIn("theme", result.stderr.lower())

    def test_render_unsafe_settings_include_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = (
                "cv:\n  name: Jane Doe\n"
                "settings:\n  render_command:\n    locale: /tmp/external-locale.yaml\n"
            )
            target = write_temp_yaml(tmp, "include.yaml", content)
            output = Path(tmp) / "out.pdf"
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(target),
                    "--output",
                    str(output),
                ],
                timeout=CLI_TIMEOUT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertTrue(result.stderr.strip())

    def test_render_dependency_failure_when_binary_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.pdf"
            env = dict(os.environ)
            env["PATH"] = tmp  # empty dir: no `rendercv` binary visible
            result = run_cli(
                [
                    sys.executable,
                    str(RENDER_SCRIPT),
                    str(FIXTURE),
                    "--output",
                    str(output),
                ],
                timeout=CLI_TIMEOUT,
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
            self.assertIn("rendercv", result.stderr.lower())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
