using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class VisitorType : TimestampedEntity
{
    public required string Code { get; set; }

    public required string Name { get; set; }

    public string? Description { get; set; }

    public bool IsActive { get; set; } = true;

    public ICollection<Visitor> Visitors { get; } = new List<Visitor>();
}
