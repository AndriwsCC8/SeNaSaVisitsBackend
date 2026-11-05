using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.Services;

/// <summary>Evaluates effective permissions from persisted facts; role membership alone is never authorization.</summary>
public sealed class PermissionService(
    IPermissionDataSource permissions,
    BranchAccessService branchAccess,
    IClock clock) : IPermissionEvaluator
{
    public async Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken)
    {
        var userActive = await permissions.GetUserActiveAsync(userId, cancellationToken).ConfigureAwait(false);
        var permission = await permissions.GetPermissionAsync(permissionCode, cancellationToken).ConfigureAwait(false);
        if (userActive != true || permission is null || !permission.IsActive || !Enum.IsDefined(permission.Scope))
        {
            return false;
        }

        DateTime now = UtcDateTime.Normalize(clock.UtcNow);
        long? effectiveBranchId;
        switch (permission.Scope)
        {
            case PermissionScope.Global:
                if (branchId is not null) return false;
                effectiveBranchId = null;
                break;
            case PermissionScope.Branch:
                if (branchId is null) return false;
                var context = await branchAccess.GetCurrentContextAsync(userId, cancellationToken).ConfigureAwait(false);
                if (context is null || context.BranchId != branchId.Value) return false;
                effectiveBranchId = context.BranchId;
                break;
            default:
                return false;
        }

        var directGrants = await permissions.GetDirectGrantsAsync(userId, permission.Id, cancellationToken).ConfigureAwait(false);
        var applicable = directGrants.Where(grant =>
            grant.UserId == userId && grant.PermissionId == permission.Id && grant.IsEffectiveAt(now) &&
            Enum.IsDefined(grant.Effect) && grant.BranchId == effectiveBranchId).ToArray();
        if (applicable.Any(grant => grant.Effect == PermissionEffect.Deny)) return false;
        if (applicable.Any(grant => grant.Effect == PermissionEffect.Allow)) return true;

        return await permissions.HasActiveRoleGrantAsync(userId, permission.Id, cancellationToken).ConfigureAwait(false);
    }

    public async Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken)
    {
        if (!await HasPermissionAsync(userId, permissionCode, branchId, cancellationToken).ConfigureAwait(false))
        {
            throw new ApplicationForbiddenException("The authenticated user does not have the required permission.");
        }
    }
}
