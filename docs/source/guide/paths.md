# Paths through the code

Each drawing on this page follows one thing from where it starts to where it ends: a request, an error,
a setting, a row of data. [Start here](start-here.md) explains the parts in words; this page shows the routes
between them.

```{note}
These drawings are written by hand from the code as it was on 2026-11-17. They do not redraw themselves when
the code changes. The names under each drawing are checked at every build, so a renamed or removed class
shows up as a warning there.
```

How to read them:

| Shape | Meaning |
|---|---|
| white box | a class or method of this project (click it to open it in the code reference) |
| grey box | something ASP.NET Core, MediatR or EF Core does |
| yellow box | a table in the database |
| diamond | a question the code asks; the lines leaving it are the answers |
| solid line | the next step |
| dashed line | reads from, or belongs to, without being a step of its own |

## All five routes at a glance

Read from left to right: the address, the controller action that receives it, the request object the action
sends, the handler that MediatR picks for that object, and the tables the handler touches.

```{graphviz}
:align: center

digraph routes {
  graph [rankdir=LR bgcolor="transparent" nodesep=0.25 ranksep=0.55 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];

  r1 [label="GET /Person" shape=plain];
  r2 [label="GET /Person/{name}" shape=plain];
  r3 [label="POST /Person" shape=plain];
  r4 [label="GET /AstronautDuty/{name}" shape=plain];
  r5 [label="POST /AstronautDuty" shape=plain];

  a1 [label="PersonController\nGetPeople" URL="../api/StargateAPI.Controllers.html#class-StargateAPI.Controllers.PersonController" target="_top"];
  a2 [label="PersonController\nGetPersonByName" URL="../api/StargateAPI.Controllers.html#class-StargateAPI.Controllers.PersonController" target="_top"];
  a3 [label="PersonController\nCreatePerson" URL="../api/StargateAPI.Controllers.html#class-StargateAPI.Controllers.PersonController" target="_top"];
  a4 [label="AstronautDutyController\nGetAstronautDutiesByName" URL="../api/StargateAPI.Controllers.html#class-StargateAPI.Controllers.AstronautDutyController" target="_top"];
  a5 [label="AstronautDutyController\nCreateAstronautDuty" URL="../api/StargateAPI.Controllers.html#class-StargateAPI.Controllers.AstronautDutyController" target="_top"];

  q1 [label="GetPeople" URL="../api/StargateAPI.Business.Queries.html#class-StargateAPI.Business.Queries.GetPeople" target="_top"];
  q2 [label="GetPersonByName" URL="../api/StargateAPI.Business.Queries.html#class-StargateAPI.Business.Queries.GetPersonByName" target="_top"];
  q3 [label="CreatePerson" URL="../api/StargateAPI.Business.Commands.html#class-StargateAPI.Business.Commands.CreatePerson" target="_top"];
  q4 [label="GetAstronautDutiesByName" URL="../api/StargateAPI.Business.Queries.html#class-StargateAPI.Business.Queries.GetAstronautDutiesByName" target="_top"];
  q5 [label="CreateAstronautDuty" URL="../api/StargateAPI.Business.Commands.html#class-StargateAPI.Business.Commands.CreateAstronautDuty" target="_top"];

  h1 [label="GetPeopleHandler" URL="../api/StargateAPI.Business.Queries.html#class-StargateAPI.Business.Queries.GetPeopleHandler" target="_top"];
  h2 [label="GetPersonByNameHandler" URL="../api/StargateAPI.Business.Queries.html#class-StargateAPI.Business.Queries.GetPersonByNameHandler" target="_top"];
  h3 [label="CreatePersonHandler" URL="../api/StargateAPI.Business.Commands.html#class-StargateAPI.Business.Commands.CreatePersonHandler" target="_top"];
  h4 [label="GetAstronautDutiesByNameHandler" URL="../api/StargateAPI.Business.Queries.html#class-StargateAPI.Business.Queries.GetAstronautDutiesByNameHandler" target="_top"];
  h5 [label="CreateAstronautDutyPreProcessor\nthen CreateAstronautDutyHandler" URL="../api/StargateAPI.Business.Commands.html#class-StargateAPI.Business.Commands.CreateAstronautDutyHandler" target="_top"];

  node [fillcolor="#fff6d6" color="#b89b3c" shape=cylinder margin="0.1,0.04"];
  person [label="Person"];
  detail [label="AstronautDetail"];
  duty [label="AstronautDuty"];

  r1 -> a1 -> q1 -> h1;
  r2 -> a2 -> q2 -> h2;
  r3 -> a3 -> q3 -> h3;
  r4 -> a4;
  a4 -> q2 [label="sends"];
  r5 -> a5 -> q5 -> h5;
  q4 -> h4;

  h1 -> person [label="reads"]; h1 -> detail [label="reads"];
  h2 -> person [label="reads"]; h2 -> detail [label="reads"];
  h3 -> person [label="writes"];
  h4 -> person [label="reads"]; h4 -> detail [label="reads"]; h4 -> duty [label="reads"];
  h5 -> person [label="reads"]; h5 -> detail [label="reads, writes"]; h5 -> duty [label="reads, writes"];
}
```

