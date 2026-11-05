using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Validators;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.Services;

/// <summary>All visit reads/writes are scoped to the current branch resolved from trusted identity.</summary>
public sealed class VisitManagementService(
    IVisitRepository visits,
    IVisitReferenceReader references,
    ICurrentUser currentUser,
    IPermissionEvaluator permissions,
    BranchAccessService branchAccess,
    IClock clock,
    ITransactionRunner transactions,
    AuditService audit)
{
    public async Task<PageResult<VisitDto>> SearchAsync(VisitSearchRequest request, CancellationToken cancellationToken)
    {
        request.Page.Validate();
        InputValidators.MaxLength(request.Search, 100, "search");
        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_VISITS", context.BranchId, cancellationToken).ConfigureAwait(false);
        DateTime? from = request.DateFrom is null ? null : ApplicationTime.ToUtc(request.DateFrom.Value);
        DateTime? to = request.DateTo is null ? null : ApplicationTime.ToUtc(request.DateTo.Value);
        ValidateDateRange(from, to);
        if (request.Status is not null && request.Status is not ("ACTIVE" or "COMPLETED" or "CANCELLED"))
            throw new ApplicationValidationException("The visit status is invalid.");
        var result = await visits.SearchInBranchAsync(new VisitSearchCriteria(context.BranchId, request.Status,
            request.VisitorId, request.ReasonId, from, to, request.Search), request.Page.Page,
            request.Page.PageSize, cancellationToken).ConfigureAwait(false);
        return new PageResult<VisitDto>(result.Items.Select(VisitDtoMapper.ToDto).ToArray(), result.Total,
            request.Page.Page, request.Page.PageSize);
    }

    public async Task<VisitDto> GetAsync(long visitId, CancellationToken cancellationToken)
    {
        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_VISITS", context.BranchId, cancellationToken).ConfigureAwait(false);
        return VisitDtoMapper.ToDto(await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<VisitDto> CreateAsync(VisitCreateRequest request, AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "CREATE_VISIT", context.BranchId, cancellationToken).ConfigureAwait(false);
        var visitor = await references.GetVisitorAsync(request.VisitorId, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationNotFoundException("The requested visitor does not exist.");
        if (!visitor.IsActive) throw new ApplicationValidationException("The requested visitor is inactive.");
        var reason = await references.GetReasonAsync(request.ReasonId, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationNotFoundException("The requested visit reason does not exist.");
        if (!reason.IsActive) throw new ApplicationValidationException("The requested visit reason is inactive.");
        ValidateCreate(request);
        var now = Now();
        var visit = new Visit
        {
            VisitorId = request.VisitorId,
            Visitor = visitor,
            BranchId = context.BranchId,
            Branch = await ResolveBranch(context.BranchId, cancellationToken).ConfigureAwait(false),
            RegisteredByUserId = currentUser.UserId,
            RegisteredBy = await ResolveUser(currentUser.UserId, cancellationToken).ConfigureAwait(false),
            EntryAt = request.EntryAt is null ? now : ApplicationTime.ToUtc(request.EntryAt.Value),
            ReasonId = request.ReasonId,
            Reason = reason,
            Destination = NormalizeOptional(request.Destination),
            VisitedPerson = NormalizeOptional(request.VisitedPerson),
            Notes = NormalizeOptional(request.Notes),
            CreatedAt = now,
            UpdatedAt = now
        };
        visit.Validate();
        await transactions.ExecuteAsync(async ct =>
        {
            await visits.AddAsync(visit, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "CREATE_VISIT", "Visit", visit.Id, context.BranchId,
                newValues: new Dictionary<string, object?>
                {
                    ["visit_id"] = visit.Id, ["visitor_id"] = visit.VisitorId, ["branch_id"] = visit.BranchId,
                    ["reason_id"] = visit.ReasonId, ["entry_at"] = visit.EntryAt, ["destination"] = visit.Destination
                }, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        return VisitDtoMapper.ToDto(await GetVisit(visit.Id, context.BranchId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<VisitDto> UpdateAsync(long visitId, VisitUpdateRequest request,
        AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "UPDATE_VISIT", context.BranchId, cancellationToken).ConfigureAwait(false);
        var visit = await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false);
        if (visit.Status != VisitStatus.Active) throw new ApplicationConflictException("Only active visits can be modified.");
        var oldValues = new Dictionary<string, object?>();
        var newValues = new Dictionary<string, object?>();
        if (request.ReasonId.IsSpecified)
        {
            if (request.ReasonId.Value is null) throw new ApplicationValidationException("reason_id cannot be null.");
            var reason = await references.GetReasonAsync(request.ReasonId.Value.Value, cancellationToken).ConfigureAwait(false)
                ?? throw new ApplicationNotFoundException("The requested visit reason does not exist.");
            if (!reason.IsActive) throw new ApplicationValidationException("The requested visit reason is inactive.");
            oldValues["reason_id"] = visit.ReasonId;
            visit.ReasonId = reason.Id; visit.Reason = reason; newValues["reason_id"] = reason.Id;
        }
        ApplyTextUpdate(request.Destination, "destination", 200, value => visit.Destination = value, oldValues, newValues, visit.Destination);
        ApplyTextUpdate(request.VisitedPerson, "visited_person", 200, value => visit.VisitedPerson = value, oldValues, newValues, visit.VisitedPerson);
        ApplyTextUpdate(request.Notes, "notes", 1000, value => visit.Notes = value, oldValues, newValues, visit.Notes);
        visit.UpdatedAt = Now();
        await transactions.ExecuteAsync(async ct =>
        {
            await visits.SaveChangesAsync(visit, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "UPDATE_VISIT", "Visit", visit.Id, visit.BranchId,
                oldValues: oldValues, newValues: newValues, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        return VisitDtoMapper.ToDto(await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<VisitDto> CompleteAsync(long visitId, VisitCompleteRequest request,
        AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "UPDATE_VISIT", context.BranchId, cancellationToken).ConfigureAwait(false);
        var visit = await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false);
        if (visit.Status != VisitStatus.Active) throw new ApplicationConflictException("Only active visits can be completed.");
        var exitAt = request.ExitAt is null ? Now() : ApplicationTime.ToUtc(request.ExitAt.Value);
        visit.Complete(currentUser.UserId, exitAt);
        visit.CompletedBy = await ResolveUser(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        visit.UpdatedAt = Now();
        await transactions.ExecuteAsync(async ct =>
        {
            await visits.SaveChangesAsync(visit, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "CHECKOUT_VISIT", "Visit", visit.Id, visit.BranchId,
                oldValues: new Dictionary<string, object?> { ["status"] = "ACTIVE" },
                newValues: new Dictionary<string, object?> { ["status"] = "COMPLETED", ["exit_at"] = exitAt },
                context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        return VisitDtoMapper.ToDto(await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<VisitDto> CancelAsync(long visitId, VisitCancelRequest request,
        AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var context = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "UPDATE_VISIT", context.BranchId, cancellationToken).ConfigureAwait(false);
        InputValidators.StringLength(request.CancellationReason, "cancellation_reason", 1, 500);
        var visit = await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false);
        if (visit.Status != VisitStatus.Active) throw new ApplicationConflictException("Only active visits can be cancelled.");
        var now = Now();
        visit.Cancel(currentUser.UserId, now, request.CancellationReason);
        visit.CancelledBy = await ResolveUser(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        visit.UpdatedAt = now;
        await transactions.ExecuteAsync(async ct =>
        {
            await visits.SaveChangesAsync(visit, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "CANCEL_VISIT", "Visit", visit.Id, visit.BranchId,
                oldValues: new Dictionary<string, object?> { ["status"] = "ACTIVE" },
                newValues: new Dictionary<string, object?>
                {
                    ["status"] = "CANCELLED", ["cancelled_at"] = now, ["cancellation_reason"] = visit.CancellationReason
                }, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        return VisitDtoMapper.ToDto(await GetVisit(visitId, context.BranchId, cancellationToken).ConfigureAwait(false));
    }

    private async Task<Visit> GetVisit(long visitId, long branchId, CancellationToken cancellationToken) =>
        await visits.GetInBranchAsync(visitId, branchId, cancellationToken).ConfigureAwait(false)
        ?? throw new ApplicationNotFoundException("The requested visit does not exist.");

    private async Task<Branch> ResolveBranch(long branchId, CancellationToken cancellationToken) =>
        (await references.GetBranchAsync(branchId, cancellationToken).ConfigureAwait(false))
        ?? throw new ApplicationNotFoundException("The authorized branch does not exist.");

    private async Task<User> ResolveUser(long userId, CancellationToken cancellationToken) =>
        (await references.GetUserAsync(userId, cancellationToken).ConfigureAwait(false))
        ?? throw new ApplicationNotFoundException("The authenticated user does not exist.");

    private DateTime Now() => ApplicationTime.ToUtc(clock.UtcNow);

    private static void ValidateCreate(VisitCreateRequest request)
    {
        InputValidators.MaxLength(request.Destination, 200, "destination");
        InputValidators.MaxLength(request.VisitedPerson, 200, "visited_person");
        InputValidators.MaxLength(request.Notes, 1000, "notes");
    }

    private static void ValidateDateRange(DateTime? from, DateTime? to)
    {
        if (from is not null && to is not null && from >= to)
            throw new ApplicationValidationException("date_to must be later than date_from; the upper bound is exclusive.");
    }

    private static string? NormalizeOptional(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    private static void ApplyTextUpdate(FieldUpdate<string?> field, string name, int maximumLength,
        Action<string?> assign, IDictionary<string, object?> oldValues, IDictionary<string, object?> newValues, string? oldValue)
    {
        if (!field.IsSpecified) return;
        InputValidators.MaxLength(field.Value, maximumLength, name);
        oldValues[name] = oldValue;
        var normalized = NormalizeOptional(field.Value);
        assign(normalized);
        newValues[name] = normalized;
    }
}
