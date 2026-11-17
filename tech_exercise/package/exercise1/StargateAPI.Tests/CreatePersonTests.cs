using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Queries;

namespace StargateAPI.Tests;

public class CreatePersonTests : IDisposable
{
    private readonly TestDatabase _db = new();

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task Adding_a_person_stores_them_and_returns_the_new_id()
    {
        var result = await _db.AddPerson("Jane Roe");

        Assert.True(result.Success);
        Assert.True(result.Id > 0);

        using var context = _db.NewContext();
        var people = await new GetPeopleHandler(context).Handle(new GetPeople(), CancellationToken.None);
        Assert.Equal("Jane Roe", Assert.Single(people.People).Name);
    }

    // Rule 2: a person who has not had an astronaut assignment has no astronaut records.
    [Fact]
    public async Task A_new_person_has_no_astronaut_records()
    {
        await _db.AddPerson("Jane Roe");

        using var context = _db.NewContext();
        Assert.Empty(await context.AstronautDetails.ToListAsync());
        Assert.Empty(await context.AstronautDuties.ToListAsync());
    }
}
