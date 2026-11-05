using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;

namespace SeNaSaVisits.Application.Services;

public sealed class DashboardService(
    IDashboardReader dashboard,
    IPermissionEvaluator permissions,
    BranchAccessService branchAccess,
    ICurrentUser currentUser)
{
    public async Task<DashboardSummaryDto> SummaryAsync(ScopedDateRequest request, CancellationToken cancellationToken)
    {
        var scope = await ResolveScope(cancellationToken).ConfigureAwait(false);
        var (from, to) = NormalizeRange(request.DateFrom, request.DateTo);
        var result = await dashboard.GetSummaryAsync(scope.BranchId, from, to, cancellationToken).ConfigureAwait(false);
        return new DashboardSummaryDto(scope.Scope, scope.BranchId, ResponseTime(request.DateFrom), ResponseTime(request.DateTo),
            result.TotalVisits, result.ActiveVisits, result.CompletedVisits, result.CancelledVisits, result.UniqueVisitors);
    }

    public async Task<DashboardSeriesDto> VisitsByDayAsync(ScopedDateRequest request, CancellationToken cancellationToken)
    {
        var scope = await ResolveScope(cancellationToken).ConfigureAwait(false);
        var (from, to) = NormalizeRange(request.DateFrom, request.DateTo);
        var result = await dashboard.GetVisitsByDayAsync(scope.BranchId, from, to, cancellationToken).ConfigureAwait(false);
        return new DashboardSeriesDto(scope.Scope, scope.BranchId, result.Select(item => new DashboardDayDto(item.Date, item.Total)).ToArray());
    }

    public async Task<DashboardDistributionDto> VisitsByStatusAsync(ScopedDateRequest request, CancellationToken cancellationToken)
    {
        var scope = await ResolveScope(cancellationToken).ConfigureAwait(false);
        var (from, to) = NormalizeRange(request.DateFrom, request.DateTo);
        var result = await dashboard.GetVisitsByStatusAsync(scope.BranchId, from, to, cancellationToken).ConfigureAwait(false);
        return new DashboardDistributionDto(scope.Scope, scope.BranchId, result.Select(item => new DistributionDto(item.Code, item.Label, item.Total)).ToArray());
    }

    public async Task<DashboardDistributionDto> VisitsByReasonAsync(ScopedDateRequest request, CancellationToken cancellationToken)
    {
        var scope = await ResolveScope(cancellationToken).ConfigureAwait(false);
        var (from, to) = NormalizeRange(request.DateFrom, request.DateTo);
        var result = await dashboard.GetVisitsByReasonAsync(scope.BranchId, from, to, cancellationToken).ConfigureAwait(false);
        return new DashboardDistributionDto(scope.Scope, scope.BranchId, result.Select(item => new DistributionDto(item.Code, item.Label, item.Total)).ToArray());
    }

    private async Task<DashboardScopeDto> ResolveScope(CancellationToken cancellationToken)
    {
        if (await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_GLOBAL_REPORTS", null, cancellationToken).ConfigureAwait(false))
            return new DashboardScopeDto(null, true);
        var branch = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_REPORTS", branch.BranchId, cancellationToken).ConfigureAwait(false);
        return new DashboardScopeDto(branch.BranchId, false);
    }

    private static (DateTime? From, DateTime? To) NormalizeRange(DateTime? from, DateTime? to)
    {
        DateTime? normalizedFrom = from is null ? null : ApplicationTime.ToUtc(from.Value);
        DateTime? normalizedTo = to is null ? null : ApplicationTime.ToUtc(to.Value);
        if (normalizedFrom is not null && normalizedTo is not null && normalizedFrom >= normalizedTo)
            throw new ApplicationValidationException("date_to must be later than date_from; the upper bound is exclusive.");
        return (normalizedFrom, normalizedTo);
    }

    private static DateTime? ResponseTime(DateTime? value) => value is null ? null : ApplicationTime.ToUtc(value.Value);
}
