using Microsoft.AspNetCore.Diagnostics;
using System.Net;

namespace StargateAPI.Controllers
{
    // The one place where an exception becomes an HTTP response.
    public class ApiExceptionHandler : IExceptionHandler
    {
        public async ValueTask<bool> TryHandleAsync(HttpContext httpContext, Exception exception, CancellationToken cancellationToken)
        {
            // Anything unexpected: a 500 and a message that gives nothing away.
            var response = new BaseResponse()
            {
                Success = false,
                Message = "An unexpected error occurred.",
                ResponseCode = (int)HttpStatusCode.InternalServerError
            };

            // A request the business rules refuse: its own message and status code.
            if (exception is BadHttpRequestException badRequest)
            {
                response.Message = badRequest.Message;
                response.ResponseCode = badRequest.StatusCode;
            }

            httpContext.Response.StatusCode = response.ResponseCode;
            await httpContext.Response.WriteAsJsonAsync(response, cancellationToken);

            return true;
        }
    }
}
