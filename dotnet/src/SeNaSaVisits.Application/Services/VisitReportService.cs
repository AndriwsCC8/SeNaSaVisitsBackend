using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;

namespace SeNaSaVisits.Application.Services;

public sealed class VisitReportService(
    IVisitReportReader reports,
    IPermissionEvaluator permissions,
    BranchAccessService branchAccess,
    ICurrentUser currentUser)
{
    public async Task<VisitReportResponse> SearchAsync(VisitReportFilters request, PageRequest page, CancellationToken cancellationToken)
    {
        page.Validate();
        var scope = await ResolveScope(request.BranchId, cancellationToken).ConfigureAwait(false);
        var filters = await NormalizeAndValidateAsync(request, cancellationToken).ConfigureAwait(false);
        var result = await reports.SearchAsync(filters, scope.BranchId, page.Page, page.PageSize, cancellationToken).ConfigureAwait(false);
        var items = result.Items.Select(ToDto).ToArray();
        return new VisitReportResponse(items, result.Total, page.Page, page.PageSize,
            result.Total == 0 ? 0 : (int)Math.Ceiling(result.Total / (double)page.PageSize));
    }

    public async Task<VisitReportSummaryResponse> SummaryAsync(VisitReportFilters request, VisitReportGroupBy groupBy, CancellationToken cancellationToken)
    {
        var scope = await ResolveScope(request.BranchId, cancellationToken).ConfigureAwait(false);
        if (groupBy == VisitReportGroupBy.Branch && !scope.IsGlobal)
            throw new ApplicationValidationException("Grouping by branch requires global report access.");
        var filters = await NormalizeAndValidateAsync(request, cancellationToken).ConfigureAwait(false);
        var groupCode = groupBy switch
        {
            VisitReportGroupBy.Status => "status",
            VisitReportGroupBy.Reason => "reason",
            VisitReportGroupBy.RegisteredBy => "registered_by",
            VisitReportGroupBy.Branch => "branch",
            _ => throw new ApplicationValidationException("The report grouping is invalid.")
        };
        var result = await reports.GroupAsync(filters, scope.BranchId, groupCode, cancellationToken).ConfigureAwait(false);
        return new VisitReportSummaryResponse(groupCode,
            result.Select(item => new DistributionDto(item.Code, item.Label, item.Total)).ToArray());
    }

    private async Task<(long? BranchId, bool IsGlobal)> ResolveScope(long? requestedBranch, CancellationToken cancellationToken)
    {
        if (await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_GLOBAL_REPORTS", null, cancellationToken).ConfigureAwait(false))
        {
            if (requestedBranch is not null && !await reports.BranchExistsAndIsActiveAsync(requestedBranch.Value, cancellationToken).ConfigureAwait(false))
                throw new ApplicationNotFoundException("The requested branch does not exist or is inactive.");
            return (null, true);
        }

        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_REPORTS", context.BranchId, cancellationToken).ConfigureAwait(false);
        if (requestedBranch is not null && requestedBranch != context.BranchId)
            throw new ApplicationForbiddenException("The requested branch is outside the authorized scope.");
        return (context.BranchId, false);
    }

    private async Task<VisitReportSearch> NormalizeAndValidateAsync(VisitReportFilters request, CancellationToken cancellationToken)
    {
        if (request.Search?.Length > 100) throw new ApplicationValidationException("search exceeds its maximum length.");
        DateTime? from = request.DateFrom is null ? null : ApplicationTime.ToUtc(request.DateFrom.Value);
        DateTime? to = request.DateTo is null ? null : ApplicationTime.ToUtc(request.DateTo.Value);
        if (from is not null && to is not null && from >= to)
            throw new ApplicationValidationException("date_to must be later than date_from; the upper bound is exclusive.");
        if (request.Status is not null && request.Status is not ("ACTIVE" or "COMPLETED" or "CANCELLED"))
            throw new ApplicationValidationException("The visit status is invalid.");
        if (request.ReasonId is not null && !await reports.ReasonExistsAsync(request.ReasonId.Value, cancellationToken).ConfigureAwait(false))
            throw new ApplicationNotFoundException("The requested visit reason does not exist.");
        if (request.VisitorId is not null && !await reports.VisitorExistsAsync(request.VisitorId.Value, cancellationToken).ConfigureAwait(false))
            throw new ApplicationNotFoundException("The requested visitor does not exist.");
        if (request.RegisteredByUserId is not null && !await reports.UserExistsAsync(request.RegisteredByUserId.Value, cancellationToken).ConfigureAwait(false))
            throw new ApplicationNotFoundException("The requested user does not exist.");
        return BuildSearch(request, from, to);
    }

    private static VisitReportSearch BuildSearch(VisitReportFilters request, DateTime? from, DateTime? to)
    {
        return new VisitReportSearch(request.Status, request.ReasonId, request.VisitorId,
            request.RegisteredByUserId, request.BranchId, from, to, request.Search);
    }

    private static VisitReportItem ToDto(VisitReportRow row) => new(row.Id, row.EntryAt, row.ExitAt, row.Status,
        row.Destination, row.VisitedPerson, row.Notes,
        new VisitVisitorDto(row.VisitorId, MaskIdentification(row.VisitorIdentification), row.VisitorFirstName, row.VisitorLastName, row.VisitorCompany),
        new VisitBranchDto(row.BranchId, row.BranchCode, row.BranchName),
        new VisitReasonDto(row.ReasonId, row.ReasonCode, row.ReasonName),
        new VisitUserDto(row.RegisteredById, row.Username, row.RegisteredFirstName, row.RegisteredLastName),
        row.CompletedByUserId, row.CancelledByUserId, row.CancelledAt, row.CancellationReason);

    private static string? MaskIdentification(string? value)
    {
        if (string.IsNullOrEmpty(value)) return null;
        return value.Length > 7 ? value[..3] + "***" + value[^4..] : "***";
    }
}
