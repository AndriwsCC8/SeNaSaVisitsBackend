using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class VisitReason : TimestampedEntity
{
    public required string Code { get; set; }

    public required string Name { get; set; }

    public string? Description { get; set; }

    public bool IsActive { get; set; } = true;

    public ICollection<Visit> Visits { get; } = new List<Visit>();
}
