"""Sphinx settings for the second site: the dev docs.

The first site (source/conf.py) is the code reference. This one shows one long Markdown
document, the study document, cut into pages. tools/gen_companion.py does the cutting and
puts the pages in <build folder>/companion/pages, so this folder holds settings only.
tools/build_companion.py runs Sphinx with them.

Both sites share the look, the hover popups and the scripts: everything under source/_static,
source/_templates and source/_ext.
"""
import json
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(DOCS / "source" / "_ext"), str(DOCS / "tools")]

from common import BUILD, COMPANION, REPO, sites  # noqa: E402  (tools/common.py)

# What tools/gen_companion.py worked out: the title, the pages, where every heading went.
MAP = json.loads((COMPANION / "map.json").read_text(encoding="utf-8"))

project = MAP["title"]          # the "#" title of the study document
author = "Stargate study notes"
html_title = MAP["title"]

extensions = [
    "myst_parser",            # pages are written in Markdown
    "sphinx_copybutton",      # "copy" button on code samples
    "reference_previews",     # source/_ext/reference_previews.py: the hover popups
    "stargate_companion",    # source/_ext/stargate_companion.py: headings, links and file pages
]

# ---- Markdown ------------------------------------------------------------------------------------
# The study document is plain Markdown that also has to read well on GitHub, so nothing extra is
# switched on. Every link is handed to stargate_companion as it is written.
myst_enable_extensions = []
myst_all_links_external = True
# Two messages are switched off because the document is not written for Sphinx:
#   myst.header                a heading that skips a level (## followed by ####)
#   misc.highlighting_failure  an excerpt that is not complete code, so it cannot be coloured strictly
suppress_warnings = ["myst.header", "misc.highlighting_failure"]

# ---- where things are ----------------------------------------------------------------------------
stargate_repo = str(REPO)
stargate_companion_map = str(COMPANION / "map.json")
stargate_code_reference = str(BUILD / "html")   # the built first site: its list of names is read
stargate_code_reference_url = "../"             # this site is served from the folder companion/ of the first one

# ---- look: the same as the first site --------------------------------------------------------------
html_theme = "sphinx_book_theme"
html_theme_options = {
    "show_toc_level": 2,
    "home_page_in_toc": True,
    "use_download_button": False,
}
html_static_path = [str(DOCS / "source" / "_static")]
templates_path = [str(DOCS / "source" / "_templates")]
# The left column of every page: the parts the theme puts there, and the switch between the two sites.
html_sidebars = {"**": ["navbar-logo.html", "site-switch.html", "icon-links.html", "search-button-field.html",
                        "sbt-sidebar-nav.html"]}
html_context = {"stargate_sites": sites("companion")}
html_css_files = ["css/stargate.css", "css/notes.css"]
html_js_files = [
    ("js/contents-list.js", {"defer": "defer"}),
    ("js/notes.js", {"defer": "defer"}),          # your own highlights and notes, kept in the browser
    ("js/source-lines.js", {"defer": "defer"}),   # marks the lines a link such as Program.cs#L6-L21 names
]
html_show_sourcelink = False
html_copy_source = False
html_last_updated_fmt = "%Y-%m-%d %H:%M"

# ---- hover popups --------------------------------------------------------------------------------
reference_preview_runtime_manifest = "reference-previews/manifest.json"
# The largest a popup gets, in pixels. On a small window it stays inside the window
# (css/reference-previews.css); what does not fit is reached by scrolling inside the popup.
reference_preview_max_width = 760
reference_preview_max_height = 680
