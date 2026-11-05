using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

/// <summary>Represents an audit record. The current application writes audit records append-only.</summary>
public sealed class AuditLog : Entity
{
    public long? ActorUserId { get; init; }

    public required string Action { get; init; }

    public required string EntityType { get; init; }

    public long? EntityId { get; init; }

    public long? BranchId { get; init; }

    public string? OldValues { get; init; }

    public string? NewValues { get; init; }

    public string? IpAddress { get; init; }

    public string? UserAgent { get; init; }

    public string? CorrelationId { get; init; }

    public DateTime CreatedAt { get; init; }

    public User? Actor { get; init; }

    public Branch? Branch { get; init; }
}
