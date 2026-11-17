using System.Net;
using System.Net.Http.Json;
using StargateAPI.Business.Commands;
using StargateAPI.Business.Queries;

namespace StargateAPI.Tests;

// These tests send real HTTP requests through the whole application: routing, MediatR, handlers, database.
public class ApiTests : IDisposable
{
    private readonly ApiFactory _factory = new();
    private readonly HttpClient _client;

    public ApiTests() => _client = _factory.CreateClient();

    public void Dispose() => _factory.Dispose();

    [Fact]
    public async Task Get_people_on_an_empty_database_returns_an_empty_list()
    {
        var response = await _client.GetAsync("/Person");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<GetPeopleResult>();
        Assert.Empty(body!.People);
    }

    [Fact]
    public async Task A_person_can_be_added_and_read_back_by_name()
    {
        var created = await _client.PostAsJsonAsync("/Person", "Jane Roe");
        Assert.Equal(HttpStatusCode.OK, created.StatusCode);
        Assert.True((await created.Content.ReadFromJsonAsync<CreatePersonResult>())!.Id > 0);

        var response = await _client.GetAsync("/Person/Jane%20Roe");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<GetPersonByNameResult>();
        Assert.Equal("Jane Roe", body!.Person!.Name);
    }

    // Rule 1, through the real application: this is the test that fails when the pre-processor is not registered.
    [Fact]
    public async Task Adding_the_same_name_twice_is_refused()
    {
        await _client.PostAsJsonAsync("/Person", "Jane Roe");

        var second = await _client.PostAsJsonAsync("/Person", "Jane Roe");

        Assert.False(second.IsSuccessStatusCode);
        var people = await _client.GetFromJsonAsync<GetPeopleResult>("/Person");
        Assert.Single(people!.People);
    }
}
