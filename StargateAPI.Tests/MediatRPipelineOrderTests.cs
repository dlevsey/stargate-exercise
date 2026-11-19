using MediatR;
using MediatR.Pipeline;
using Microsoft.Extensions.DependencyInjection;

namespace StargateAPI.Tests;

// Where must a behaviour be registered to see an exception that a pre-processor throws?
// MediatR runs behaviours in the order they were registered, the first one outermost,
// and AddMediatR registers its own pre-processor behaviour before the ones added inside its lambda.
public class MediatRPipelineOrderTests
{
    public record Ping : IRequest<string>;

    public class PingHandler : IRequestHandler<Ping, string>
    {
        public Task<string> Handle(Ping request, CancellationToken cancellationToken) => Task.FromResult("pong");
    }

    public class RefusingPreProcessor : IRequestPreProcessor<Ping>
    {
        public Task Process(Ping request, CancellationToken cancellationToken) => throw new InvalidOperationException("refused by the pre-processor");
    }

    public class Seen
    {
        public List<string> Events { get; } = new();
    }

    public class RecordingBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse> where TRequest : notnull
    {
        private readonly Seen _seen;

        public RecordingBehavior(Seen seen) => _seen = seen;

        public async Task<TResponse> Handle(TRequest request, RequestHandlerDelegate<TResponse> next, CancellationToken cancellationToken)
        {
            _seen.Events.Add("entered");
            try
            {
                return await next();
            }
            catch (Exception ex)
            {
                _seen.Events.Add("saw: " + ex.Message);
                throw;
            }
        }
    }

    private static async Task<List<string>> SendPing(Action<IServiceCollection> beforeAddMediatR, Action<MediatRServiceConfiguration> insideAddMediatR)
    {
        var services = new ServiceCollection();
        services.AddSingleton<Seen>();
        beforeAddMediatR(services);
        services.AddMediatR(cfg =>
        {
            cfg.AddRequestPreProcessor<RefusingPreProcessor>();
            cfg.RegisterServicesFromAssemblyContaining<MediatRPipelineOrderTests>();
            insideAddMediatR(cfg);
        });

        using var provider = services.BuildServiceProvider();
        await Assert.ThrowsAsync<InvalidOperationException>(() => provider.GetRequiredService<IMediator>().Send(new Ping()));

        return provider.GetRequiredService<Seen>().Events;
    }

    [Fact]
    public async Task A_behaviour_added_inside_AddMediatR_never_sees_a_pre_processor_exception()
    {
        var events = await SendPing(_ => { }, cfg => cfg.AddOpenBehavior(typeof(RecordingBehavior<,>)));

        Assert.Empty(events);
    }

    [Fact]
    public async Task A_behaviour_registered_before_AddMediatR_sees_it()
    {
        var events = await SendPing(
            services => services.AddTransient(typeof(IPipelineBehavior<,>), typeof(RecordingBehavior<,>)),
            _ => { });

        Assert.Equal(new[] { "entered", "saw: refused by the pre-processor" }, events);
    }
}
