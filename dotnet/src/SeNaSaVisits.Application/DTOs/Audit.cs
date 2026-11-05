using SeNaSaVisits.Application.Common;

namespace SeNaSaVisits.Application.DTOs;

public sealed record AuditDto(long Id, long? ActorUserId, string Action, string EntityType,
    long? EntityId, long? BranchId, string? OldValues, string? NewValues,
    string? IpAddress, string? UserAgent, string? CorrelationId, DateTime CreatedAt);
public sealed record AuditSearchRequest
{
    public PageRequest Page { get; init; } = new(1, 50);
    public long? ActorUserId { get; init; }
    public string? Action { get; init; }
    public string? EntityType { get; init; }
    public long? EntityId { get; init; }
    public long? BranchId { get; init; }
    public DateTime? DateFrom { get; init; }
    public DateTime? DateTo { get; init; }
}
