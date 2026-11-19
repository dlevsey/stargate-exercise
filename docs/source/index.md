# Stargate docs

Stargate is the API of ACTS, the Astronaut Career Tracking System: a record of the people who have served as
astronauts and of the duties they held. The code is a technical exercise. This site documents that code.

Most pages are made from the repository each time the site is built, so they cannot drift away from the code:

- the **code reference** comes from the C# files,
- the **HTTP endpoints** come from the description the running API publishes,
- the **data model** comes from the model snapshot that Entity Framework Core keeps beside the migrations,
- **projects and packages** come from the project files,
- the pages under **From the repository** are the README files of the exercise, with its tasks and rules.

The **guides** are written by hand. They point at classes and methods by name and show code by reading it from
the real file, so the build warns when something they mention has been renamed or removed.

```{tip}
Hover over any linked name to see what it is without leaving the page.
[Using this site](guide/using-this-site.md) explains the popups and how each page is kept up to date.
```

## Where to begin

| You want to | Read |
|---|---|
| see how one request travels through the code | [Start here](guide/start-here.md) |
| follow every route, an error, a setting and a saved row in drawings | [Paths through the code](guide/paths.md) |
| see the screens of the frontend as designed | [Frontend mockups](guide/mockups.md) |
| read the tasks and the rules of the exercise | [From the repository](project/index.md) |
| look up a class, method or property | [Code reference](api/index.md) |
| call the API | [HTTP endpoints](http/index.md) |
| see the tables and how they relate | [Data model](diagrams/data-model.md) |
| see what the project is built with | [Projects and packages](diagrams/projects.md) |

````{only} companion
```{admonition} There is a second site: the dev docs
:class: seealso
The [dev docs](companion:) is made from `stargate-api-and-patterns.md`, a long study document in the
repository. The two sites link to each other: a class name there leads to its entry in the code reference here, and
every type in the code reference names the parts of the dev docs that mention it. The switch at the top of
the left column takes you from one site to the other.
```
````

```{toctree}
:maxdepth: 1
:caption: Guides

guide/start-here
guide/paths
guide/mockups
guide/using-this-site
```

```{toctree}
:maxdepth: 1
:caption: From the repository

project/index
```

```{toctree}
:maxdepth: 1
:caption: Diagrams

diagrams/data-model
diagrams/projects
```

```{toctree}
:maxdepth: 2
:caption: Reference

http/index
api/index
```
