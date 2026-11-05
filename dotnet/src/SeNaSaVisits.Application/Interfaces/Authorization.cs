using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.Interfaces;

public interface IPermissionDataSource
{
    Task<bool?> GetUserActiveAsync(long userId, CancellationToken cancellationToken);

    Task<Permission?> GetPermissionAsync(string code, CancellationToken cancellationToken);

    /// <summary>Returns direct grants for the user/permission; Application rechecks active dates and scope branch.</summary>
    Task<IReadOnlyCollection<UserPermission>> GetDirectGrantsAsync(
        long userId, long permissionId, CancellationToken cancellationToken);

    /// <summary>Must consider only active UserRole, Role, and RolePermission rows.</summary>
    Task<bool> HasActiveRoleGrantAsync(long userId, long permissionId, CancellationToken cancellationToken);
}

public sealed record CurrentBranchAssignment(UserBranchAssignment Assignment, bool BranchIsActive);

public interface IBranchAssignmentReader
{
    /// <summary>Returns every ACTIVE assignment containing the instant, including whether its branch is active.</summary>
    Task<IReadOnlyList<CurrentBranchAssignment>> GetCurrentAssignmentsAsync(
        long userId, DateTime atUtc, CancellationToken cancellationToken);
}

public interface IPermissionEvaluator
{
    Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken);

    Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken);
}
