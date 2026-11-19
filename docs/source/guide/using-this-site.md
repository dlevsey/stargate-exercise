# Using this site

This page explains the popups, says where every page comes from, and shows how to add to the site.

## Hover popups

Rest the pointer on a link and a small window shows what the link points at: a page, a section, or the entry
of a class or member. You can read it without leaving the page you are on.

| You do | What happens |
|---|---|
| Rest the pointer on a link | The popup opens. |
| Keep the pointer on the link or the popup for about a second | The ring next to the title fills up. A full ring means the popup is *pinned*: it stays open when the pointer moves away. |
| Click the ring | Pins the popup at once, or un-pins a pinned one. |
| Rest the pointer on a link inside a popup | A second popup opens, and the first one is pinned so that it stays. This works to any depth. |
| Click **×** | Closes that popup and every popup opened from inside it. |
| Press {kbd}`Esc` | Closes the newest popup. |
| Click anywhere on the page outside the popups | Closes all of them. |
| Click **Open full page** | Goes to the page, as the link itself would. |

With the keyboard: {kbd}`Tab` to a link opens its popup. {kbd}`↓` moves into the popup, where the arrow keys
scroll and {kbd}`Tab` reaches the links and buttons. {kbd}`Esc` closes it and returns to the link.
{kbd}`Enter` on a link follows it as usual.

Three things to know:

- **.NET names have popups too.** A name such as `Guid` or `DbContext` links to Microsoft's documentation.
  Its popup shows the description that ships with the .NET SDK, saved when the site was built, so nothing is
  fetched from Microsoft while you read. The footer of such a popup says "Saved preview" and the date.
- **Popups need a web server.** Start one with `./serve.sh`. If you open the HTML files straight from the
  folder, the pages work but the popups do not.
- **Touch screens get no popups.** A tap follows the link.

## Where each page comes from

| Pages | Made from | Made by |
|---|---|---|
| Guides | Markdown files in `source/guide/`, written by hand | a person |
| [From the repository](../project/index.md) | every Markdown file in the repository, such as the README files | `tools/prebuild.py` copies them at every build |
| [Data model](../diagrams/data-model.md) | the model snapshot, the file `...ModelSnapshot.cs` that EF Core keeps beside the migrations | `tools/gen_diagrams.py` |
| [Projects and packages](../diagrams/projects.md) | the project files (`.csproj`) | `tools/gen_diagrams.py` |
| [HTTP endpoints](../http/index.md) | the OpenAPI description the API publishes | `tools/gen_endpoints.py` |
| [Code reference](../api/index.md) | every `.cs` file of every project in the repository | Doxygen, then `tools/gen_pages.py` |

A project that holds tests is left out of the code reference, so that the reference stays about the application.
The line `STARGATE_DOCS_TESTS=1` in the file `local.env` puts test projects in as well.

Generated pages are written into `source/api/`, `source/diagrams/`, `source/http/` and `source/project/`.
Do not edit them: the next build overwrites them. Change the code or the original file and build again.

One page has a condition. The **HTTP endpoints** come from the running API. When the API is running during a
build (`http://localhost:5204`), the build asks it for a fresh description and keeps a copy in
`data/openapi.json`. When it is not running, the build uses that copy. The page says on which date the copy
was saved.

```{note}
The build runs in WSL, and Visual Studio runs the API on Windows. With the usual WSL set-up a program in WSL
cannot reach a Windows program at `localhost`. So when the direct request fails, the build asks Windows to
fetch the description, with the `curl.exe` that comes with Windows.
```

## Building the site

All commands are run in the docs project folder, in WSL.

| Command | What it does |
|---|---|
| `./setup.sh` | Once: creates a private Python environment with the packages listed in `requirements.txt`, and downloads Doxygen. Both go into `~/.local/share/stargate-docs`. It does not use `sudo` and changes nothing else on the machine. |
| `./build.sh` | Builds the whole site from nothing into `_build/html/`. Stops with an error when a check fails (see below). |
| `./serve.sh` | Serves the built site at `http://localhost:8770`. |
| `./watch.sh` | Builds, serves at `http://localhost:8770`, and builds again whenever a C# file, a repository document or a page of this site is saved. The page in the browser reloads by itself. |
| `./test.sh` | Checks the build tools themselves. Needed only after changing a tool or installing another version of Doxygen. |

