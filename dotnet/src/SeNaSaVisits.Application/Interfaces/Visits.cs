using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.Interfaces;

public sealed record VisitSearchCriteria(
    long BranchId, string? Status, long? VisitorId, long? ReasonId,
    DateTime? DateFromUtc, DateTime? DateToUtc, string? Search);

public interface IVisitRepository
{
    /// <summary>Must constrain the query by branchId in the data source; a foreign-branch row is returned as absent.</summary>
    Task<Visit?> GetInBranchAsync(long visitId, long branchId, CancellationToken cancellationToken);

    /// <summary>Applies branch and date/status/reference filters, trims search text, orders by EntryAt DESC then Id DESC, and loads response navigations.</summary>
    Task<(IReadOnlyList<Visit> Items, int Total)> SearchInBranchAsync(
        VisitSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken);

    Task AddAsync(Visit visit, CancellationToken cancellationToken);

    Task SaveChangesAsync(Visit visit, CancellationToken cancellationToken);
}

public interface IVisitReferenceReader
{
    Task<Visitor?> GetVisitorAsync(long visitorId, CancellationToken cancellationToken);

    Task<VisitReason?> GetReasonAsync(long reasonId, CancellationToken cancellationToken);

    Task<Branch?> GetBranchAsync(long branchId, CancellationToken cancellationToken);

    Task<User?> GetUserAsync(long userId, CancellationToken cancellationToken);
}
