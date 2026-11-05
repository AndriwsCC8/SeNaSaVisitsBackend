using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.Interfaces;

public interface ICatalogReader
{
    Task<IReadOnlyList<Branch>> ListBranchesAsync(long? branchId, bool includeInactive, CancellationToken cancellationToken);
    Task<IReadOnlyList<BranchType>> ListBranchTypesAsync(bool includeInactive, CancellationToken cancellationToken);
    Task<IReadOnlyList<VisitorType>> ListVisitorTypesAsync(bool includeInactive, CancellationToken cancellationToken);
    Task<IReadOnlyList<VisitReason>> ListVisitReasonsAsync(bool includeInactive, CancellationToken cancellationToken);
    Task<IReadOnlyList<Role>> ListRolesAsync(bool includeInactive, CancellationToken cancellationToken);
}

public sealed record DashboardAggregate(
    int TotalVisits, int ActiveVisits, int CompletedVisits, int CancelledVisits, int UniqueVisitors);
public sealed record DashboardDay(DateOnly Date, int Total);
public sealed record DistributionItem(string Code, string Label, int Total);

public interface IDashboardReader
{
    /// <summary>Must aggregate in the data source; day grouping is by UTC date, matching the current SQL Server behavior.</summary>
    Task<DashboardAggregate> GetSummaryAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken);
    Task<IReadOnlyList<DashboardDay>> GetVisitsByDayAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken);
    Task<IReadOnlyList<DistributionItem>> GetVisitsByStatusAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken);
    Task<IReadOnlyList<DistributionItem>> GetVisitsByReasonAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken);
}

public sealed record VisitReportSearch(
    string? Status, long? ReasonId, long? VisitorId, long? RegisteredByUserId,
    long? BranchId, DateTime? DateFromUtc, DateTime? DateToUtc, string? Search);
public sealed record VisitReportRow(
    long Id, DateTime EntryAt, DateTime? ExitAt, string Status, string? Destination,
    string? VisitedPerson, string? Notes, long VisitorId, string? VisitorIdentification,
    string VisitorFirstName, string VisitorLastName, string? VisitorCompany,
    long BranchId, string BranchCode, string BranchName, long ReasonId, string ReasonCode,
    string ReasonName, long RegisteredById, string Username, string RegisteredFirstName,
    string RegisteredLastName, long? CompletedByUserId, long? CancelledByUserId,
    DateTime? CancelledAt, string? CancellationReason);

public interface IVisitReportReader
{
    /// <summary>Returns the current SQL-first report projection without phone/email, ordered EntryAt DESC then Id DESC.</summary>
    Task<(IReadOnlyList<VisitReportRow> Items, int Total)> SearchAsync(
        VisitReportSearch filters, long? scopedBranchId, int page, int pageSize, CancellationToken cancellationToken);

    /// <summary>Group keys are status, reason, registered_by, or branch; preserve current data-source ordering (not guaranteed).</summary>
    Task<IReadOnlyList<DistributionItem>> GroupAsync(
        VisitReportSearch filters, long? scopedBranchId, string groupBy, CancellationToken cancellationToken);

    Task<bool> BranchExistsAndIsActiveAsync(long branchId, CancellationToken cancellationToken);

    Task<bool> ReasonExistsAsync(long reasonId, CancellationToken cancellationToken);

    Task<bool> VisitorExistsAsync(long visitorId, CancellationToken cancellationToken);

    Task<bool> UserExistsAsync(long userId, CancellationToken cancellationToken);
}
