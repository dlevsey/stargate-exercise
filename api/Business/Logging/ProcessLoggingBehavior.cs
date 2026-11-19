using MediatR;
using StargateAPI.Business.Data;

namespace StargateAPI.Business.Logging
{
    // Runs around every MediatR request and writes one ProcessLog row: one when it succeeds, one when it throws.
    public class ProcessLoggingBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse> where TRequest : notnull
    {
        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<ProcessLoggingBehavior<TRequest, TResponse>> _logger;

        public ProcessLoggingBehavior(IServiceScopeFactory scopeFactory, ILogger<ProcessLoggingBehavior<TRequest, TResponse>> logger)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
        }

        public async Task<TResponse> Handle(TRequest request, RequestHandlerDelegate<TResponse> next, CancellationToken cancellationToken)
        {
            var process = typeof(TRequest).Name;

            try
            {
                var response = await next();

                await WriteLog("Information", process, "Successful", null);

                return response;
            }
            catch (Exception ex)
            {
                await WriteLog("Error", process, ex.Message, ex.ToString());

                throw;
            }
        }

        private async Task WriteLog(string level, string process, string message, string? exception)
        {
            try
            {
                // Its own scope, and so its own StargateContext: the row is saved even when the request's work is not.
                using var scope = _scopeFactory.CreateScope();
                var context = scope.ServiceProvider.GetRequiredService<StargateContext>();

                context.ProcessLogs.Add(new ProcessLog()
                {
                    CreatedDate = DateTime.UtcNow,
                    Level = level,
                    Process = process,
                    Message = message,
                    Exception = exception
                });

                await context.SaveChangesAsync();
            }
            catch (Exception ex)
            {
                // A failure to log must never break the request.
                _logger.LogError(ex, "Could not write the process log for {Process}", process);
            }
        }
    }
}
