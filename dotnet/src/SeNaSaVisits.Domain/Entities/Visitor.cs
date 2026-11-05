using SeNaSaVisits.Domain.Common;
using SeNaSaVisits.Domain.ValueObjects;

namespace SeNaSaVisits.Domain.Entities;

public sealed class Visitor : TimestampedEntity
{
    /// <summary>Maps to the identification and identification_normalized columns.</summary>
    public VisitorIdentification? Identification { get; set; }

    public string? IdentificationNormalized => Identification?.NormalizedValue;

    public required string FirstName { get; set; }

    public required string LastName { get; set; }

    public string? Phone { get; set; }

    public string? Email { get; set; }

    public string? Company { get; set; }

    public long? VisitorTypeId { get; set; }

    public bool IsActive { get; set; } = true;

    public VisitorType? VisitorType { get; set; }

    public ICollection<Visit> Visits { get; } = new List<Visit>();
}