- The actions are {cs:meth}`PersonController.GetPeople`, {cs:meth}`PersonController.GetPersonByName`,
  {cs:meth}`PersonController.CreatePerson`, {cs:meth}`AstronautDutyController.GetAstronautDutiesByName` and
  {cs:meth}`AstronautDutyController.CreateAstronautDuty`.
- The line from each request object to its handler is drawn by MediatR, not by the code: a handler says which
  request it is for in its base type, such as `IRequestHandler<GetPeople, GetPeopleResult>`.
- The drawing follows the code line by line. In `AstronautDutyController.cs`, line 24, the action
  for `GET /AstronautDuty/{name}` creates a {cs:type}`GetPersonByName` object. No action creates a
  {cs:type}`GetAstronautDutiesByName` object, so nothing leads into its handler.

## Start-up: what `Program.cs` sets up

`Program.cs` runs once, from top to bottom. The first half fills the list of services; the second half lays
out the stations every request passes, in this order.

```{graphviz}
:align: center

digraph startup {
  graph [rankdir=TB bgcolor="transparent" nodesep=0.3 ranksep=0.35 fontname="Helvetica" fontsize=10 compound=true];
  node [shape=box style="rounded,filled" fillcolor="#eef1f5" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];

  subgraph cluster_services {
    label="1. Services are registered (lines 5 to 20)"; color="#c3c9d2"; style="rounded";
    s1 [label="AddControllers\nthe two controllers"];
    s2 [label="AddEndpointsApiExplorer, AddSwaggerGen\nthe description of the API"];
    s3 [label="AddDbContext<StargateContext>\nUseSqlite(connection string)"];
    s4 [label="AddMediatR\nfinds the handlers in the project,\nnames CreateAstronautDutyPreProcessor"];
    s1 -> s2 -> s3 -> s4;
  }
  build [label="builder.Build()   line 22"];
  subgraph cluster_pipeline {
    label="2. The stations of a request (lines 25 to 35)"; color="#c3c9d2"; style="rounded";
    p1 [label="Swagger and Swagger UI\nonly in Development"];
    p2 [label="UseHttpsRedirection\nan http request is sent on to https"];
    p3 [label="UseAuthorization"];
    p4 [label="MapControllers\nthe address picks the action"];
    p1 -> p2 -> p3 -> p4;
  }
  run [label="app.Run()   line 37\nthe application now waits for requests"];
  s4 -> build [ltail=cluster_services];
  build -> p1 [lhead=cluster_pipeline];
  p4 -> run [ltail=cluster_pipeline];
}
```

The class behind `AddDbContext` is {cs:type}`StargateContext`; the pre-processor named in `AddMediatR` is
{cs:type}`CreateAstronautDutyPreProcessor`.

## A setting: from `appsettings.json` to the database file

