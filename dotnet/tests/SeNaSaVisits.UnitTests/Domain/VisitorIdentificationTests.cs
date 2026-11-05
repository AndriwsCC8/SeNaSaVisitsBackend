using SeNaSaVisits.Domain.ValueObjects;
using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.UnitTests.Domain;

public sealed class VisitorIdentificationTests
{
    [Fact]
    public void From_RemovesWhitespaceAndUppercases_WhilePreservingPunctuation()
    {
        var identification = VisitorIdentification.From("  ab 12- c  ");

        Assert.NotNull(identification);
        Assert.Equal("ab 12- c", identification.RawValue);
        Assert.Equal("AB12-C", identification.NormalizedValue);
    }

    [Fact]
    public void From_NullReturnsNull()
    {
        Assert.Null(VisitorIdentification.From(null));
    }

    [Fact]
    public void From_WhitespaceOnlyPreservesEmptyRawValueAndHasNoNormalizedValue()
    {
        var identification = VisitorIdentification.From(" \t ");

        Assert.NotNull(identification);
        Assert.Equal(string.Empty, identification.RawValue);
        Assert.Null(identification.NormalizedValue);
    }

    [Fact]
    public void Visitor_ExposesNormalizedIdentificationFromValueObject()
    {
        var visitor = new Visitor
        {
            FirstName = "Ana",
            LastName = "Ejemplo",
            Identification = VisitorIdentification.From("  ab 12- c  ")
        };

        Assert.Equal("AB12-C", visitor.IdentificationNormalized);
    }
}
