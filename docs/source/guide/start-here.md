# Start here

*Last compared with the code: 2026-11-17.*

This page follows one request through the code, from the address that is called to the rows that are saved.
Every other request takes the same route, so after this page the rest of the code reads quickly.

## What is in the repository

One project, `StargateAPI`, in the folder `api/`. It is a web API written with ASP.NET Core.
[Projects and packages](../diagrams/projects.md) lists what it is built with. Three packages shape the code:

| Package | What the code uses it for |
|---|---|
| MediatR | handing each request from a controller to the class that handles it |
| Entity Framework Core (EF Core), with SQLite | the tables as C# classes, the migrations, and saving changes |
| Dapper | reading rows with SQL text that is written out in the code |

The folders inside the project:

| Folder | Holds |
|---|---|
| `Controllers/` | the two controllers, and {cs:type}`BaseResponse`, the shape every answer has |
| `Business/Commands/` | the requests that change data: {cs:type}`CreatePerson` and {cs:type}`CreateAstronautDuty` |
| `Business/Queries/` | the requests that only read: {cs:type}`GetPeople`, {cs:type}`GetPersonByName` and {cs:type}`GetAstronautDutiesByName` |
| `Business/Data/` | {cs:type}`StargateContext` and the three classes that are stored as tables |
| `Business/Dtos/` | {cs:type}`PersonAstronaut`, the shape in which a person is sent back |
| `Business/Migrations/` | the code that creates the tables |

The tasks and the rules of the exercise are in its README: [Stargate](../project/README.md).

## The route of a request

```{graphviz}
:align: center

digraph route {
  graph [rankdir=TB bgcolor="transparent" nodesep=0.3 ranksep=0.4];
  node [shape=box style="rounded,filled" fillcolor="white" color="#8a94a3" fontname="Helvetica" fontsize=11 margin="0.14,0.08"];
  edge [color="#55606e" fontname="Helvetica" fontsize=9];
  request [label="HTTP request" shape=plain];
  action [label="controller action"];
  mediator [label="IMediator.Send"];
  pre [label="pre-processor"];
  handler [label="handler"];
  answer [label="GetResponse"];
  response [label="HTTP answer" shape=plain];
  { rank=same; request -> action -> mediator -> pre; }
  { rank=same; response -> answer [dir=back]; answer -> handler [dir=back label="result"]; }
  pre -> handler;
}
```

The steps below use one request as the example: `POST /AstronautDuty`, which adds a duty for a person.

### 1. Start-up names the parts

`Program.cs` runs once, when the application starts. This part of it registers the pieces that every request
needs. *Registering* means telling ASP.NET Core that a class exists, so that it can create the class and hand it
to whoever asks for it in a constructor.

```{repo-code} api/Program.cs
:start-at: builder.Services.AddControllers();
:end-at: });
```

- `AddControllers` makes the controller classes answer HTTP requests.
- `AddDbContext` registers {cs:type}`StargateContext`, the class through which the code talks to the database, and
  tells it to use SQLite. The connection string named `StarbaseApiDatabase` is in `appsettings.json`; it names
  the file `starbase.db`.
- `AddMediatR` sets up MediatR. `RegisterServicesFromAssemblies` has it look through the project for the classes
  that handle requests, and `AddRequestPreProcessor` names a pre-processor (step 4).

### 2. The controller receives the request

```{repo-code} api/Controllers/AstronautDutyController.cs
:start-at: [HttpPost("")]
:block:
```

The attribute `[Route("[controller]")]` on {cs:type}`AstronautDutyController` gives the class the address
`/AstronautDuty`: its name without "Controller". `[HttpPost("")]` makes this method answer a `POST` to that
address, and `[FromBody]` has ASP.NET Core build the {cs:type}`CreateAstronautDuty` object from the JSON text of
the request.

The method does not do the work itself. It hands the object to `_mediator.Send(...)` and turns whatever comes
back into an HTTP answer (step 6).

### 3. The request is an object

```{repo-code} api/Business/Commands/CreateAstronautDuty.cs
:start-at: public class CreateAstronautDuty :
:block:
```

`IRequest<CreateAstronautDutyResult>` marks the class as a MediatR request whose answer is a
{cs:type}`CreateAstronautDutyResult`. MediatR is a *mediator*, a go-between: the controller knows only
`IMediator`, and MediatR finds the class that handles a request by the type of the request object. So a
controller never names a handler.

