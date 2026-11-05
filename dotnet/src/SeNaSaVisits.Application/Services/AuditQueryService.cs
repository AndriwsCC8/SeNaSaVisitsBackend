using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;

namespace SeNaSaVisits.Application.Services;

/// <summary>Global, paginated, read-only audit query use case.</summary>
public sealed class AuditQueryService(
    IAuditReader reader,
    IPermissionEvaluator permissions,
    ICurrentUser currentUser)
{
    public async Task<PageResult<AuditDto>> SearchAsync(AuditSearchRequest request, CancellationToken cancellationToken)
    {
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_AUDIT_LOGS", null, cancellationToken).ConfigureAwait(false);
        request.Page.Validate();
        if (request.Page.PageSize > 100) throw new ApplicationValidationException("page_size must not exceed 100.");
        if (request.Action?.Length > 60) throw new ApplicationValidationException("action exceeds its maximum length.");
        if (request.EntityType?.Length > 80) throw new ApplicationValidationException("entity_type exceeds its maximum length.");
        DateTime? from = request.DateFrom is null ? null : ApplicationTime.ToUtc(request.DateFrom.Value);
        DateTime? to = request.DateTo is null ? null : ApplicationTime.ToUtc(request.DateTo.Value);
        if (from is not null && to is not null && from >= to)
            throw new ApplicationValidationException("date_to must be later than date_from; the upper bound is exclusive.");

        var result = await reader.SearchAsync(new AuditSearchCriteria(request.ActorUserId, request.Action,
            request.EntityType, request.EntityId, request.BranchId, from, to),
            request.Page.Page, request.Page.PageSize, cancellationToken).ConfigureAwait(false);
        var items = result.Items.Select(log => new AuditDto(log.Id, log.ActorUserId, log.Action, log.EntityType,
            log.EntityId, log.BranchId, AuditService.RedactSerialized(log.OldValues),
            AuditService.RedactSerialized(log.NewValues), log.IpAddress, log.UserAgent,
            log.CorrelationId, log.CreatedAt)).ToArray();
        return new PageResult<AuditDto>(items, result.Total, request.Page.Page, request.Page.PageSize);
    }
}
