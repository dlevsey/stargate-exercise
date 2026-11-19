using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using StargateAPI.Business.Data;

namespace StargateAPI.Tests;

// Starts the real application (Program.cs) in memory, with an in-memory SQLite database in place of starbase.db.
public class ApiFactory : WebApplicationFactory<Program>
{
    private readonly SqliteConnection _connection = new("Data Source=:memory:");
    private readonly bool _createDatabase;

    // createDatabase: false leaves the database without tables, so that every query fails.
    public ApiFactory(bool createDatabase = true) => _createDatabase = createDatabase;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        _connection.Open();

        builder.ConfigureServices(services =>
        {
            var fileDatabase = services.Single(d => d.ServiceType == typeof(DbContextOptions<StargateContext>));
            services.Remove(fileDatabase);
            services.AddDbContext<StargateContext>(options => options.UseSqlite(_connection));
        });
    }

    protected override IHost CreateHost(IHostBuilder builder)
    {
        var host = base.CreateHost(builder);

        if (_createDatabase)
        {
            using var scope = host.Services.CreateScope();
            scope.ServiceProvider.GetRequiredService<StargateContext>().Database.Migrate();
        }

        return host;
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        _connection.Dispose();
    }
}
