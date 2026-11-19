using System.Net;
using System.Net.Http.Json;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging.Abstractions;
using StargateAPI.Business.Commands;
using StargateAPI.Business.Data;
using StargateAPI.Business.Logging;

namespace StargateAPI.Tests;

public class ProcessLogTests : IDisposable
{
    private readonly ApiFactory _factory = new();
    private readonly HttpClient _client;

    public ProcessLogTests() => _client = _factory.CreateClient();

    public void Dispose() => _factory.Dispose();

    private async Task<List<ProcessLog>> Logs()
    {
        using var scope = _factory.Services.CreateScope();
        return await scope.ServiceProvider.GetRequiredService<StargateContext>().ProcessLogs.OrderBy(l => l.Id).ToListAsync();
    }

    [Fact]
    public async Task A_successful_request_writes_one_log_row()
    {
        await _client.PostAsJsonAsync("/Person", "Jane Roe");

        var log = Assert.Single(await Logs());
        Assert.Equal("Information", log.Level);
        Assert.Equal("CreatePerson", log.Process);
        Assert.Null(log.Exception);
    }

    // The duplicate is refused by a pre-processor. The row shows that the logging sits around the pre-processors.
    [Fact]
    public async Task A_refused_request_writes_a_log_row_with_the_exception()
    {
        await _client.PostAsJsonAsync("/Person", "Jane Roe");

        var refused = await _client.PostAsJsonAsync("/Person", "Jane Roe");

        Assert.Equal(HttpStatusCode.Conflict, refused.StatusCode);
        var log = (await Logs()).Last();
        Assert.Equal("Error", log.Level);
        Assert.Equal("CreatePerson", log.Process);
        Assert.Equal("A person with this name already exists.", log.Message);
        Assert.Contains("BadHttpRequestException", log.Exception);
    }

    // The log row is written through its own context, so saving it does not save the request's half-done work.
    [Fact]
    public async Task The_log_row_is_saved_when_the_request_fails_half_way_and_the_request_work_is_not()
    {
        using var scope = _factory.Services.CreateScope();
        var requestContext = scope.ServiceProvider.GetRequiredService<StargateContext>();
        var behavior = new ProcessLoggingBehavior<CreatePerson, CreatePersonResult>(
            _factory.Services.GetRequiredService<IServiceScopeFactory>(),
            NullLogger<ProcessLoggingBehavior<CreatePerson, CreatePersonResult>>.Instance);

        await Assert.ThrowsAsync<InvalidOperationException>(() => behavior.Handle(
            new CreatePerson { Name = "Jane Roe" },
            () =>
            {
                requestContext.People.Add(new Person { Name = "Jane Roe" });
                throw new InvalidOperationException("failed half way");
            },
            CancellationToken.None));

        Assert.Equal("failed half way", Assert.Single(await Logs()).Message);
        Assert.Empty(await requestContext.People.AsNoTracking().ToListAsync());
    }
}
