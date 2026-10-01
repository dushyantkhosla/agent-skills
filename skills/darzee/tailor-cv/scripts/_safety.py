"""Shared RenderCV YAML safety guard for tailor-cv helpers.

Both ``validate_rendercv.py`` and ``render_cv.py`` must reject untrusted
configuration *before* RenderCV loads it, because RenderCV extensions can
cause file/network access or custom-code execution:

- ``design.theme`` outside the verified built-in set loads a local theme
  folder (``*.j2.typ`` templates plus ``__init__.py`` Python execution).
- ``settings.render_command.design`` / ``locale`` reference external YAML
  files (file includes resolved relative to the input file).
- ``settings.render_command`` output paths can redirect writes outside the
  isolated temporary directory.
- ``cv.photo`` as a URL can trigger network fetch; absolute or parent-
  traversal photo paths read outside the input directory.

This module keeps YAML self-contained and built-in-theme-only. It performs
no writes and never executes the YAML; it only parses it with a safe loader
for inspection. Schema validation itself remains RenderCV's job.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Verified against RenderCV 2.8 (`available_themes` in
# rendercv.schema.models.design.built_in_design).
BUILT_IN_THEMES = (
    "classic",
    "ember",
    "engineeringclassic",
    "engineeringresumes",
    "harvard",
    "ink",
    "moderncv",
    "opal",
    "sb2nov",
)

# External file includes resolved by RenderCV relative to the input file.
FORBIDDEN_INCLUDE_KEYS = ("design", "locale", "locale_catalog", "settings")

# Output redirections that would escape isolated temporary generation.
FORBIDDEN_OUTPUT_KEYS = (
    "output_folder",
    "typst_path",
    "pdf_path",
    "markdown_path",
    "html_path",
    "png_path",
)


class SafetyError(ValueError):
    """Raised when YAML requests unsafe RenderCV extensions."""


def assert_safe_yaml_text(text: str) -> None:
    """Reject unsafe RenderCV extensions without executing the YAML.

    Raises:
        SafetyError: with an actionable message naming the blocked key.
    """
    lowered = text.lower()
    if "!!python" in lowered:
        raise SafetyError(
            "Rejected unsafe YAML tag '!!python': "
            "only ordinary self-contained RenderCV YAML is allowed."
        )
    if "!include" in lowered:
        raise SafetyError(
            "Rejected '!include' directive: "
            "only self-contained RenderCV YAML without external includes is allowed."
        )

    try:
        from ruamel.yaml import YAML
    except ImportError:
        # Without ruamel there is no safe parse available; fall back to a
        # conservative text scan so safety still applies when RenderCV's own
        # dependency set is unavailable. Detailed structure checks run when
        # ruamel is present (normal `uv sync` environment).
        _fallback_text_scan(text)
        return

    try:
        data = YAML(typ="safe").load(text)
    except Exception:
        # Syntax errors are RenderCV's validation job, not a safety decision.
        return

    if not isinstance(data, dict):
        return

    design = data.get("design")
    if isinstance(design, dict) and "theme" in design:
        theme = design.get("theme")
        if theme is not None and str(theme) not in BUILT_IN_THEMES:
            raise SafetyError(
                f"Rejected custom theme {theme!r}: only built-in themes "
                f"{sorted(BUILT_IN_THEMES)} are allowed because custom themes "
                "execute local template/code."
            )

    settings = data.get("settings")
    if isinstance(settings, dict):
        render_command = settings.get("render_command")
        if isinstance(render_command, dict):
            for key in FORBIDDEN_INCLUDE_KEYS:
                if key in render_command:
                    raise SafetyError(
                        f"Rejected settings.render_command.{key}: external YAML includes "
                        "are not allowed; provide a single self-contained YAML file."
                    )
            for key in FORBIDDEN_OUTPUT_KEYS:
                if key in render_command:
                    raise SafetyError(
                        f"Rejected settings.render_command.{key}: output path overrides "
                        "are not allowed; the wrapper controls isolated output locations."
                    )

    cv = data.get("cv")
    if isinstance(cv, dict):
        photo = cv.get("photo")
        if isinstance(photo, str) and photo.strip():
            value = photo.strip()
            low = value.lower()
            if low.startswith(("http://", "https://")):
                raise SafetyError(
                    "Rejected cv.photo URL: remote photos require network access; "
                    "use a local file next to the YAML or omit the photo."
                )
            # Pure-path check avoids filesystem access.
            posix = PurePosixPath(value)
            if posix.is_absolute() or ".." in posix.parts:
                raise SafetyError(
                    f"Rejected cv.photo {value!r}: only relative paths inside the "
                    "input directory are allowed."
                )


def _fallback_text_scan(text: str) -> None:
    """Minimal regex-free scan used only when ruamel is unavailable."""
    import re

    match = re.search(r"(?m)^\s*theme\s*:\s*(\S+)\s*$", text)
    if match:
        theme = match.group(1).strip("'\"")
        if theme not in BUILT_IN_THEMES:
            raise SafetyError(
                f"Rejected custom theme {theme!r}: only built-in themes "
                f"{sorted(BUILT_IN_THEMES)} are allowed."
            )
    # Block obvious external-include keys without a full parse.
    for key in FORBIDDEN_INCLUDE_KEYS + FORBIDDEN_OUTPUT_KEYS:
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*:", text):
            # Only reject when nested under render_command to avoid false
            # positives on CV content; require both markers present.
            if "render_command" in text:
                raise SafetyError(
                    f"Rejected settings.render_command.{key}: external includes and "
                    "output overrides are not allowed in self-contained YAML."
                )
