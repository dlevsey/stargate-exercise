using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Commands;
using StargateAPI.Business.Data;

namespace StargateAPI.Tests;

// A real SQLite database that lives in memory for one test.
// The handlers run raw SQL through the context's connection, so they need a real relational database.
public sealed class TestDatabase : IDisposable
{
    private readonly SqliteConnection _connection;
    private readonly DbContextOptions<StargateContext> _options;

    public TestDatabase()
    {
        // An in-memory database disappears when its connection closes, so one connection stays open.
        _connection = new SqliteConnection("Data Source=:memory:");
        _connection.Open();
        _options = new DbContextOptionsBuilder<StargateContext>().UseSqlite(_connection).Options;

        using var context = NewContext();
        context.Database.EnsureCreated();
    }

    // A new context per call, the way each HTTP request gets its own.
    public StargateContext NewContext() => new StargateContext(_options);

    // Runs the pre-processor and then the handler, in the order MediatR runs them.
    public async Task<CreatePersonResult> AddPerson(string name)
    {
        using var context = NewContext();
        var request = new CreatePerson { Name = name };
        await new CreatePersonPreProcessor(context).Process(request, CancellationToken.None);
        return await new CreatePersonHandler(context).Handle(request, CancellationToken.None);
    }

    public async Task<CreateAstronautDutyResult> AddDuty(string name, string rank, string dutyTitle, DateTime dutyStartDate)
    {
        using var context = NewContext();
        var request = new CreateAstronautDuty { Name = name, Rank = rank, DutyTitle = dutyTitle, DutyStartDate = dutyStartDate };
        await new CreateAstronautDutyPreProcessor(context).Process(request, CancellationToken.None);
        return await new CreateAstronautDutyHandler(context).Handle(request, CancellationToken.None);
    }

    public void Dispose() => _connection.Dispose();
}