```{graphviz}
:align: center

digraph setting {
  graph [rankdir=LR bgcolor="transparent" nodesep=0.3 ranksep=0.45 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="#eef1f5" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];
  file [label="appsettings.json\nConnectionStrings:\nStarbaseApiDatabase"];
  get [label="GetConnectionString\n(\"StarbaseApiDatabase\")\nProgram.cs line 14"];
  sqlite [label="UseSqlite\n\"Data Source=starbase.db\""];
  context [label="StargateContext" fillcolor="white" URL="../api/StargateAPI.Business.Data.html#class-StargateAPI.Business.Data.StargateContext" target="_top"];
  db [label="starbase.db" shape=cylinder fillcolor="#fff6d6" color="#b89b3c"];
  file -> get -> sqlite -> context -> db;
}
```

`starbase.db` has no folder in front of it, so SQLite looks for it in the folder the application was started
from. The file is not in the repository; the first task of the exercise creates it.

## Reading: the three `GET` requests

All three follow the same short path. They differ in the request object and in the SQL text.

```{graphviz}
:align: center

digraph reading {
  graph [rankdir=LR bgcolor="transparent" nodesep=0.3 ranksep=0.45 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];
  action [label="action\ncreates the request object"];
  send [label="IMediator.Send" fillcolor="#eef1f5"];
  handler [label="handler\nbuilds the SQL text"];
  dapper [label="Dapper\nQueryAsync on\nStargateContext.Connection" fillcolor="#eef1f5"];
  tables [label="Person\nLEFT JOIN\nAstronautDetail" shape=cylinder fillcolor="#fff6d6" color="#b89b3c"];
  result [label="result object\nSuccess = true\nResponseCode = 200"];
  answer [label="GetResponse\nJSON, status 200"];
  action -> send -> handler -> dapper -> tables;
  tables -> dapper [label="rows" style=dashed constraint=false];
  handler -> result -> answer;
}
```

| Request | SQL reads | The result holds |
|---|---|---|
| {cs:type}`GetPeople` | every `Person` row with its `AstronautDetail` row, if it has one | {cs:prop}`GetPeopleResult.People`, a list of {cs:type}`PersonAstronaut` |
| {cs:type}`GetPersonByName` | the same join, for one name | {cs:prop}`GetPersonByNameResult.Person`, one {cs:type}`PersonAstronaut` or nothing |
| {cs:type}`GetAstronautDutiesByName` | the same join for one name, then that person's `AstronautDuty` rows, newest first | {cs:prop}`GetAstronautDutiesByNameResult.Person` and {cs:prop}`GetAstronautDutiesByNameResult.AstronautDuties` |

A `LEFT JOIN` keeps a person who has no `AstronautDetail` row; the four astronaut columns are then empty.
The values `Success = true` and `ResponseCode = 200` are not set by the handlers: they are the starting
values in {cs:type}`BaseResponse`.

## Writing: `POST /Person`

```{graphviz}
:align: center

digraph createperson {
  graph [rankdir=TB bgcolor="transparent" nodesep=0.35 ranksep=0.35 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];
  body [label="body: \"Jane Doe\"" shape=plain];
  action [label="PersonController.CreatePerson\nnew CreatePerson { Name = name }"];
  send [label="IMediator.Send" fillcolor="#eef1f5"];
  pre [label="CreatePersonPreProcessor\nis there a person with this name?\nif yes: throw" style="rounded,filled,dashed"];
  handler [label="CreatePersonHandler.Handle\nnew Person { Name }"];
  add [label="People.AddAsync\nSaveChangesAsync" fillcolor="#eef1f5"];
  person [label="Person\none new row" shape=cylinder fillcolor="#fff6d6" color="#b89b3c"];
  result [label="CreatePersonResult\nId = the new row's Id"];
  answer [label="GetResponse\nJSON, status 200"];
  body -> action -> send -> handler -> add -> person;
  send -> pre [style=dashed label="only if registered"];
  add -> result [label="the database\nhas set Id"];
  result -> answer;
}
```