`./watch.sh` is the one to leave running while you work on the code: a change shows up a few seconds
after you save. Where `./build.sh` stops at a problem, `./watch.sh` prints it as a warning and carries on.
So run `./build.sh` before you rely on the result.

Two things `./watch.sh` cannot notice by itself:

- **A new folder directly inside a C# project**, such as a new `api/Services/`. Stop the script
  and start it again. New files, and new folders inside a folder that was already there, are noticed.
- **A new project, or a new Markdown file in a folder that held none.** Stop the script and start it again.
- **A change in the running API.** The HTTP endpoints page is refreshed during a build, and a build starts
  when a file is saved. Restart the API, then save any file or run `./build.sh`.

The scripts look for the repository in the folder above the docs project. If the docs project is somewhere
else, a file named `local.env` says where the repository is. `local.env.example` shows how.

`README.md` in the docs project folder has the details, including what to do when a build fails.

## Adding a guide page

1. Create a Markdown file in `source/guide/`, for example `source/guide/reports.md`, that starts with a
   `# Title` line.
2. Add its name without `.md` to the first list in `source/index.md` (under `:caption: Guides`).
3. Run `./build.sh`, or look at the browser if `./watch.sh` is running.

A change to a repository document needs nothing here: edit the README file in the repository, and the next
build copies it. A new Markdown file anywhere in the repository appears in the menu by itself.

## Linking to code

Write the name of a class or member with a *role* in front of it. The build turns it into a link with a
popup, and it warns you when the name no longer exists.

| You write | You get |
|---|---|
| ``{cs:type}`Person` `` | {cs:type}`Person` (a class, record, interface or enum) |
| ``{cs:meth}`CreatePersonHandler.Handle` `` | {cs:meth}`CreatePersonHandler.Handle` (a method or a constructor) |
| ``{cs:prop}`BaseResponse.ResponseCode` `` | {cs:prop}`BaseResponse.ResponseCode` (a property) |
| ``{cs:var}`PersonController._mediator` `` | {cs:var}`PersonController._mediator` (a field or constant) |
| ``{cs:enum}`Name` `` | an enum (the code has none at the moment) |
| ``{cs:enumerator}`Name.Value` `` | one value of an enum |

Leave type arguments out: for a class `Result<T>`, write ``{cs:type}`Result` ``.

Some names are used twice in this code: `CreatePerson` is a class in `Business/Commands/` and also a method of
`PersonController`. The role decides which one is meant: ``{cs:type}`CreatePerson` `` is the class, and
``{cs:meth}`PersonController.CreatePerson` `` is the method.

To show code, use `repo-code`. It reads the file from the repository at every build, so the sample is always
the real code, with its real line numbers:

````markdown
```{repo-code} api/Business/Commands/CreatePerson.cs
:start-at: public class CreatePersonHandler
:block:
```
````

| Option | Meaning |
|---|---|
| *(none)* | the whole file |
| `:start-at: text` | begin at the first line that contains this text |
| `:end-at: text` | stop at the first line after the start that contains this text, and include it |
| `:end-before: text` | the same, without that line |
| `:block:` | with `:start-at:`: show the whole method, class or other `{ ... }` block that begins there |
| `:no-caption:` | do not show the file path above the code |

Choose marker text that is unlikely to change and that appears only once, such as the first line of a method.
Two limits come from the way the options are read:

- the text must not begin with a quotation mark (`"` or `'`);
- the text must not contain a space followed by `#`. Everything from there on is ignored.

`./build.sh -v` prints one line for every sample with the file and the line numbers it picked. Search the
output for `repo-code`.

## What the build checks

`./build.sh` stops with an error when one of these is true:

- A name written with a `{cs:...}` role does not exist in the code. The message is
  "C# name not found in the code".
- A `repo-code` sample names a file that does not exist, or a marker that is not in the file.
- A link to another page or heading of this site leads nowhere.
- Doxygen did not find a type that is declared in the C# files. The code reference would silently miss it.
- Anything else Sphinx warns about.