Each file in `Business/Commands/` and `Business/Queries/` holds everything that belongs to one request: the
request class, its handler, its result class and, for the two commands, a pre-processor.

### 4. A pre-processor runs before the handler

```{repo-code} api/Business/Commands/CreateAstronautDuty.cs
:start-at: public class CreateAstronautDutyPreProcessor
:block:
```

A *pre-processor* is a class that MediatR runs before the handler of the same request; that is what
`IRequestPreProcessor<CreateAstronautDuty>` says. This one compares the request with what is stored and stops it
by throwing a `BadHttpRequestException`.

### 5. The handler does the work

```{repo-code} api/Business/Commands/CreateAstronautDuty.cs
:start-at: public class CreateAstronautDutyHandler
:block:
```

{cs:meth}`CreateAstronautDutyHandler.Handle` talks to the database in two ways:

- It **reads** with Dapper. `_context.Connection` is the open connection to the database, and
  `QueryFirstOrDefaultAsync<T>` runs SQL text on it and fills one object of type `T` from the first row.
- It **writes** with EF Core. `AddAsync` and `Update` only note what has to change; `SaveChangesAsync` then sends
  all of it to the database.

In order, the method finds the person, creates or updates the person's {cs:type}`AstronautDetail`, closes the
person's latest {cs:type}`AstronautDuty`, adds the new one, saves, and returns the new id. The section *Rules* of
the [README](../project/README.md) says what has to be true after it has run.

### 6. The answer

Every result class derives from {cs:type}`BaseResponse`:

```{repo-code} api/Controllers/BaseResponse.cs
:start-at: public class BaseResponse
:block:
```

```{repo-code} api/Controllers/ControllerBaseExtensions.cs
:start-at: public static IActionResult GetResponse
:block:
```

{cs:meth}`ControllerBaseExtensions.GetResponse` puts the result object into the HTTP answer and uses its
`ResponseCode` as the HTTP status code. It is an *extension method*: the word `this` in front of its first
parameter lets a controller call it as `this.GetResponse(result)`, as if the method were part of the controller.

## Every request has the same parts

| Request | Handler | Result | Pre-processor |
|---|---|---|---|
| {cs:type}`GetPeople` | {cs:type}`GetPeopleHandler` | {cs:type}`GetPeopleResult` | |
| {cs:type}`GetPersonByName` | {cs:type}`GetPersonByNameHandler` | {cs:type}`GetPersonByNameResult` | |
| {cs:type}`GetAstronautDutiesByName` | {cs:type}`GetAstronautDutiesByNameHandler` | {cs:type}`GetAstronautDutiesByNameResult` | |
| {cs:type}`CreatePerson` | {cs:type}`CreatePersonHandler` | {cs:type}`CreatePersonResult` | {cs:type}`CreatePersonPreProcessor` |
| {cs:type}`CreateAstronautDuty` | {cs:type}`CreateAstronautDutyHandler` | {cs:type}`CreateAstronautDutyResult` | {cs:type}`CreateAstronautDutyPreProcessor` |

The controllers that send them are {cs:type}`PersonController` and {cs:type}`AstronautDutyController`.
[HTTP endpoints](../http/index.md) lists their addresses.

## Where the data lives

```{repo-code} api/Business/Data/StargateContext.cs
:start-at: public class StargateContext
:end-at: public DbSet<AstronautDuty>
```

- Each `DbSet` stands for one table: {cs:type}`Person`, {cs:type}`AstronautDetail` and {cs:type}`AstronautDuty`.
  [Data model](../diagrams/data-model.md) shows their columns and how they relate.
- `Connection` hands out the connection that EF Core itself uses. The Dapper calls in the handlers run on it.
- Each of the three files in `Business/Data/` also holds a configuration class, such as
  {cs:type}`PersonConfiguration`. {cs:meth}`StargateContext.OnModelCreating` picks those up with
  `ApplyConfigurationsFromAssembly`.
- `Business/Migrations/` holds one migration, `InitialCreate`, which creates the three tables, and the model
  snapshot that the data model page is drawn from.

The repository does not contain the database file. Creating it is the first task in the README
("Generate the database").

## Where to go next

| You want to | Read |
|---|---|
| know what the exercise asks for | [Stargate](../project/README.md), the sections *Tasks* and *Rules* |
| try a request | [HTTP endpoints](../http/index.md) |
| see every class with its members | [Code reference](../api/index.md) |
| add a page of your own to this site | [Using this site](using-this-site.md) |