- {cs:type}`CreatePersonPreProcessor` is drawn with a dashed border. The class is in `CreatePerson.cs`, and
  MediatR runs a pre-processor only when it has been registered. `Program.cs`, line 18, names
  {cs:type}`CreateAstronautDutyPreProcessor`; it does not name this one.
- EF Core writes the row at `SaveChangesAsync`, not at `AddAsync`. After the save, `newPerson.Id` holds the
  number the database gave the row, and {cs:meth}`CreatePersonHandler.Handle` puts it into
  {cs:prop}`CreatePersonResult.Id`.

## Writing: `POST /AstronautDuty`

This is the longest path in the project. The pre-processor asks two questions; then the handler reads three
things, changes up to two rows, adds one, and saves everything at once.

```{graphviz}
:align: center

digraph createduty {
  graph [rankdir=TB bgcolor="transparent" nodesep=0.3 ranksep=0.32 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];

  body [label="body: Name, Rank, DutyTitle, DutyStartDate" shape=plain];
  action [label="AstronautDutyController.CreateAstronautDuty\nthe body already is the request object"];
  send [label="IMediator.Send" fillcolor="#eef1f5"];

  subgraph cluster_pre {
    label="CreateAstronautDutyPreProcessor.Process   (EF Core, lines 31 to 42)"; color="#c3c9d2"; style="rounded"; fontname="Helvetica"; fontsize=9;
    k1 [label="a person with\nthis Name?" shape=diamond style="filled" fillcolor="white"];
    k2 [label="a duty with the same\nDutyTitle and DutyStartDate?" shape=diamond style="filled" fillcolor="white"];
  }
  stop [label="throw BadHttpRequestException\n(\"Bad Request\")" color="#b3564b"];

  subgraph cluster_handler {
    label="CreateAstronautDutyHandler.Handle   (lines 53 to 117)"; color="#c3c9d2"; style="rounded"; fontname="Helvetica"; fontsize=9;
    h1 [label="read the Person by name   (Dapper)"];
    h2 [label="read this person's AstronautDetail   (Dapper)"];
    d1 [label="is there an\nAstronautDetail?" shape=diamond style="filled" fillcolor="white"];
    new [label="new AstronautDetail\nCurrentDutyTitle, CurrentRank\nCareerStartDate = start date\nRETIRED: CareerEndDate = start date\nAstronautDetails.AddAsync"];
    upd [label="change the one that was read\nCurrentDutyTitle, CurrentRank\nRETIRED: CareerEndDate = start date - 1 day\nAstronautDetails.Update"];
    h3 [label="read this person's newest AstronautDuty   (Dapper)"];
    d2 [label="is there an\nearlier duty?" shape=diamond style="filled" fillcolor="white"];
    close [label="its DutyEndDate = start date - 1 day\nAstronautDuties.Update"];
    add [label="new AstronautDuty\nDutyEndDate = null\nAstronautDuties.AddAsync"];
    save [label="SaveChangesAsync\nall changes are written together" fillcolor="#eef1f5"];
  }
  result [label="CreateAstronautDutyResult\nId = the new duty's Id"];
  answer [label="GetResponse\nJSON, status 200"];

  body -> action -> send -> k1;
  k1 -> k2 [label="yes"];
  k1 -> stop [label="no"];
  k2 -> stop [label="yes"];
  k2 -> h1 [label="no"];
  h1 -> h2 -> d1;
  d1 -> new [label="no"];
  d1 -> upd [label="yes"];
  new -> h3; upd -> h3;
  h3 -> d2;
  d2 -> close [label="yes"];
  d2 -> add [label="no"];
  close -> add -> save -> result -> answer;
}
```

- The two classes are {cs:type}`CreateAstronautDutyPreProcessor` and {cs:type}`CreateAstronautDutyHandler`;
  the result is {cs:type}`CreateAstronautDutyResult`.
- The pre-processor reads through EF Core (`_context.People`, `_context.AstronautDuties`). The handler reads
  with Dapper and SQL text, and writes through EF Core. Both use the same {cs:type}`StargateContext`.
- The rules that this path has to keep are in the exercise's README:
  [Stargate](../project/README.md), section *Rules*. The drawing shows what the code does,
  not what the rules ask for.

