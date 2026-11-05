using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.Interfaces;

public sealed record AuditContext(string? IpAddress = null, string? UserAgent = null, string? CorrelationId = null);

public sealed record AuditSearchCriteria(
    long? ActorUserId, string? Action, string? EntityType, long? EntityId,
    long? BranchId, DateTime? DateFromUtc, DateTime? DateToUtc);

public interface IAuditWriter
{
    /// <summary>Append a new event only; no update/delete operation is intentionally exposed.</summary>
    /// <param name="transaction">When provided, the insert must use the same connection/transaction scope.</param>
    Task AppendAsync(AuditLog auditLog, CancellationToken cancellationToken, IApplicationTransaction? transaction = null);
}

public interface IAuditReader
{
    /// <summary>Returns filtered rows ordered by CreatedAt DESC, then Id DESC; this is a global query port.</summary>
    Task<(IReadOnlyList<AuditLog> Items, int Total)> SearchAsync(
        AuditSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken);
}
