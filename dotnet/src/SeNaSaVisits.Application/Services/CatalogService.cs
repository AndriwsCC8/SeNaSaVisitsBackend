using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.Services;

/// <summary>Read-only reference catalogs with the same authorization alternatives as the current API.</summary>
public sealed class CatalogService(
    ICatalogReader catalogs,
    IPermissionEvaluator permissions,
    BranchAccessService branchAccess,
    ICurrentUser currentUser)
{
    private static readonly string[] BranchGlobalPermissions =
        ["MANAGE_BRANCHES", "MANAGE_USERS", "ASSIGN_USER_BRANCH", "MOVE_USER_BRANCH", "VIEW_GLOBAL_REPORTS", "VIEW_AUDIT_LOGS"];
    private static readonly string[] BranchLocalPermissions =
        ["VIEW_VISITS", "CREATE_VISIT", "UPDATE_VISIT", "VIEW_VISITORS", "VIEW_REPORTS"];
    private static readonly string[] VisitorTypeBranchPermissions =
        ["VIEW_VISITORS", "CREATE_VISITOR", "UPDATE_VISITOR", "VIEW_VISITS", "CREATE_VISIT"];
    private static readonly string[] VisitReasonBranchPermissions =
        ["VIEW_VISITS", "CREATE_VISIT", "UPDATE_VISIT", "VIEW_REPORTS"];

    public async Task<IReadOnlyList<CatalogItemDto>> ListBranchesAsync(bool includeInactive, CancellationToken cancellationToken)
    {
        var global = await HasAny(BranchGlobalPermissions, null, cancellationToken).ConfigureAwait(false);
        long? branchId = null;
        if (!global)
        {
            var context = await branchAccess.GetCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
            if (context is null || !await HasAny(BranchLocalPermissions, context.BranchId, cancellationToken).ConfigureAwait(false))
                throw new ApplicationForbiddenException("No branch catalog access is available.");
            branchId = context.BranchId;
        }
        if (includeInactive) await permissions.RequirePermissionAsync(currentUser.UserId, "MANAGE_BRANCHES", null, cancellationToken).ConfigureAwait(false);
        var items = await catalogs.ListBranchesAsync(branchId, includeInactive, cancellationToken).ConfigureAwait(false);
        return items.Select(branch => new CatalogItemDto(branch.Id, branch.Code, branch.Name, branch.BranchTypeId, branch.IsActive)).ToArray();
    }

    public async Task<IReadOnlyList<CatalogItemDto>> ListBranchTypesAsync(bool includeInactive, CancellationToken cancellationToken)
    {
        await permissions.RequirePermissionAsync(currentUser.UserId, "MANAGE_BRANCHES", null, cancellationToken).ConfigureAwait(false);
        var items = await catalogs.ListBranchTypesAsync(includeInactive, cancellationToken).ConfigureAwait(false);
        return items.Select(item => new CatalogItemDto(item.Id, item.Code, item.Name, IsActive: item.IsActive)).ToArray();
    }

    public async Task<IReadOnlyList<CatalogItemDto>> ListVisitorTypesAsync(bool includeInactive, CancellationToken cancellationToken)
    {
        var global = await permissions.HasPermissionAsync(currentUser.UserId, "MANAGE_VISITOR_TYPES", null, cancellationToken).ConfigureAwait(false);
        if (!global)
        {
            var context = await branchAccess.GetCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
            if (context is null || !await HasAny(VisitorTypeBranchPermissions, context.BranchId, cancellationToken).ConfigureAwait(false))
                throw new ApplicationForbiddenException("No visitor type catalog access is available.");
        }
        if (includeInactive) await permissions.RequirePermissionAsync(currentUser.UserId, "MANAGE_VISITOR_TYPES", null, cancellationToken).ConfigureAwait(false);
        var items = await catalogs.ListVisitorTypesAsync(includeInactive, cancellationToken).ConfigureAwait(false);
        return items.Select(item => new CatalogItemDto(item.Id, item.Code, item.Name, IsActive: item.IsActive)).ToArray();
    }

    public async Task<IReadOnlyList<CatalogItemDto>> ListVisitReasonsAsync(bool includeInactive, CancellationToken cancellationToken)
    {
        var global = await HasAny(["VIEW_GLOBAL_REPORTS", "MANAGE_VISIT_REASONS"], null, cancellationToken).ConfigureAwait(false);
        if (!global)
        {
            var context = await branchAccess.GetCurrentContextAsync(currentUser.UserId, cancellationToken).ConfigureAwait(false);
            if (context is null || !await HasAny(VisitReasonBranchPermissions, context.BranchId, cancellationToken).ConfigureAwait(false))
                throw new ApplicationForbiddenException("No visit reason catalog access is available.");
        }
        if (includeInactive) await permissions.RequirePermissionAsync(currentUser.UserId, "MANAGE_VISIT_REASONS", null, cancellationToken).ConfigureAwait(false);
        var items = await catalogs.ListVisitReasonsAsync(includeInactive, cancellationToken).ConfigureAwait(false);
        return items.Select(item => new CatalogItemDto(item.Id, item.Code, item.Name, IsActive: item.IsActive)).ToArray();
    }

    public async Task<IReadOnlyList<RoleDto>> ListRolesAsync(CancellationToken cancellationToken)
    {
        await permissions.RequirePermissionAsync(currentUser.UserId, "MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        var items = await catalogs.ListRolesAsync(false, cancellationToken).ConfigureAwait(false);
        return items.Select(item => new RoleDto(item.Id, item.Code, item.Name)).ToArray();
    }

    private async Task<bool> HasAny(IReadOnlyList<string> codes, long? branchId, CancellationToken cancellationToken)
    {
        foreach (var code in codes)
            if (await permissions.HasPermissionAsync(currentUser.UserId, code, branchId, cancellationToken).ConfigureAwait(false)) return true;
        return false;
    }
}