### What one call changes in the tables

```{graphviz}
:align: center

digraph changes {
  graph [rankdir=LR bgcolor="transparent" nodesep=0.3 ranksep=0.7 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];
  call [label="POST /AstronautDuty\nfor one person"];
  node [shape=cylinder fillcolor="#fff6d6" color="#b89b3c"];
  person [label="Person\nnothing changes"];
  detail [label="AstronautDetail\nfirst duty: one new row\nlater duty: the row is changed"];
  old [label="AstronautDuty, newest row so far\nDutyEndDate is filled in"];
  fresh [label="AstronautDuty, new row\nDutyEndDate is empty"];
  call -> person [label="read" style=dashed];
  call -> detail [label="add or change"];
  call -> old [label="change, if there is one"];
  call -> fresh [label="add"];
}
```

The tables are {cs:type}`Person`, {cs:type}`AstronautDetail` and {cs:type}`AstronautDuty`;
[Data model](../diagrams/data-model.md) shows their columns.

## When something goes wrong: the path of an exception

An *exception* is how code reports that it cannot go on. It travels back up through every method that was
waiting, until one of them catches it.

```{graphviz}
:align: center

digraph errors {
  graph [rankdir=TB bgcolor="transparent" nodesep=0.4 ranksep=0.38 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];
  thrown [label="an exception is thrown\nin a pre-processor, a handler,\nDapper, EF Core or SQLite" color="#b3564b"];
  mediator [label="IMediator.Send\npasses it on" fillcolor="#eef1f5"];
  q [label="does the action have\ntry / catch?" shape=diamond style="filled" fillcolor="white"];
  catch [label="catch (Exception ex)\nnew BaseResponse\nMessage = ex.Message\nSuccess = false\nResponseCode = 500"];
  answer [label="GetResponse\nJSON, status 500"];
  asp [label="ASP.NET Core answers by itself\nthe answer is not a BaseResponse" fillcolor="#eef1f5"];
  thrown -> mediator -> q;
  q -> catch [label="yes: GetPeople, GetPersonByName,\nCreatePerson, GetAstronautDutiesByName"];
  q -> asp [label="no: CreateAstronautDuty"];
  catch -> answer;
}
```

- Four actions wrap their work in `try` / `catch`. The fifth,
  {cs:meth}`AstronautDutyController.CreateAstronautDuty` (lines 43 to 47), has none.
- The `catch` blocks catch every kind of exception and always answer with status 500, whatever the reason was.
  That includes the `BadHttpRequestException` a pre-processor throws.
- No handler sets {cs:prop}`BaseResponse.Success` to `false` or changes {cs:prop}`BaseResponse.ResponseCode`
  itself. A result that comes back from a handler always says 200.
- An example you can see without writing code: before the database exists, `GET /Person` answers with status
  500 and the message `SQLite Error 1: 'no such table: Person'`. That message took exactly the left path.

## The answer: from result object to HTTP

```{graphviz}
:align: center

digraph answer {
  graph [rankdir=LR bgcolor="transparent" nodesep=0.3 ranksep=0.45 fontname="Helvetica"];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=10 margin="0.12,0.06"];
  edge [color="#55606e" fontname="Helvetica" fontsize=8];
  result [label="result object\nfor example GetPeopleResult\nderives from BaseResponse"];
  get [label="this.GetResponse(result)"];
  obj [label="new ObjectResult(result)\nStatusCode = result.ResponseCode" fillcolor="#eef1f5"];
  json [label="ASP.NET Core writes the object\nas JSON" fillcolor="#eef1f5"];
  http [label="HTTP answer\nstatus + JSON body" shape=plain];
  result -> get -> obj -> json -> http;
}
```

{cs:meth}`ControllerBaseExtensions.GetResponse` is the only place that decides the status code, and it takes
it from {cs:prop}`BaseResponse.ResponseCode`. The JSON body always holds `success`, `message` and
`responseCode`, together with what the result class adds, such as `people` or `id`.
