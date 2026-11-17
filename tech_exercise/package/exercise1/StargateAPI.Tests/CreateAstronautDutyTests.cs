using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;

namespace StargateAPI.Tests;

public class CreateAstronautDutyTests : IDisposable
{
    private readonly TestDatabase _db = new();

    public void Dispose() => _db.Dispose();

    [Fact]
    public async Task First_duty_creates_the_astronaut_detail()
    {
        await _db.AddPerson("Jane Roe");

        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        using var context = _db.NewContext();
        var detail = await context.AstronautDetails.SingleAsync();
        Assert.Equal("1LT", detail.CurrentRank);
        Assert.Equal("Pilot", detail.CurrentDutyTitle);
        Assert.Equal(new DateTime(2024, 1, 15), detail.CareerStartDate);
        Assert.Null(detail.CareerEndDate);
    }

    // Rule 4: the current duty has no end date.
    [Fact]
    public async Task The_newest_duty_has_no_end_date()
    {
        await _db.AddPerson("Jane Roe");

        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        using var context = _db.NewContext();
        Assert.Null((await context.AstronautDuties.SingleAsync()).DutyEndDate);
    }

    // Rule 5: the previous duty ends the day before the new one starts.
    [Fact]
    public async Task A_second_duty_closes_the_first_one_the_day_before()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await _db.AddDuty("Jane Roe", "CPT", "Commander", new DateTime(2024, 6, 1));

        using var context = _db.NewContext();
        var duties = await context.AstronautDuties.OrderBy(d => d.DutyStartDate).ToListAsync();
        Assert.Equal(2, duties.Count);
        Assert.Equal(new DateTime(2024, 5, 31), duties[0].DutyEndDate);
        Assert.Null(duties[1].DutyEndDate);

        var detail = await context.AstronautDetails.SingleAsync();
        Assert.Equal("CPT", detail.CurrentRank);
        Assert.Equal("Commander", detail.CurrentDutyTitle);
    }

    // Rule 7: the career end date is one day before the RETIRED duty starts.
    [Fact]
    public async Task Retiring_after_a_duty_ends_the_career_the_day_before()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await _db.AddDuty("Jane Roe", "1LT", "RETIRED", new DateTime(2025, 1, 1));

        using var context = _db.NewContext();
        var detail = await context.AstronautDetails.SingleAsync();
        Assert.Equal("RETIRED", detail.CurrentDutyTitle);
        Assert.Equal(new DateTime(2024, 1, 15), detail.CareerStartDate);
        Assert.Equal(new DateTime(2024, 12, 31), detail.CareerEndDate);
    }

    [Fact]
    public async Task A_duty_for_an_unknown_person_is_refused()
    {
        await Assert.ThrowsAsync<BadHttpRequestException>(
            () => _db.AddDuty("Nobody", "1LT", "Pilot", new DateTime(2024, 1, 15)));
    }
}
