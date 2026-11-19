"""Site-wide reference previews: a hover popup for links to pages, headings and C# names.

This extension owns preview initialization, so it refuses to load next to
sphinx_tippy: two handlers on the same links would show two popups.
"""

import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from sphinx.errors import ConfigError


def external_pages(app):
    """Load the explicit public-page snapshot map without network access at build time."""
    manifest = app.config.reference_preview_external_manifest
    if not manifest:
        return {}
    try:
        path = PurePosixPath(manifest)
        if path.parts[0] != "_static" or ".." in path.parts or path.is_absolute():
            raise ValueError("manifest must be inside _static")
        entries = json.loads((Path(app.srcdir) / path).read_text(encoding="utf-8"))
        pages = {}
        for url, filename in entries.items():
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
                raise ValueError(f"invalid public page URL: {url}")
            if filename is not None and (
                not isinstance(filename, str) or PurePosixPath(filename).name != filename
                or not filename.endswith(".json")
                or not (Path(app.srcdir) / path.parent / filename).is_file()
            ):
                raise ValueError(f"invalid or missing snapshot: {filename}")
            pages[url] = str(path.parent.relative_to("_static") / filename) if filename else None
        return pages
    except (OSError, ValueError, TypeError, AttributeError, IndexError) as error:
        raise ConfigError(f"Invalid reference preview manifest {manifest}: {error}") from error


def runtime_manifest(app):
    """A list of saved pages that is written after the build: a .json path inside _static, or ''."""
    manifest = app.config.reference_preview_runtime_manifest
    path = PurePosixPath(manifest)
    if manifest and (path.is_absolute() or ".." in path.parts or path.suffix != ".json"):
        raise ConfigError(
            f"Invalid reference_preview_runtime_manifest {manifest}: use a .json path inside _static")
    return manifest


def configure_assets(app):
    if app.builder.format != "html" or not app.config.reference_previews_enabled:
        return

    if "sphinx_tippy" in app.extensions:
        raise ConfigError(
            "Use reference_previews as the reference preview handler; "
            "remove sphinx_tippy to avoid duplicate tooltips."
        )

    config = {
        "parentSelector": app.config.tippy_anchor_parent_selector,
        "skipClasses": list(app.config.tippy_skip_anchor_classes),
        "maxWidth": app.config.reference_preview_max_width,
        "maxHeight": app.config.reference_preview_max_height,
        "delay": app.config.reference_preview_delay,
        "pinDelay": app.config.reference_preview_pin_delay,
        "externalPages": external_pages(app),
        "runtimeManifest": runtime_manifest(app),
    }
    # Escaping '<' prevents a configurable selector from ending the script tag.
    payload = json.dumps(config).replace("<", "\\u003c")
    app.add_js_file(
        None, body=f"window.REFERENCE_PREVIEW_CONFIG = {payload};", priority=490
    )
    # Ordered deferred scripts use the same local libraries as the reference theme.
    for priority, asset in enumerate(app.config.tippy_js, start=500):
        app.add_js_file(asset, priority=priority, defer="defer")
    app.add_js_file("js/tippy-preview.js", priority=510, defer="defer")
    app.add_css_file("css/reference-previews.css", priority=600)


def changed_preview_pages(app, env, added, changed, removed):
    """Refresh inline maps even when only saved JSON changed during autobuild."""
    if app.builder.format != "html" or not app.config.reference_previews_enabled:
        return []
    pages = external_pages(app)
    if pages != getattr(env, "reference_preview_external_pages", None):
        env.reference_preview_external_pages = pages
        return sorted(env.found_docs - removed)
    return []


def setup(app):
    app.add_config_value("reference_previews_enabled", True, "html", types=[bool])
    app.add_config_value("tippy_anchor_parent_selector", "article.bd-article", "html", types=[str])
    app.add_config_value(
        "tippy_skip_anchor_classes",
        ("headerlink", "no-preview"),
        "html", types=[list, tuple],
    )
    app.add_config_value(
        "tippy_js",
        ("vendor/tippy/popper.min.js", "vendor/tippy/tippy.min.js"),
        "html", types=[list, tuple],
    )
    app.add_config_value("reference_preview_max_width", 550, "html", types=[int])
    app.add_config_value("reference_preview_max_height", 450, "html", types=[int])
    app.add_config_value("reference_preview_delay", 200, "html", types=[int])
    app.add_config_value("reference_preview_pin_delay", 1000, "html", types=[int])
    app.add_config_value("reference_preview_external_manifest", "", "html", types=[str])
    app.add_config_value("reference_preview_runtime_manifest", "", "html", types=[str])
    app.connect("builder-inited", configure_assets)
    app.connect("env-get-outdated", changed_preview_pages)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
