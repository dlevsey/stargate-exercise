using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Data;

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

    // Rule 3: a person has one current duty, so a new duty cannot start on or before the current one.
    [Fact]
    public async Task A_back_dated_duty_is_refused()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await Assert.ThrowsAsync<BadHttpRequestException>(
            () => _db.AddDuty("Jane Roe", "2LT", "Trainee", new DateTime(2023, 6, 1)));

        using var context = _db.NewContext();
        var duty = await context.AstronautDuties.SingleAsync();
        Assert.Equal("Pilot", duty.DutyTitle);
        Assert.Null(duty.DutyEndDate);
    }

    [Fact]
    public async Task A_duty_starting_on_the_same_day_as_the_current_one_is_refused()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await Assert.ThrowsAsync<BadHttpRequestException>(
            () => _db.AddDuty("Jane Roe", "CPT", "Commander", new DateTime(2024, 1, 15, 9, 30, 0)));
    }

    [Fact]
    public async Task The_same_duty_twice_is_refused()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await Assert.ThrowsAsync<BadHttpRequestException>(
            () => _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15)));
    }

    // The duplicate check belongs to one person: two people can start the same duty on the same day.
    [Fact]
    public async Task Two_people_can_start_the_same_duty_on_the_same_day()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddPerson("Sam Poe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await _db.AddDuty("Sam Poe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        using var context = _db.NewContext();
        Assert.Equal(2, await context.AstronautDuties.CountAsync());
    }

    // Rules 3 and 4 together: after any number of duties a person has exactly one duty without an end date.
    [Fact]
    public async Task Each_person_has_exactly_one_open_duty()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "2LT", "Trainee", new DateTime(2023, 1, 1));
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));
        await _db.AddDuty("Jane Roe", "CPT", "Commander", new DateTime(2024, 6, 1));

        using var context = _db.NewContext();
        var open = await context.AstronautDuties.Where(d => d.DutyEndDate == null).ToListAsync();
        Assert.Equal("Commander", Assert.Single(open).DutyTitle);
        var closed = await context.AstronautDuties.Where(d => d.DutyEndDate != null).OrderBy(d => d.DutyStartDate).ToListAsync();
        Assert.Equal(new[] { new DateTime(2024, 1, 14), new DateTime(2024, 5, 31) }, closed.Select(d => d.DutyEndDate!.Value));
    }

    // Rule 6: a person is 'Retired' when the duty title is 'RETIRED', however the word is typed.
    [Fact]
    public async Task Retired_in_lower_case_counts_as_retired()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));

        await _db.AddDuty("Jane Roe", "1LT", "retired", new DateTime(2025, 1, 1));

        using var context = _db.NewContext();
        var detail = await context.AstronautDetails.SingleAsync();
        Assert.Equal("RETIRED", detail.CurrentDutyTitle);
        Assert.Equal(new DateTime(2024, 12, 31), detail.CareerEndDate);
        Assert.Equal("RETIRED", (await context.AstronautDuties.SingleAsync(d => d.DutyEndDate == null)).DutyTitle);
    }

    // A retired person who takes a new duty is active again, so the career end date is cleared.
    [Fact]
    public async Task A_duty_after_retirement_clears_the_career_end_date()
    {
        await _db.AddPerson("Jane Roe");
        await _db.AddDuty("Jane Roe", "1LT", "Pilot", new DateTime(2024, 1, 15));
        await _db.AddDuty("Jane Roe", "1LT", "RETIRED", new DateTime(2025, 1, 1));

        await _db.AddDuty("Jane Roe", "CPT", "Commander", new DateTime(2026, 1, 1));

        using var context = _db.NewContext();
        var detail = await context.AstronautDetails.SingleAsync();
        Assert.Equal("Commander", detail.CurrentDutyTitle);
        Assert.Null(detail.CareerEndDate);
    }

    // Rule 7 when RETIRED is the very first duty. The career then ends the day before it starts.
    [Fact]
    public async Task Retiring_as_the_first_duty_ends_the_career_the_day_before()
    {
        await _db.AddPerson("Jane Roe");

        await _db.AddDuty("Jane Roe", "1LT", "RETIRED", new DateTime(2025, 1, 1));

        using var context = _db.NewContext();
        var detail = await context.AstronautDetails.SingleAsync();
        Assert.Equal(new DateTime(2025, 1, 1), detail.CareerStartDate);
        Assert.Equal(new DateTime(2024, 12, 31), detail.CareerEndDate);
    }

    // Rule 5 on data the old code left behind: a back-dated duty that was accepted, so the open duty is not the newest one.
    [Fact]
    public async Task The_duty_that_gets_closed_is_the_open_one()
    {
        var person = await _db.AddPerson("Jane Roe");
        using (var seed = _db.NewContext())
        {
            seed.AstronautDetails.Add(new AstronautDetail { PersonId = person.Id, CurrentRank = "2LT", CurrentDutyTitle = "Trainee", CareerStartDate = new DateTime(2024, 1, 15) });
            seed.AstronautDuties.Add(new AstronautDuty { PersonId = person.Id, Rank = "1LT", DutyTitle = "Pilot", DutyStartDate = new DateTime(2024, 1, 15), DutyEndDate = new DateTime(2023, 5, 31) });
            seed.AstronautDuties.Add(new AstronautDuty { PersonId = person.Id, Rank = "2LT", DutyTitle = "Trainee", DutyStartDate = new DateTime(2023, 6, 1), DutyEndDate = null });
            await seed.SaveChangesAsync();
        }

        await _db.AddDuty("Jane Roe", "CPT", "Commander", new DateTime(2025, 1, 1));

        using var context = _db.NewContext();
        var open = await context.AstronautDuties.Where(d => d.DutyEndDate == null).ToListAsync();
        Assert.Equal("Commander", Assert.Single(open).DutyTitle);
        var trainee = await context.AstronautDuties.SingleAsync(d => d.DutyTitle == "Trainee");
        Assert.Equal(new DateTime(2024, 12, 31), trainee.DutyEndDate);
    }
}
