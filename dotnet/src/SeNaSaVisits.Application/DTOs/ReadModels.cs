using SeNaSaVisits.Application.Common;

namespace SeNaSaVisits.Application.DTOs;

public sealed record CatalogItemDto(long Id, string Code, string Name, long? BranchTypeId = null, bool? IsActive = null);
public sealed record DashboardScopeDto(long? BranchId, bool IsGlobal)
{
    public string Scope => IsGlobal ? "global" : "branch";
}
public sealed record DashboardSummaryDto(string Scope, long? BranchId, DateTime? DateFrom, DateTime? DateTo,
    int TotalVisits, int ActiveVisits, int CompletedVisits, int CancelledVisits, int UniqueVisitors);
public sealed record DashboardSeriesDto(string Scope, long? BranchId, IReadOnlyList<DashboardDayDto> Items);
public sealed record DashboardDistributionDto(string Scope, long? BranchId, IReadOnlyList<DistributionDto> Items);
public sealed record DashboardDayDto(DateOnly Date, int Total);
public sealed record DistributionDto(string Code, string Label, int Total);
public enum VisitReportGroupBy { Status, Reason, RegisteredBy, Branch }
public sealed record VisitReportFilters(string? Status = null, long? ReasonId = null, long? VisitorId = null,
    long? RegisteredByUserId = null, long? BranchId = null, DateTime? DateFrom = null,
    DateTime? DateTo = null, string? Search = null);
public sealed record VisitReportItem(long Id, DateTime EntryAt, DateTime? ExitAt, string Status,
    string? Destination, string? VisitedPerson, string? Notes, VisitVisitorDto Visitor,
    VisitBranchDto Branch, VisitReasonDto Reason, VisitUserDto RegisteredBy,
    long? CompletedByUserId, long? CancelledByUserId, DateTime? CancelledAt, string? CancellationReason);
public sealed record VisitReportResponse(IReadOnlyList<VisitReportItem> Items, int Total, int Page, int PageSize, int TotalPages);
public sealed record VisitReportSummaryResponse(string GroupBy, IReadOnlyList<DistributionDto> Items);

public sealed record ScopedDateRequest(DateTime? DateFrom = null, DateTime? DateTo = null);
public sealed record ListRequest(PageRequest Page);
