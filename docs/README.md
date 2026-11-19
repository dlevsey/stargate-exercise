# Stargate docs site

This folder builds a documentation website for the repository it sits in, Stargate (the ACTS
exercise):

- a **code reference** made from the C# files (every class, record, interface, enum and member),
- **diagrams**: the data model, and the projects with their NuGet packages,
- the **HTTP endpoints**, made from the description the API publishes,
- the repository's own Markdown documents (its `README.md` and `CHANGES.md`),
- two **guides** written by hand,
- **hover popups** on every link, including links to .NET names,
- and, once a study document exists, a **second site** made from it (see
  [The second site](#the-second-site-the-dev-docs)).

The scripts only **read** the repository. They never change a file in it, and they do not build
or run the application.

Everything here runs in WSL (Linux). The page [Using this site](source/guide/using-this-site.md)
is the short version for readers and for people who add pages. This file is for whoever keeps the
site working.

## First time

```bash
./setup.sh      # once: installs the tools (see below)
./build.sh      # builds the site, in a few seconds
./serve.sh      # shows it at http://localhost:8770   (Ctrl+C stops)
```

`./setup.sh` needs Python 3.12 or newer with its `venv` module, Graphviz (the `dot` program, which
draws the diagrams), `curl`, `tar` and `sha256sum`. It checks for each of them and, when one is
missing, prints the `apt` command that installs it. It never runs `sudo` itself.

What it installs, all in one folder, `~/.local/share/stargate-docs` (about 300 MB):

- a private Python environment (a *virtual environment*: a folder with its own copy of the Python
  packages, so they cannot clash with anything else on the machine), holding exactly the package
  versions listed in `requirements.txt`;
- Doxygen 1.18.0, the program that reads the C# files. It is downloaded from Doxygen's release page
  on GitHub (about 115 MB) and compared with a known SHA-256 fingerprint before it is used. The
  Doxygen that `apt` offers is older; the rewrite rules and the checks here are written for 1.18.0.

Nothing is added to `PATH`, no service is started, and nothing is installed system-wide.

The script can be run again at any time; it keeps what is already there. When a download stalls,
it tries again by itself. If it stops all the same, its last lines say why and what to do.

**Where the repository is.** The scripts look for a file named `local.env` in this folder and read
the line `STARGATE_REPO=...` from it. Without that line they take the folder above this one, which
fits when this folder sits directly inside the repository, as it does now (the folder `docs`).
To set it:

```bash
cp local.env.example local.env
# then edit the STARGATE_REPO line in local.env
```

Any folder with C# projects in it works: the tools look for `.csproj` files and take what they find.

**Where the popup texts for .NET names come from.** Popups for .NET names such as `DbContext` or
`ControllerBase` take their text from documentation files (XML) that are already on the machine:

- the *reference packs* of .NET, for the framework the projects are built for (`net8.0` for
  Stargate). They are looked for in the .NET installation inside WSL and in the one on Windows
  (`/mnt/c/Program Files/dotnet`), so the SDK that Visual Studio uses is enough;
- the NuGet packages the projects use, in the NuGet folder of WSL (`~/.nuget/packages`) and in the
  folders a restore has written down in `obj/project.assets.json`.

Without them the build still works and prints a line that starts with
`note: documentation XML not found for`; those names then open as ordinary links.

## While you work on the code

```bash
./watch.sh      # builds, serves at http://localhost:8770, and builds again after every save
```

Save a C# file, a repository document or a page of this site, and a few seconds later the page in
the browser reloads by itself. Open the site as `http://localhost:8770`, the address the
script prints: the reload only works under that name.

Where `./build.sh` stops at the first problem, `./watch.sh` prints it as a warning and keeps showing
the last pages that could be built. So run `./build.sh` before you rely on the result.

Things `./watch.sh` does not notice by itself:

- **A new folder directly inside a C# project** (for example a new `api/Services/`),
  **a new project**, and **a new Markdown document** in a folder that had none.
  The list of watched folders is made when the script starts. Stop it and start it again.
  New files and folders *inside* a folder that is already watched are noticed.
- **A change in the running API.** The HTTP endpoints page is refreshed during a build, and a build
  starts when a file is saved. After changing a controller: restart the API, then save any watched
  file, or run `./build.sh`.
- **A change to the tools in `tools/`.** Stop the script and start it again.

The script finds saved files by looking at the time stamp of every watched file once a second.
WSL is not told when a program on Windows saves a file, so waiting for a signal would miss those
saves. Looking at time stamps does not depend on who saved the file, which is why a save from
Visual Studio is expected to be picked up too.

## What is in this folder

| Path | What it is |
|---|---|
| `setup.sh` `build.sh` `serve.sh` `watch.sh` `test.sh` | The five commands. Each begins with a comment that says what it does. |
| `requirements.txt` | The exact Python package versions. |
| `Doxyfile` | Doxygen's settings. |
| `local.env.example` | Settings for one machine. Copy it to `local.env` to use them. |
| `source/index.md`, `source/guide/` | The pages written by hand. |
| `source/conf.py` | Sphinx's settings, including the list of .NET names that become links. |
| `source/_ext/stargate_docs.py` | Additions to Sphinx: `repo-code` (code samples read from the repository), the check for C# names that no longer exist, links after "Subclassed by", the "record" label, the short names in the "Contents" list. |
| `source/_ext/stargate_companion.py`, `companion/conf.py`, `source/_templates/site-switch.html`, `source/_static/js/source-lines.js` | The second site (see [The second site](#the-second-site-the-dev-docs)). |
| `source/_ext/reference_previews.py`, `source/_static/js/tippy-preview.js`, `source/_static/css/reference-previews.css`, `source/_static/vendor/tippy/` | The hover popups (see [The hover popups](#the-hover-popups)). |
| `source/_static/js/contents-list.js` | Marks the part of the page that is being read in the "Contents" list on the right, shows the members of that type there, and says where a long name may go on to a second line. Its first lines say why the theme does not do this by itself. |
| `source/_static/css/stargate.css` | Small changes to the look of the theme. |
| `tools/prebuild.py` | Everything that happens before Sphinx runs. |
| `tools/cs_doxygen_filter.py` | Rewrites modern C# into a form Doxygen understands. Its first lines list every rule. |
| `tools/gen_pages.py` `tools/gen_diagrams.py` `tools/gen_endpoints.py` | Write the generated pages. |
| `tools/gen_companion.py` `tools/build_companion.py` `tools/code_names.py` | Cut the study document into pages, build the second site, and decide which C# name a word in code font means. |
| `tools/dotnet_xml_previews.py` | Saves the popup texts for .NET names. |
| `tools/watch_paths.py`, `tools/autobuild.py` | The list of folders `watch.sh` watches, and the program that builds again after a save. |
| `tools/common.py`, `tools/env.sh` | Where the folders are (the same defaults, once for Python and once for the shell scripts), and how the C# projects of a repository are found. |
| `tools/test_*.py` | The checks that `./test.sh` runs. |
| `data/openapi.json`, `data/openapi.saved-on.txt` | The saved copy of the API's description, and the date it was saved. |

Made by a build and ignored by Git: `_build/`, `source/api/`, `source/diagrams/`, `source/http/`,
`source/project/`. Also ignored: `local.env`.

## How a build works

```text
C# files ── a rewritten copy ──> Doxygen ──> XML ───────────────────────────┐
.csproj files, the EF Core model snapshot ──> gen_diagrams.py ──> pages ────┤
running API, or data/openapi.json ──> gen_endpoints.py ──> page ────────────┼──> Sphinx ──> _build/html
the repository's .md files ── copied ──> source/project/ ───────────────────┤
source/index.md, source/guide/*.md  (written by hand) ──────────────────────┘
                                             afterwards: popup texts for .NET names
```

1. **`tools/prebuild.py`** looks for the C# projects of the repository: every folder with a
   `.csproj` file, wherever it is. Build output (`bin/`, `obj/`), `node_modules/` and folders whose
   name starts with a dot are skipped, and test projects are left out unless `STARGATE_DOCS_TESTS=1`
   is set. It copies every `.cs` file of those projects into a temporary folder. On the way each
   copy is rewritten by `tools/cs_doxygen_filter.py`, because Doxygen 1.18 does not understand some
   newer C# (records with a body, primary constructors, types without a body). The real files are
   only read, and no line is added or removed, so line numbers stay the real ones.
2. **Doxygen** reads the copies and writes XML files that describe every type and member.
   For C# it names a base type without its type arguments: `IRequestHandler` where the code says
   `IRequestHandler<CreatePerson, CreatePersonResult>`. `prebuild.py` reads the arguments from the
   declaration and adds them to the XML, so the page of a handler says which request it answers.
3. `prebuild.py` then **compares** the types declared in the C# files with the types in the XML.
   A type that Doxygen lost stops `./build.sh`. It also writes the generated pages (one page per
   namespace, the two diagram pages, the HTTP endpoints) and copies the repository's documents.
   The data model is read from the *model snapshot*, the file `...ModelSnapshot.cs` that Entity
   Framework Core writes next to the migrations; without migrations the page says so.
4. **Sphinx** turns all pages into HTML. Two extensions do the C# part: *Breathe* reads Doxygen's
   XML, and *sphinx-csharp* shows it as C# and makes every C# name a link. `./build.sh` runs Sphinx
   with `-W`, which makes every warning an error.
5. **`tools/dotnet_xml_previews.py`** looks which .NET names the finished pages link to and saves
   a small popup text for each.

## Settings

Put them in `local.env` (one `NAME=value` per line), or in front of a command for one run:
`STARGATE_REPO=/path/to/stargate-exercise ./build.sh`. A value given in front of a command wins over
the same name in `local.env`.

| Name | Meaning | Default |
|---|---|---|
| `STARGATE_REPO` | the Stargate repository | the folder above this one |
| `STARGATE_DOCS_BUILD` | where a build puts its results | `_build` in this folder |
| `STARGATE_DOCS_TOOLS` | where `./setup.sh` puts the tools | `~/.local/share/stargate-docs` |
| `DOXYGEN` | your own Doxygen program | the one `./setup.sh` downloaded |
| `STARGATE_OPENAPI_URL` | where the running API publishes its description | `http://localhost:5204/swagger/v1/swagger.json` |
| `STARGATE_DOCS_TESTS` | `1` puts test projects into the code reference | left out |
| `STARGATE_COMPANION_DOC` | the study document the second site is made from | `stargate-api-and-patterns.md` in the top folder of the repository |
| `PYTHON` | the Python that `./setup.sh` builds the environment from | `python3` |
| `WATCHFILES_POLL_DELAY_MS` | how often `./watch.sh` looks for saved files, in milliseconds | `1000` |
| `DOTNET_ROOT`, `NUGET_PACKAGES` | .NET's own names for where .NET and the NuGet packages are; the popup texts for .NET names are looked for there first | not set |

## When a build fails

A build that worked ends with `Built without problems:` and the folder. Anything else means it
stopped. The reason is in the last lines, or in the lines marked `WARNING` or `ERROR` above them.
Such a line starts with the page and the line number.

| Message | What it means | What to do |
|---|---|---|
| `C# name not found in the code: CreatePersonHandler.Handel` | A guide page names a class or member that does not exist: renamed, removed or mistyped. | Correct the name on the page that the line names. |
| `repo-code: there is no file '...' in the repository` | A code sample names a file that is gone or was moved. | Correct the path. It starts at the repository's top folder. |
| `start-at pattern not found: ...`, `end-at pattern not found: ...`, `end-before pattern not found: ...` | The text that marks where a code sample starts or stops is no longer in the file. | Open the file and choose marker text that is there. |
| `repo-code: :block: needs :start-at: ...` | `:block:` was used without `:start-at:`, or together with an end marker. | Give it a `:start-at:` line and remove the end marker. |
| `repo-code: no closing brace found for the block that starts at ...` | The `{` after the start line is never closed. | Usually the start text matches an earlier line than intended. Make it more specific. |
| `'myst' cross-reference target not found: 'page.md'` | A link to another page of this site leads nowhere. | Correct the link, or create the page. |
| `local id not found in doc '...': 'heading'` | A link to a heading (`page.md#heading`) leads nowhere: the heading was renamed. | Correct the part after `#`. It is the heading in lower case with `-` for spaces. |
| `document isn't included in any toctree` | A page exists but is in no menu. | Add it to a list in `source/index.md`. |
| `MISSING from the code reference ...` then `Stopped because types are missing (strict mode).` | Doxygen did not understand a type declaration. | See [When a type is missing](#when-a-type-is-missing). |
| `Cannot find C# code to document: there is no project (.csproj file) under ...` | The repository is not where the scripts look. | Set `STARGATE_REPO` in `local.env`. |
| `The tools are not installed yet` | `./setup.sh` has not run, or the tools folder was removed. | Run `./setup.sh`. |
| `Doxygen not found at ...` | The same, for Doxygen alone, or `DOXYGEN` names a file that is not there. | Run `./setup.sh`, or correct `DOXYGEN`. |
| `Doxygen failed (exit code N).` | Doxygen itself stopped. Its own message is printed just above, under `Doxygen said:`. | Read that message. |
| `No saved OpenAPI description (...) and the API did not answer` | `data/openapi.json` is missing and the API is not running. | Start the API and build again, or restore the file with Git. |
| `bash: ./build.sh: Permission denied` | The script has lost its mark "may be run". Git does not record that mark for files added on a Windows drive, so a fresh copy fetched with Git can lack it. | For this copy: `chmod +x *.sh`. For everyone who fetches it later: `git add --chmod=+x *.sh`, then commit. |
| `Port 8770 is already in use.` | Another `./watch.sh` or `./serve.sh` is still running. | Stop it with Ctrl+C in its terminal, or give another port: `./serve.sh 8780`. |
| `UnknownStateError: text` (a long Python error from Sphinx) | The spelling of a link in a `///` comment was changed in `tools/cs_doxygen_filter.py`, and Breathe cannot read it. | Run `./test.sh`. The comment in `rewrite_see()` explains what the spelling must look like. |

The last line of a failed Sphinx run is
`build finished with problems, N warnings (with warnings treated as errors).`

Two kinds of lines look like problems and are not:

- **`Doxygen said:`** followed by lines such as
  `api/Business/Commands/CreatePerson.cs:24: warning: argument 'nope' of command @param is not found in the argument list of ...`
  Doxygen found something odd in a `///` comment, here a `<param>` for a parameter that does not
  exist. The build goes on. The path is the real file, and the line number points at that comment.
- **`Names in the code reference without a link (4). ...`** These are names in signatures that are
  neither declared in the repository nor known .NET names, so they are shown without a link. To
  link a .NET name, add it to `sphinx_csharp_external_type_map` in `source/conf.py`. For Stargate
  the four names are MediatR's (`IMediator`, `IRequest`, `IRequestHandler`, `IRequestPreProcessor`).
  MediatR is not part of .NET and has no page on Microsoft Learn, so there is nothing to link to.

## When a type is missing

The build counts the type declarations in the C# files (`class`, `record`, `struct`, `interface`,
`enum`) and compares them with what Doxygen wrote. A line such as
`31 of 31 declared types are in the XML` means nothing was lost. (The parts of a `partial` type,
such as a migration and its `.Designer.cs` file, count as one type.) When a name is listed as `MISSING`:

1. Find its declaration in the C# file. Something about its form is new to the rewrite rules.
2. Look at what Doxygen is given: `python3 tools/cs_doxygen_filter.py path/to/File.cs`
3. Add or adjust a rule in `tools/cs_doxygen_filter.py` so that the declaration comes out in an
   older form that means the same, and add a check for it to `tools/test_cs_doxygen_filter.py`.
4. Run `./test.sh`, then `./build.sh`.

If the listed word is not a type at all, for instance `of` from a line in a `/* ... */` comment that
starts with "class of ...", add it to `NOT_A_TYPE` in `tools/prebuild.py`.

## Descriptions from `///` comments

The code reference shows the text of `///` comments under each signature and in its popup.
[Using this site](source/guide/using-this-site.md) lists the tags that are understood and their
limits. Two things matter for whoever maintains the tools:

- Doxygen writes `<see cref="X"/>` as plain text, so `cs_doxygen_filter.py` rewrites it into a
  link. The spelling of that link is exact on purpose: Doxygen and Breathe each read it with strict
  rules of their own, and a spelling Doxygen misreads makes it treat the rest of the file as a
  comment, so the types in that file vanish without a message. `rewrite_see()` explains the rules.
- `tools/test_comment_links.py` guards this. It runs Doxygen itself on small C# files with links in
  every awkward place and checks that no type, member or link is lost.

## The HTTP endpoints page

The page is written from the API's OpenAPI description, a JSON document that lists every endpoint
with its parameters and answers. The API publishes it at
`http://localhost:5204/swagger/v1/swagger.json` while it runs in the *Development* environment
(`Program.cs` switches Swagger on only there; starting the API from Visual Studio or with
`dotnet run` uses that environment).

- **API running during a build:** the build fetches the description. If it differs from
  `data/openapi.json`, the file is replaced and today's date is written to
  `data/openapi.saved-on.txt`.
- **API not running:** the build uses the saved copy and says so. The page shows the date.

- **API running on Windows, build running in WSL:** with WSL's default network setting, a program
  in WSL cannot reach `localhost` on Windows. When the direct request fails, the build therefore
  asks Windows' own `curl.exe` to fetch the description. Nothing has to be set for that.

`data/openapi.json` is meant to be kept under version control. A change to it in `git diff` shows
exactly how the API changed, and anyone can build the site without starting the API first.

The page says only what the description says. Stargate's actions return `IActionResult`, so the
description names no data shape for any answer, and the page has a note about that.

## Speed on a Windows drive

WSL reads files on a Windows drive (`/mnt/c/...`) much more slowly than files in its own file
system. Three things keep builds short anyway:

- the tools live in the WSL home folder, not in this folder;
- Doxygen works on a temporary copy of the C# files on the Linux side;
- folders that never matter (`bin/`, `obj/`, `node_modules/`) are not read at all.

If this folder itself sits on a Windows drive, the build results can be moved to the Linux side
as well. Put this line in `local.env`:

```bash
STARGATE_DOCS_BUILD=~/.cache/stargate-docs
```

## Updating the tools

The versions are fixed on purpose, so that a build next year behaves like a build today.

**Python packages**

1. In `requirements.txt`, change the versions in the first block (`what the site uses directly`)
   and delete every line of the second block.
2. Remove the old environment and install again:
   `rm -rf ~/.local/share/stargate-docs/venv && ./setup.sh`
3. Run `./test.sh` and `./build.sh`, and look at a few pages and popups. Scroll a page of the
   code reference too: the "Contents" list on the right should mark the type being read and show
   its members. `source/_static/js/contents-list.js` does that, and it depends on three names
   that the theme gives to parts of the page: `pst-page-toc-nav` (the list), `bd-header-article`
   (the bar at the top) and `bd-sidebar-secondary` (the box the list scrolls in).
4. Fix the versions again: run `~/.local/share/stargate-docs/venv/bin/python -m pip freeze` and
   copy the lines for packages that are not in the first block into the second block.

**Doxygen**

1. In `setup.sh`, change `DOXYGEN_VERSION`, `DOXYGEN_URL` and `DOXYGEN_SHA256`. GitHub shows a
   `sha256:` value next to every file on a release page.
2. In `tools/prebuild.py`, change `TESTED_DOXYGEN` to the same version.
3. Run `./setup.sh`, then `./test.sh`, then `./build.sh`. `./test.sh` matters most here, because
   the link spelling described above depends on how this version of Doxygen reads comments. One
   check in `tools/test_prebuild.py` fails when a newer Doxygen keeps the type arguments of base
   types by itself; the step that adds them (`restore_type_arguments`) can go then.

**The two popup libraries:** `source/_static/vendor/tippy/PROVENANCE.txt` says where they come from
and how to replace them.

## The checks

```bash
./test.sh       # about ten seconds
./test.sh -v    # the same, and every check is named
```

Every file `tools/test_*.py` is run. Each one starts with a line that says what it checks: the
rewrite rules, the links in `///` comments and the type arguments of base types (these two run
Doxygen on sample files of their own and are skipped when Doxygen is not installed), how projects
are found, the data model and endpoints pages,
the popup texts, the second site, the watcher and the settings. None of them needs the repository:
they make small sample repositories in a temporary folder.

## The second site: the dev docs

A long study document can become a second site, served under `/companion/` of the first, with the
same popups and with links in both directions. It is made when the file
`stargate-api-and-patterns.md` exists in the top folder of the repository (or wherever
`STARGATE_COMPANION_DOC` points). Without that file there is one site, and nothing else changes.

- `tools/gen_companion.py` cuts the document into one page per `##` heading and notes which
  sections name which C# type. Its first lines explain the rules.
- `tools/build_companion.py` builds those pages with the settings in `companion/conf.py`.
- A C# name in code font in the document becomes a link to its entry in the code reference, and
  each type in the code reference lists the sections that mention it.
- Pages of the first site link to a section with `[text](companion:the-heading)`.
  [Using this site](source/guide/using-this-site.md) has the details for writers.

## The hover popups

Rest the pointer on a link and a small window shows what the link points at.

- **How it works.** When the pointer rests on a link, the page script
  (`source/_static/js/tippy-preview.js`) fetches the linked page of this same site in the
  background, takes the part the link points at, and shows it in a popup made with two small
  libraries, Tippy and Popper. Browsers only allow such background fetches for pages that come from
  a web server, which is why the site is looked at through `./serve.sh` or `./watch.sh` and not by
  opening the HTML files from the folder.
- **C# entries.** For a link to a class or member, the popup shows the signature together with the
  description and the member list that follow it.
- **Pinned and nested popups.** A popup that stays open for a second becomes *pinned*, and links
  inside it open further popups. `reference_preview_pin_delay` in `source/conf.py` sets the delay
  in milliseconds (default 1000).
- **.NET names.** A link to Microsoft's documentation leads to another website, which a popup may
  not fetch. `tools/dotnet_xml_previews.py` therefore saves a short text for each linked .NET name
  after the build, from the documentation files on this machine, and writes a list of them
  (`_static/reference-previews/manifest.json` in the built site). The page script reads that list
  when a page opens. Nothing is fetched from Microsoft, neither during a build nor while reading.

## Removing everything

```bash
rm -rf ~/.local/share/stargate-docs    # the tools
rm -rf ~/.cache/stargate-docs          # only if STARGATE_DOCS_BUILD was set to it
```

Then delete this folder. `pip`, which installs the Python packages, also keeps the files it
downloaded in its own cache, `~/.cache/pip`. That folder can be deleted too.

## Known gaps

- **What the code reference covers.** Every C# project found in the repository except test
  projects (`STARGATE_DOCS_TESTS=1` puts them in). Today that is the one project
  `api`. Code in other languages is not covered.
- **`Program.cs`.** It consists of *top-level statements* (code written directly in the file,
  without a class around it), so it declares no type and has no entry in the code reference. The
  guide "Start here" shows its lines instead.
- **MediatR names** (`IMediator`, `IRequest`, `IRequestHandler`, `IRequestPreProcessor`) are shown
  without a link and without a popup: there is no Microsoft Learn page to link to.
- **Base types of a type written in several parts.** For a `partial` type, a base type is shown
  with its type arguments only when the part that Doxygen names as the place of the type is the
  part that lists the base type. Otherwise it is shown without them.
- **Names inside method bodies.** The reference shows declarations: signatures, base types and
  comments. A call made inside a method does not appear anywhere.
- **Parameters of a record.** A record such as `record OrderQuery(Guid CustomerId, ...)` is shown
  with its parameters, but a single parameter is not a link target: `` {cs:prop}`OrderQuery.CustomerId` ``
  stops the build with "C# name not found in the code", and `<see cref="OrderQuery.CustomerId"/>`
  in a `///` comment is shown as a name without a link. Link to the record instead. (Stargate has
  no records today.)
- **Sentences in the guides.** The build checks every name and every code sample on a guide page.
  It cannot check what the sentences claim. Each guide starts with the date it was last compared
  with the code.
- **The HTTP endpoints page** is as fresh as the last build that ran while the API was up.
  The copy that came with this folder was saved on 2026-11-17 from a scratch copy of the API.
- **One message in the browser console.** The first time a browser opens the site, the theme
  writes `Got invalid theme mode: . Resetting to auto.` into the console (F12). It is harmless:
  the site follows the light or dark setting of the system either way. `source/conf.py` says why
  the setting that would stop the message is left out.
- **Machines.** Made for and tried on WSL 2 (Ubuntu, x86_64). The ready-made Doxygen is for x86_64
  processors; on another processor `./setup.sh` says how to use a Doxygen of your own.
