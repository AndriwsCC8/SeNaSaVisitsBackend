using SeNaSaVisits.Application.Services;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class AuditRedactionTests
{
    [Fact]
    public void SerializeRedactsSensitiveKeysRecursivelyInObjectsAndLists()
    {
        var data = new Dictionary<string, object?>
        {
            ["username"] = "ana",
            ["password"] = "secret",
            ["nested"] = new Dictionary<string, object?> { ["Refresh-Token"] = "secret", ["ok"] = 1 },
            ["items"] = new object[] { new Dictionary<string, object?> { ["api_key"] = "secret", ["value"] = true } }
        };

        var serialized = AuditService.Serialize(data);

        Assert.NotNull(serialized);
        Assert.Contains("username", serialized);
        Assert.Contains("nested", serialized);
        Assert.DoesNotContain("secret", serialized);
        Assert.DoesNotContain("password", serialized);
        Assert.DoesNotContain("Refresh-Token", serialized);
        Assert.DoesNotContain("api_key", serialized);
    }

    [Fact]
    public void RedactSerializedReturnsNullForInvalidJsonAndRedactsPreviouslyStoredData()
    {
        Assert.Null(AuditService.RedactSerialized("not-json"));
        var result = AuditService.RedactSerialized("{\"Authorization\":\"secret\",\"keep\":1}");
        Assert.NotNull(result);
        Assert.DoesNotContain("secret", result);
        Assert.Contains("keep", result);
    }
}
