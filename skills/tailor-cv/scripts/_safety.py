"""Pre-RenderCV safety guard: self-contained YAML, built-in themes only."""

from __future__ import annotations

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

FORBIDDEN_INCLUDE_KEYS = ("design", "locale", "locale_catalog", "settings")

FORBIDDEN_OUTPUT_KEYS = (
    "output_folder",
    "typst_path",
    "pdf_path",
    "markdown_path",
    "html_path",
    "png_path",
)


class SafetyError(ValueError):
    """Unsafe or unsafely-parseable YAML."""


class SafetyDependencyError(RuntimeError):
    """Safe YAML parser unavailable."""


def assert_safe_yaml_text(text: str) -> None:
    """Inspect the parsed representation before RenderCV loads it."""
    try:
        from ruamel.yaml import YAML
    except ImportError as exc:
        raise SafetyDependencyError(
            "Safe YAML parser (ruamel.yaml) is required but unavailable for this RenderCV helper. "
            "Re-run this helper with `uv run --no-project <absolute-path-to-script> ...` "
            "so its inline dependencies install automatically."
        ) from exc

    try:
        data = YAML(typ="safe").load(text)
    except Exception as exc:
        detail = str(exc).strip().splitlines()
        first = detail[0].strip() if detail else exc.__class__.__name__
        raise SafetyError(
            f"Input could not be safely parsed as YAML/JSON: {first}"
        ) from exc

    if not isinstance(data, dict):
        raise SafetyError(
            "Input must be a mapping with RenderCV content; "
            "only ordinary self-contained YAML (.yaml/.yml) or JSON (.json) is allowed."
        )

    design = data.get("design")
    if isinstance(design, dict) and "theme" in design:
        theme = design.get("theme")
        if theme is not None and str(theme) not in BUILT_IN_THEMES:
            raise SafetyError(
                f"Rejected custom theme {theme!r}: only built-in themes "
                f"{sorted(BUILT_IN_THEMES)} are allowed."
            )

    settings = data.get("settings")
    if isinstance(settings, dict):
        render_command = settings.get("render_command")
        if isinstance(render_command, dict):
            for key in FORBIDDEN_INCLUDE_KEYS:
                if key in render_command:
                    raise SafetyError(
                        f"Rejected settings.render_command.{key}: external YAML includes "
                        "are not allowed; provide a single self-contained file."
                    )
            for key in FORBIDDEN_OUTPUT_KEYS:
                if key in render_command:
                    raise SafetyError(
                        f"Rejected settings.render_command.{key}: output path overrides "
                        "are not allowed; the wrapper controls output locations."
                    )

    cv = data.get("cv")
    if isinstance(cv, dict) and "photo" in cv:
        photo = cv.get("photo")
        if photo is not None and (not isinstance(photo, str) or photo.strip() != ""):
            raise SafetyError(
                "Rejected cv.photo: external photo assets are not allowed; "
                "omit the photo for a self-contained ATS CV."
            )
