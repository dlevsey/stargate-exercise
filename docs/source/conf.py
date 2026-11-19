"""Sphinx settings for the Stargate docs site.

Sphinx reads this file once, at the start of every build. Nothing here contains a
path that only exists on one machine: the repository and the build folder are
worked out in tools/common.py.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "_ext"), str(HERE.parent / "tools")]

from common import BUILD, COMPANION, REPO, sites  # noqa: E402  (tools/common.py)

project = "Stargate"
author = "Stargate study notes"
html_title = "Stargate docs"

extensions = [
    "myst_parser",          # pages are written in Markdown
    "breathe",              # reads the XML that Doxygen writes from the C# files
    "sphinx_csharp",        # shows that XML as C# and makes C# names into links
    "sphinx.ext.graphviz",  # draws the diagrams
    "sphinx_copybutton",    # "copy" button on code samples
    "reference_previews",   # _ext/reference_previews.py: the hover popups
    "stargate_docs",       # _ext/stargate_docs.py: code excerpts from the repository, and checks
]

# ---- Markdown ------------------------------------------------------------------------------------
myst_enable_extensions = ["tasklist"]   # "- [x] done" lists in the documents of the repository
myst_heading_anchors = 3                # every heading down to ### can be linked as page.md#heading
# Which words in front of ":" make a link an address. "companion" is ours: [text](companion:heading)
# leads to a heading of the second site (see "the second site" below).
myst_url_schemes = {"http": None, "https": None, "mailto": None, "ftp": None, "companion": None}

# The README of the exercise goes from a "##" heading straight to "#####". That is its own
# choice of layout, so the build does not treat it as a problem.
suppress_warnings = ["myst.header"]

# ---- C# code reference ---------------------------------------------------------------------------
breathe_projects = {"stargate": str(BUILD / "doxygen" / "xml")}
breathe_default_project = "stargate"
breathe_domain_by_extension = {"cs": "cs"}

# .NET names that are not part of Stargate. A name listed here becomes a link to Microsoft's
# documentation (and gets a hover popup). The C# extension already knows the most common
# System.* names (Guid, Task, List<T>, ...); these are the ones Stargate uses on top of those.
# "-1" after a name means it takes one type argument, such as DbSet<T>.
# The build prints the names it could not link, so this list is easy to keep complete.
sphinx_csharp_external_type_map = {"msdn": {
    "System": ["DateOnly"],
    "System.Data": ["IDbConnection"],
    "System.Linq": ["IQueryable-1"],
    "System.Net": ["HttpStatusCode"],
    "Microsoft.AspNetCore.Mvc": ["ControllerBase", "ActionResult", "ActionResult-1", "IActionResult", "ObjectResult",
                                 "ProblemDetails"],
    "Microsoft.EntityFrameworkCore": ["DbContext", "DbSet-1", "DbContextOptions-1", "ModelBuilder",
                                      "IEntityTypeConfiguration-1"],
    "Microsoft.EntityFrameworkCore.Infrastructure": ["ModelSnapshot"],
    "Microsoft.EntityFrameworkCore.Metadata.Builders": ["EntityTypeBuilder-1"],
    "Microsoft.EntityFrameworkCore.Migrations": ["Migration", "MigrationBuilder"],
    "Microsoft.Extensions.Configuration": ["IConfiguration"],
    "Microsoft.Extensions.DependencyInjection": ["IServiceCollection"],
    "Microsoft.Extensions.Logging": ["ILogger-1"],
}}

# ---- repository files ----------------------------------------------------------------------------
stargate_repo = str(REPO)   # where the `repo-code` directive finds files

# ---- the second site: the dev docs ---------------------------------------------------------
# tools/gen_companion.py cuts the study document (stargate-api-and-patterns.md in the repository)
# into the pages of a second site and writes a map of them. companion/conf.py holds the settings
# of that site, and it is built into the folder companion/ of this one.
stargate_companion_map = str(COMPANION / "map.json")
stargate_companion_url = "companion/"
# Under every type of the code reference, a line names the parts of the dev docs that
# mention the type. False leaves those lines out.
stargate_companion_backlinks = True
# Without the study document there is no second site. A page can keep text for that case out of
# the way with the directive ```{only} companion.
if sites("docs"):
    tags.add("companion")  # noqa: F821  ("tags" is given to this file by Sphinx)

# ---- look ----------------------------------------------------------------------------------------
html_theme = "sphinx_book_theme"
html_theme_options = {
    "show_toc_level": 2,           # the "Contents" list shows two levels; deeper ones open as you read
    "home_page_in_toc": True,
    "use_download_button": False,
}
html_static_path = ["_static"]
templates_path = ["_templates"]
# The left column of every page: the parts the theme puts there, and the switch between the two sites.
html_sidebars = {"**": ["navbar-logo.html", "site-switch.html", "icon-links.html", "search-button-field.html",
                        "sbt-sidebar-nav.html"]}
html_context = {"stargate_sites": sites("docs")}
html_css_files = ["css/stargate.css", "css/notes.css"]
# Marks, in the "Contents" list on the right, the part of the page that is being read.
# The top of the file says why the theme does not do that by itself.
html_js_files = [
    ("js/contents-list.js", {"defer": "defer"}),
    ("js/notes.js", {"defer": "defer"}),          # your own highlights and notes, kept in the browser
]
# No html_context["default_mode"] here, on purpose. The theme follows the reader's system
# (light or dark) without it. On a first visit it does write "Got invalid theme mode" into
# the browser console, which is harmless. Naming the mode ("auto") stops that message, but
# then a reader without JavaScript gets a page without any colours (tried on 2026-11-16).
html_show_sourcelink = False       # no "show source" link: most pages are generated
html_copy_source = False
html_last_updated_fmt = "%Y-%m-%d %H:%M"
graphviz_output_format = "svg"

# ---- hover popups --------------------------------------------------------------------------------
# Popups for .NET names are saved after the build by tools/dotnet_xml_previews.py.
# The page script reads this list when a page opens (path inside the built _static folder).
reference_preview_runtime_manifest = "reference-previews/manifest.json"
# The largest a popup gets, in pixels. On a small window it stays inside the window
# (css/reference-previews.css); what does not fit is reached by scrolling inside the popup.
reference_preview_max_width = 760
reference_preview_max_height = 680
