using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Validators;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.ValueObjects;

namespace SeNaSaVisits.Application.Services;

/// <summary>Visitor profiles are global records; permission checks still require the authenticated user's branch context.</summary>
public sealed class VisitorManagementService(
    IVisitorRepository visitors,
    IVisitorTypeRepository visitorTypes,
    ICurrentUser currentUser,
    IPermissionEvaluator permissions,
    BranchAccessService branchAccess,
    IClock clock,
    ITransactionRunner transactions,
    AuditService audit)
{
    public async Task<PageResult<VisitorDto>> SearchAsync(VisitorSearchRequest request, CancellationToken cancellationToken)
    {
        request.Page.Validate();
        InputValidators.MaxLength(request.Search, 100, "search");
        var branch = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_VISITORS", branch.BranchId, cancellationToken).ConfigureAwait(false);
        var includeContact = await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_VISITOR_CONTACT", branch.BranchId, cancellationToken).ConfigureAwait(false);
        var result = await visitors.SearchAsync(new VisitorSearchCriteria(request.Search, request.IsActive,
            request.VisitorTypeId, includeContact), request.Page.Page, request.Page.PageSize, cancellationToken).ConfigureAwait(false);
        return new PageResult<VisitorDto>(result.Items.Select(item => VisitorDtoMapper.ToDto(item, includeContact)).ToArray(),
            result.Total, request.Page.Page, request.Page.PageSize);
    }

    public async Task<VisitorDto> GetAsync(long visitorId, CancellationToken cancellationToken)
    {
        var branch = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "VIEW_VISITORS", branch.BranchId, cancellationToken).ConfigureAwait(false);
        var canViewContact = await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_VISITOR_CONTACT", branch.BranchId, cancellationToken).ConfigureAwait(false);
        var visitor = await GetVisitor(visitorId, cancellationToken).ConfigureAwait(false);
        return VisitorDtoMapper.ToDto(visitor, canViewContact);
    }

    public async Task<VisitorDto> CreateAsync(VisitorCreateRequest request, AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var branch = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "CREATE_VISITOR", branch.BranchId, cancellationToken).ConfigureAwait(false);
        ValidateCreate(request);
        var identification = FromPythonInput(request.Identification);
        await ValidateType(request.VisitorTypeId, cancellationToken).ConfigureAwait(false);
        if (identification?.NormalizedValue is { } normalized &&
            await visitors.IdentificationExistsAsync(normalized, null, cancellationToken).ConfigureAwait(false))
            throw new ApplicationConflictException("The identification is already registered.");

        var visitor = new Visitor
        {
            Identification = identification,
            FirstName = InputValidators.NormalizeRequiredText(request.FirstName, "first_name"),
            LastName = InputValidators.NormalizeRequiredText(request.LastName, "last_name"),
            Phone = string.IsNullOrWhiteSpace(request.Phone) ? null : request.Phone.Trim(),
            Email = InputValidators.ValidateEmail(request.Email),
            Company = string.IsNullOrWhiteSpace(request.Company) ? null : request.Company.Trim(),
            VisitorTypeId = request.VisitorTypeId,
            IsActive = true,
            CreatedAt = Now(),
            UpdatedAt = Now()
        };
        await transactions.ExecuteAsync(async ct =>
        {
            await visitors.AddAsync(visitor, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "CREATE_VISITOR", "Visitor", visitor.Id,
                newValues: new Dictionary<string, object?>
                {
                    ["visitor_id"] = visitor.Id, ["first_name"] = visitor.FirstName,
                    ["last_name"] = visitor.LastName, ["is_active"] = true
                }, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        var canViewContact = await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_VISITOR_CONTACT", branch.BranchId, cancellationToken).ConfigureAwait(false);
        return VisitorDtoMapper.ToDto(await GetVisitor(visitor.Id, cancellationToken).ConfigureAwait(false), canViewContact);
    }

    public async Task<VisitorDto> UpdateAsync(long visitorId, VisitorUpdateRequest request,
        AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var branch = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "UPDATE_VISITOR", branch.BranchId, cancellationToken).ConfigureAwait(false);
        var visitor = await GetVisitor(visitorId, cancellationToken).ConfigureAwait(false);
        var oldValues = new Dictionary<string, object?>();
        var newValues = new Dictionary<string, object?>();

        if (request.FirstName.IsSpecified && request.FirstName.Value is not null)
        {
            InputValidators.MaxLength(request.FirstName.Value, 100, "first_name");
            oldValues["first_name"] = visitor.FirstName;
            visitor.FirstName = InputValidators.NormalizeRequiredText(request.FirstName.Value, "first_name");
            newValues["first_name"] = visitor.FirstName;
        }
        if (request.LastName.IsSpecified && request.LastName.Value is not null)
        {
            InputValidators.MaxLength(request.LastName.Value, 100, "last_name");
            oldValues["last_name"] = visitor.LastName;
            visitor.LastName = InputValidators.NormalizeRequiredText(request.LastName.Value, "last_name");
            newValues["last_name"] = visitor.LastName;
        }
        if (request.Identification.IsSpecified)
        {
            var identification = FromPythonInput(request.Identification.Value);
            if (identification?.NormalizedValue is { } normalized &&
                normalized != visitor.IdentificationNormalized &&
                await visitors.IdentificationExistsAsync(normalized, visitorId, cancellationToken).ConfigureAwait(false))
                throw new ApplicationConflictException("The identification is already registered.");
            visitor.Identification = identification;
            oldValues["identification"] = "[REDACTED]";
            newValues["identification"] = identification?.RawValue is null ? null : "[REDACTED]";
        }
        if (request.Phone.IsSpecified)
        {
            if (request.Phone.Value is null)
                throw new ApplicationValidationException("Explicit null for phone is not supported by the current Python update path.");
            InputValidators.MaxLength(request.Phone.Value, 30, "phone");
            visitor.Phone = request.Phone.Value.Trim().Length == 0 ? null : request.Phone.Value.Trim();
        }
        if (request.Email.IsSpecified)
        {
            InputValidators.MaxLength(request.Email.Value, 254, "email");
            visitor.Email = InputValidators.ValidateEmail(request.Email.Value);
        }
        if (request.Company.IsSpecified)
        {
            if (request.Company.Value is null)
                throw new ApplicationValidationException("Explicit null for company is not supported by the current Python update path.");
            InputValidators.MaxLength(request.Company.Value, 200, "company");
            oldValues["company"] = visitor.Company;
            visitor.Company = request.Company.Value.Trim().Length == 0 ? null : request.Company.Value.Trim();
            newValues["company"] = visitor.Company;
        }
        if (request.VisitorTypeId.IsSpecified)
        {
            await ValidateType(request.VisitorTypeId.Value, cancellationToken).ConfigureAwait(false);
            visitor.VisitorTypeId = request.VisitorTypeId.Value;
        }
        visitor.UpdatedAt = Now();
        await transactions.ExecuteAsync(async ct =>
        {
            await visitors.SaveChangesAsync(visitor, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "UPDATE_VISITOR", "Visitor", visitor.Id,
                oldValues: oldValues, newValues: newValues, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        var canViewContact = await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_VISITOR_CONTACT", branch.BranchId, cancellationToken).ConfigureAwait(false);
        return VisitorDtoMapper.ToDto(await GetVisitor(visitorId, cancellationToken).ConfigureAwait(false), canViewContact);
    }

    public async Task<VisitorDto> SetActiveAsync(long visitorId, bool active, AuditContext? auditContext, CancellationToken cancellationToken)
    {
        var branch = await branchAccess.RequireCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
        await permissions.RequirePermissionAsync(currentUser.UserId, "UPDATE_VISITOR", branch.BranchId, cancellationToken).ConfigureAwait(false);
        var visitor = await GetVisitor(visitorId, cancellationToken).ConfigureAwait(false);
        visitor.IsActive = active;
        visitor.UpdatedAt = Now();
        await transactions.ExecuteAsync(async ct =>
        {
            await visitors.SaveChangesAsync(visitor, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "UPDATE_VISITOR", "Visitor", visitorId,
                oldValues: new Dictionary<string, object?> { ["is_active"] = !active },
                newValues: new Dictionary<string, object?> { ["is_active"] = active }, context: auditContext,
                cancellationToken: ct).ConfigureAwait(false);
            return true;
        }, cancellationToken).ConfigureAwait(false);
        var canViewContact = await permissions.HasPermissionAsync(currentUser.UserId, "VIEW_VISITOR_CONTACT", branch.BranchId, cancellationToken).ConfigureAwait(false);
        return VisitorDtoMapper.ToDto(await GetVisitor(visitorId, cancellationToken).ConfigureAwait(false), canViewContact);
    }

    private async Task<Visitor> GetVisitor(long id, CancellationToken cancellationToken) =>
        await visitors.GetByIdAsync(id, cancellationToken).ConfigureAwait(false)
        ?? throw new ApplicationNotFoundException("The requested visitor does not exist.");

    private async Task ValidateType(long? typeId, CancellationToken cancellationToken)
    {
        if (typeId is null) return;
        var type = await visitorTypes.GetByIdAsync(typeId.Value, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationNotFoundException("The requested visitor type does not exist.");
        if (!type.IsActive) throw new ApplicationValidationException("The requested visitor type is inactive.");
    }

    private static VisitorIdentification? FromPythonInput(string? value) =>
        string.IsNullOrEmpty(value) ? null : VisitorIdentification.From(value);

    private DateTime Now() => ApplicationTime.ToUtc(clock.UtcNow);

    private static void ValidateCreate(VisitorCreateRequest request)
    {
        InputValidators.RequiredText(request.FirstName, "first_name", 100);
        InputValidators.RequiredText(request.LastName, "last_name", 100);
        InputValidators.MaxLength(request.Identification, 50, "identification");
        InputValidators.MaxLength(request.Phone, 30, "phone");
        InputValidators.MaxLength(request.Email, 254, "email");
        InputValidators.MaxLength(request.Company, 200, "company");
        _ = InputValidators.ValidateEmail(request.Email);
    }
}
