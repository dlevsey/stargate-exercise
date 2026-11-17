using Microsoft.AspNetCore.Mvc;
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

        Assert.Equal("Jane Roe", result.Person.Name);
        Assert.Equal(new[] { "Commander", "Pilot" }, result.AstronautDuties.Select(d => d.DutyTitle));
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
