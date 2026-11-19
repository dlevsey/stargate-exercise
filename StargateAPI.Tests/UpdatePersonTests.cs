using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Commands;

namespace StargateAPI.Tests;

public class UpdatePersonTests : IDisposable
{
    private readonly TestDatabase _db = new();

    public void Dispose() => _db.Dispose();

    private async Task<UpdatePersonResult> Rename(string name, string newName)
    {
        using var context = _db.NewContext();
        var request = new UpdatePerson { Name = name, NewName = newName };
        await new UpdatePersonPreProcessor(context).Process(request, CancellationToken.None);
        return await new UpdatePersonHandler(context).Handle(request, CancellationToken.None);
    }

    [Fact]
    public async Task Renaming_changes_the_name_and_keeps_the_id()
    {
        var created = await _db.AddPerson("Jane Roe");

        var result = await Rename("Jane Roe", "Jane Doe");

        Assert.Equal(created.Id, result.Id);
        using var context = _db.NewContext();
        Assert.Equal("Jane Doe", (await context.People.SingleAsync()).Name);
    }

    [Fact]
    public async Task Changing_only_the_capital_letters_of_a_name_is_allowed()
    {
        await _db.AddPerson("jane roe");

        await Rename("jane roe", "Jane Roe");

        using var context = _db.NewContext();
        Assert.Equal("Jane Roe", (await context.People.SingleAsync()).Name);
    }

    [Theory]
    [InlineData("Nobody", "Somebody", 404)]
    [InlineData("Jane Roe", "Sam Poe", 409)]
    [InlineData("Jane Roe", " ", 400)]
    public async Task A_rename_that_cannot_be_done_is_refused(string name, string newName, int expectedStatus)
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddPerson("Sam Poe");

        var refused = await Assert.ThrowsAsync<BadHttpRequestException>(() => Rename(name, newName));

        Assert.Equal(expectedStatus, refused.StatusCode);
    }
}