So when a method is renamed, the build names every guide page that still uses the old name.

What no build can check is the **sentences**. If a page says "the handler saves once" and the code changes
to save twice, the sample on the page shows the new code and the sentence still says once. That is why every guide
page starts with the date it was last compared with the code. After a larger change, read the guide pages
that mention the changed classes again. The search box finds them.

## Descriptions in the code reference

The code reference takes its descriptions from `///` comments (XML documentation comments) in the C# files:

```csharp
/// <summary>
/// Adds one <see cref="Person"/> to the database and returns its id.
/// </summary>
public class CreatePersonHandler : IRequestHandler<CreatePerson, CreatePersonResult>
```

A type or member with such a comment shows the text under its signature and in its popup. One without shows
its signature only. The code has almost no such comments at the moment, so most entries are signatures.
Adding a comment and saving the file is all it takes; `./watch.sh` picks it up.

### The tags that are understood

| You write | You get |
|---|---|
| `<summary>` | the description, as the first paragraph |
| `<remarks>`, `<para>` | further paragraphs |
| `<param name="x">`, `<typeparam name="T">` | the lists "Parameters" and "Type Parameters" |
| `<returns>` | the entry "Returns" |
| `<exception cref="X">` | the entry "Throws", with the exception as a link |
| `<see cref="X"/>` | a link to `X` with a popup. `X` is a Stargate name or a .NET name |
| `<see cref="X">some words</see>` | the same link, shown as "some words" |
| `<see href="https://...">some words</see>` | a link to a web page |
| `<seealso cref="X"/>` | a "See also" line with the link |
| `<see langword="null"/>`, `<c>text</c>`, `<paramref name="x"/>`, `<typeparamref name="T"/>` | the word in code letters |
| `<list type="bullet">` with `<item><description>` | a list |
| `<example>` with `<code>` | a code sample |
| `<inheritdoc/>` | the comment of the interface member or base member that this member implements |

### Limits

- **One line.** A `<see ... />` tag has to start and end on the same line.
- **Names.** Write the name as in code: `cref="Person"` or `cref="BaseResponse.ResponseCode"`. Type
  arguments and parameter lists are allowed and ignored: `cref="Result{T}.From(T)"` links to
  `Result.From`, and the link shows the name without them.
- **A name that does not exist** is shown without a link. In a comment this does not stop the build. The build
  lists such names in one line near its end, after "Names in the code reference without a link".
- **Quotation marks.** Between two `"` signs a name is shown without a link. For a single `"` sign, such as
  the sign for inches, write `&quot;`. Otherwise the names up to the next `"` sign in the same comment lose
  their links.
- **Not linkable:** one parameter of a record (see below), operators and indexers.
- **`<inheritdoc cref="X"/>`** works like `<inheritdoc/>`: the `cref` is ignored.

### Records

The code has no records at the moment. For when it gets one: a record written on one line, such as
`record PersonName(string First, string Last);`, is shown with its parameters in the signature. `<param>` lines in
its comment become its "Parameters" list.

A record that also has members of its own, written inside `{ }`, is shown as a record with a member list. Its
parameters appear there as a constructor.

In both cases a single parameter cannot be linked: `` {cs:prop}`PersonName.First` `` is reported as a
name that does not exist. Link to the record instead.

## The second site: the dev docs

The build can make a second site from one long study document: a Markdown file named
`stargate-api-and-patterns.md` in the top folder of the repository. Every `##` heading of that file becomes a
page, class names in it get links and popups, and the two sites link to each other. A switch at the top of the
left column leads from one to the other.

There is no such file at the moment, so there is one site and no switch. The second site appears with the first
build after the file is created. To keep the file somewhere else, name it in `local.env` with the line
`STARGATE_COMPANION_DOC=/path/to/the-file.md`.

### Linking to the dev docs

On a page of this site, `[the words](companion:name-of-a-heading)` leads to a heading of the dev docs.
The heading is named by its text in small letters, with `-` for every space and without punctuation:
`## 3. Patterns` is `(companion:3-patterns)`. `(companion:)` alone leads to the first page.

A heading that the study document does not have is a warning, and `./build.sh` stops. While there is no study
document, such links are shown as plain text.
