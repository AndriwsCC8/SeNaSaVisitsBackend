using System.Reflection;

namespace SeNaSaVisits.UnitTests;

public sealed class DomainAssemblyTests
{
    [Fact]
    public void DomainAssembly_CanBeLoaded()
    {
        var assembly = Assembly.Load("SeNaSaVisits.Domain");

        Assert.Equal("SeNaSaVisits.Domain", assembly.GetName().Name);
    }
}
