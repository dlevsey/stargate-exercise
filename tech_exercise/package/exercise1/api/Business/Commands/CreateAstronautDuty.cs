using Dapper;
using MediatR;
using MediatR.Pipeline;
using Microsoft.EntityFrameworkCore;
using StargateAPI.Business.Data;
using StargateAPI.Controllers;
using System.Net;

namespace StargateAPI.Business.Commands
{
    public class CreateAstronautDuty : IRequest<CreateAstronautDutyResult>
    {
        public required string Name { get; set; }

        public required string Rank { get; set; }

        public required string DutyTitle { get; set; }

        public DateTime DutyStartDate { get; set; }
    }

    public class CreateAstronautDutyPreProcessor : IRequestPreProcessor<CreateAstronautDuty>
    {
        private readonly StargateContext _context;

        public CreateAstronautDutyPreProcessor(StargateContext context)
        {
            _context = context;
        }

        public async Task Process(CreateAstronautDuty request, CancellationToken cancellationToken)
        {
            if (string.IsNullOrWhiteSpace(request.Name)) throw new BadHttpRequestException("Name is required.");
            if (string.IsNullOrWhiteSpace(request.Rank)) throw new BadHttpRequestException("Rank is required.");
            if (string.IsNullOrWhiteSpace(request.DutyTitle)) throw new BadHttpRequestException("DutyTitle is required.");
            if (request.DutyStartDate == default) throw new BadHttpRequestException("DutyStartDate is required.");

            var person = await _context.People.AsNoTracking().FirstOrDefaultAsync(z => z.Name == request.Name, cancellationToken);

            if (person is null) throw new BadHttpRequestException("Person not found.", StatusCodes.Status404NotFound);

            var verifyNoPreviousDuty = await _context.AstronautDuties.FirstOrDefaultAsync(z => z.PersonId == person.Id && z.DutyTitle == request.DutyTitle && z.DutyStartDate == request.DutyStartDate.Date, cancellationToken);

            if (verifyNoPreviousDuty is not null) throw new BadHttpRequestException("This person already has this duty on this start date.", StatusCodes.Status409Conflict);

            var currentDuty = await _context.AstronautDuties.AsNoTracking().FirstOrDefaultAsync(z => z.PersonId == person.Id && z.DutyEndDate == null, cancellationToken);

            if (currentDuty is not null && request.DutyStartDate.Date <= currentDuty.DutyStartDate) throw new BadHttpRequestException("A new duty must start after the current duty's start date.");
        }
    }

    public class CreateAstronautDutyHandler : IRequestHandler<CreateAstronautDuty, CreateAstronautDutyResult>
    {
        private readonly StargateContext _context;

        public CreateAstronautDutyHandler(StargateContext context)
        {
            _context = context;
        }
        public async Task<CreateAstronautDutyResult> Handle(CreateAstronautDuty request, CancellationToken cancellationToken)
        {
            var isRetired = string.Equals(request.DutyTitle, AstronautDuty.RetiredDutyTitle, StringComparison.OrdinalIgnoreCase);
            var dutyTitle = isRetired ? AstronautDuty.RetiredDutyTitle : request.DutyTitle;

            var query = "SELECT * FROM [Person] WHERE @Name = Name";

            var person = await _context.Connection.QueryFirstOrDefaultAsync<Person>(query, new { request.Name });

            if (person is null) throw new BadHttpRequestException("Person not found.", StatusCodes.Status404NotFound);

            query = "SELECT * FROM [AstronautDetail] WHERE @PersonId = PersonId";

            var astronautDetail = await _context.Connection.QueryFirstOrDefaultAsync<AstronautDetail>(query, new { PersonId = person.Id });

            if (astronautDetail == null)
            {
                astronautDetail = new AstronautDetail();
                astronautDetail.PersonId = person.Id;
                astronautDetail.CurrentDutyTitle = dutyTitle;
                astronautDetail.CurrentRank = request.Rank;
                astronautDetail.CareerStartDate = request.DutyStartDate.Date;
                if (isRetired)
                {
                    astronautDetail.CareerEndDate = request.DutyStartDate.AddDays(-1).Date;
                }

                await _context.AstronautDetails.AddAsync(astronautDetail, cancellationToken);

            }
            else
            {
                astronautDetail.CurrentDutyTitle = dutyTitle;
                astronautDetail.CurrentRank = request.Rank;
                astronautDetail.CareerEndDate = isRetired ? request.DutyStartDate.AddDays(-1).Date : null;
                _context.AstronautDetails.Update(astronautDetail);
            }

            query = "SELECT * FROM [AstronautDuty] WHERE @PersonId = PersonId AND DutyEndDate IS NULL Order By DutyStartDate Desc";

            var astronautDuty = await _context.Connection.QueryFirstOrDefaultAsync<AstronautDuty>(query, new { PersonId = person.Id });

            if (astronautDuty != null)
            {
                astronautDuty.DutyEndDate = request.DutyStartDate.AddDays(-1).Date;
                _context.AstronautDuties.Update(astronautDuty);
            }

            var newAstronautDuty = new AstronautDuty()
            {
                PersonId = person.Id,
                Rank = request.Rank,
                DutyTitle = dutyTitle,
                DutyStartDate = request.DutyStartDate.Date,
                DutyEndDate = null
            };

            await _context.AstronautDuties.AddAsync(newAstronautDuty, cancellationToken);

            await _context.SaveChangesAsync(cancellationToken);

            return new CreateAstronautDutyResult()
            {
                Id = newAstronautDuty.Id
            };
        }
    }

    public class CreateAstronautDutyResult : BaseResponse
    {
        public int? Id { get; set; }
    }
}
