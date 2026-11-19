using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Data;
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

    // Rule 1: a person is uniquely identified by their name.
    [Fact]
    public async Task Adding_the_same_name_twice_is_refused()
    {
        await _db.AddPerson("Jane Roe");

        var refused = await Assert.ThrowsAsync<BadHttpRequestException>(() => _db.AddPerson("Jane Roe"));
        Assert.Equal(409, refused.StatusCode);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task A_blank_name_is_refused(string name)
    {
        var refused = await Assert.ThrowsAsync<BadHttpRequestException>(() => _db.AddPerson(name));

        Assert.Equal(400, refused.StatusCode);
    }

    [Fact]
    public async Task Names_that_differ_only_by_case_are_the_same_person()
    {
        await _db.AddPerson("Jane Roe");

        await Assert.ThrowsAsync<BadHttpRequestException>(() => _db.AddPerson("jane roe"));
    }

    // The unique index is the last line of defence, for example when two requests arrive together.
    [Fact]
    public async Task The_database_itself_refuses_a_duplicate_name()
    {
        await _db.AddPerson("Jane Roe");

        using var context = _db.NewContext();
        context.People.Add(new Person { Name = "JANE ROE" });

        await Assert.ThrowsAsync<DbUpdateException>(() => context.SaveChangesAsync());
    }
}
