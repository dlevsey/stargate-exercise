using System.Net;
using System.Net.Http.Json;
using StargateAPI.Business.Commands;
using StargateAPI.Business.Queries;
using StargateAPI.Controllers;

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

        Assert.Equal(HttpStatusCode.Conflict, second.StatusCode);
        var body = await second.Content.ReadFromJsonAsync<BaseResponse>();
        Assert.False(body!.Success);
        Assert.Equal(409, body.ResponseCode);
        var people = await _client.GetFromJsonAsync<GetPeopleResult>("/Person");
        Assert.Single(people!.People);
    }

    [Fact]
    public async Task An_unknown_person_returns_404()
    {
        var response = await _client.GetAsync("/Person/Nobody");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<BaseResponse>();
        Assert.False(body!.Success);
        Assert.Equal("Person not found.", body.Message);
    }

    // POST /AstronautDuty had no try/catch at all: this used to be an unhandled exception.
    [Fact]
    public async Task A_duty_for_an_unknown_person_returns_404()
    {
        var response = await _client.PostAsJsonAsync("/AstronautDuty", Duty("Nobody", "Pilot", new DateTime(2024, 1, 15)));

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        Assert.False((await response.Content.ReadFromJsonAsync<BaseResponse>())!.Success);
    }

    [Fact]
    public async Task A_repeated_duty_returns_409_and_a_back_dated_duty_returns_400()
    {
        await _client.PostAsJsonAsync("/Person", "Jane Roe");
        var first = await _client.PostAsJsonAsync("/AstronautDuty", Duty("Jane Roe", "Pilot", new DateTime(2024, 1, 15)));
        Assert.Equal(HttpStatusCode.OK, first.StatusCode);

        var repeated = await _client.PostAsJsonAsync("/AstronautDuty", Duty("Jane Roe", "Pilot", new DateTime(2024, 1, 15)));
        var backDated = await _client.PostAsJsonAsync("/AstronautDuty", Duty("Jane Roe", "Trainee", new DateTime(2023, 6, 1)));

        Assert.Equal(HttpStatusCode.Conflict, repeated.StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, backDated.StatusCode);
    }

    // Anything unexpected becomes a 500 with a fixed message: no SQL, no table names, no stack trace.
    [Fact]
    public async Task An_unexpected_error_returns_500_without_internal_details()
    {
        using var broken = new ApiFactory(createDatabase: false);

        var response = await broken.CreateClient().GetAsync("/Person");

        Assert.Equal(HttpStatusCode.InternalServerError, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync();
        Assert.Contains("An unexpected error occurred.", text);
        Assert.DoesNotContain("SQLite", text);
    }

    [Fact]
    public async Task Blank_and_missing_values_return_400()
    {
        var blankName = await _client.PostAsJsonAsync("/Person", "   ");
        await _client.PostAsJsonAsync("/Person", "Jane Roe");
        var noStartDate = await _client.PostAsJsonAsync("/AstronautDuty", new { name = "Jane Roe", rank = "1LT", dutyTitle = "Pilot" });

        Assert.Equal(HttpStatusCode.BadRequest, blankName.StatusCode);
        Assert.Equal("Name is required.", (await blankName.Content.ReadFromJsonAsync<BaseResponse>())!.Message);
        Assert.Equal(HttpStatusCode.BadRequest, noStartDate.StatusCode);
        Assert.Equal("DutyStartDate is required.", (await noStartDate.Content.ReadFromJsonAsync<BaseResponse>())!.Message);
    }

    private static CreateAstronautDuty Duty(string name, string dutyTitle, DateTime start) =>
        new() { Name = name, Rank = "1LT", DutyTitle = dutyTitle, DutyStartDate = start };
}
