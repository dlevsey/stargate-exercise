using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Queries;
using StargateAPI.Controllers;

namespace StargateAPI.Tests;

public class QueryTests : IDisposable
{
    private readonly TestDatabase _db = new();

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task GetPersonByName_returns_the_current_rank_and_title()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        using var context = _db.NewContext();
        var result = await new GetPersonByNameHandler(context).Handle(new GetPersonByName { Name = "Jane Roe" }, CancellationToken.None);

        Assert.NotNull(result.Person);
        Assert.Equal("Jane Roe", result.Person.Name);
        Assert.Equal("1LT", result.Person.CurrentRank);
        Assert.Equal("Pilot", result.Person.CurrentDutyTitle);
        Assert.Equal(new DateTime(2024, 1, 15), result.Person.CareerStartDate);
    }

    [Fact]
    public async Task GetPersonByName_ignores_upper_and_lower_case()
    {
        await _db.AddPerson("Jane Roe");

        using var context = _db.NewContext();
        var result = await new GetPersonByNameHandler(context).Handle(new GetPersonByName { Name = "JANE ROE" }, CancellationToken.None);

        Assert.Equal("Jane Roe", result.Person?.Name);
    }

    [Fact]
    public async Task GetAstronautDutiesByName_returns_the_duties_newest_first()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));
        await _db.AddDuty("Jane Roe", "CPT", "Commander", new DateTime(2024, 6, 1));

        using var context = _db.NewContext();
        var result = await new GetAstronautDutiesByNameHandler(context).Handle(new GetAstronautDutiesByName { Name = "Jane Roe" }, CancellationToken.None);

        Assert.Equal("Jane Roe", result.Person?.Name);
        Assert.Equal(new[] { "Commander", "Pilot" }, result.AstronautDuties.Select(d => d.DutyTitle));
    }

    // A name with an apostrophe is ordinary data. In SQL built from strings it ended the text early and broke the query.
    [Fact]
    public async Task A_name_with_an_apostrophe_can_be_read_back()
    {
        await _db.AddPerson("Miles O'Brien");
        await _db.AddDuty("Miles O'Brien", "CPO", "Engineer", new DateTime(2024, 1, 15));

        using var context = _db.NewContext();
        var person = await new GetPersonByNameHandler(context).Handle(new GetPersonByName { Name = "Miles O'Brien" }, CancellationToken.None);
        var duties = await new GetAstronautDutiesByNameHandler(context).Handle(new GetAstronautDutiesByName { Name = "Miles O'Brien" }, CancellationToken.None);

        Assert.Equal("Miles O'Brien", person.Person?.Name);
        Assert.Equal("Engineer", Assert.Single(duties.AstronautDuties).DutyTitle);
    }

    // SQL injection: in SQL built from strings this name matched every row, so the first person in the table was used.
    [Fact]
    public async Task Sql_in_a_name_is_treated_as_text()
    {
        await _db.AddPerson("Jane Roe");
        var odd = await _db.AddPerson("' OR 1=1 --");
        await _db.AddDuty("' OR 1=1 --", "1LT", "Pilot", new DateTime(2024, 1, 15));

        using var context = _db.NewContext();
        var result = await new GetPersonByNameHandler(context).Handle(new GetPersonByName { Name = "' OR 1=1 --" }, CancellationToken.None);

        Assert.Equal(odd.Id, result.Person?.PersonId);
        Assert.Equal(odd.Id, (await context.AstronautDuties.SingleAsync()).PersonId);
    }

    // An unknown name used to give 200 with "person": null from one query and a NullReferenceException from the other.
    [Fact]
    public async Task Asking_for_an_unknown_person_is_refused_with_404()
    {
        using var context = _db.NewContext();

        var person = await Assert.ThrowsAsync<BadHttpRequestException>(
            () => new GetPersonByNameHandler(context).Handle(new GetPersonByName { Name = "Nobody" }, CancellationToken.None));
        var duties = await Assert.ThrowsAsync<BadHttpRequestException>(
            () => new GetAstronautDutiesByNameHandler(context).Handle(new GetAstronautDutiesByName { Name = "Nobody" }, CancellationToken.None));

        Assert.Equal(404, person.StatusCode);
        Assert.Equal(404, duties.StatusCode);
    }

    [Fact]
    public void GetResponse_uses_the_response_code_as_the_http_status()
    {
        var controller = new PersonController(null!);

        var result = controller.GetResponse(new BaseResponse { Success = false, Message = "Not found", ResponseCode = 404 });

        var objectResult = Assert.IsType<ObjectResult>(result);
        Assert.Equal(404, objectResult.StatusCode);
    }
}
