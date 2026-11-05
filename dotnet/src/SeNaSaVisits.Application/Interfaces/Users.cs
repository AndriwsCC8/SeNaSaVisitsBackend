using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.Interfaces;

public sealed record UserSearchCriteria(string? Search, bool? IsActive, long? BranchId, string? RoleCode, DateTime AtUtc);

public interface IUserRepository
{
    Task<User?> GetByIdAsync(long userId, CancellationToken cancellationToken);

    /// <summary>Searches username/name/employee code, filters current branch assignment/active role, orders by Id ASC, and returns loaded role/assignment navigations.</summary>
    Task<(IReadOnlyList<User> Items, int Total)> SearchAsync(
        UserSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken);

    Task<bool> UsernameExistsAsync(string username, long? excludingUserId, CancellationToken cancellationToken);

    Task<bool> EmailExistsAsync(string email, long? excludingUserId, CancellationToken cancellationToken);

    Task<bool> EmployeeCodeExistsAsync(string employeeCode, long? excludingUserId, CancellationToken cancellationToken);

    Task AddAsync(User user, CancellationToken cancellationToken);

    Task SaveChangesAsync(User user, CancellationToken cancellationToken);
}

public interface IRoleRepository
{
    Task<Role?> GetByCodeAsync(string roleCode, CancellationToken cancellationToken);

    Task<IReadOnlyList<Role>> ListActiveForUserAsync(long userId, CancellationToken cancellationToken);

    /// <summary>Replace all active role assignments for the user and add the specified role atomically.</summary>
    Task ReplaceActiveRoleAsync(long userId, Role role, long assignedByUserId, DateTime atUtc, CancellationToken cancellationToken);
}

public interface IUserBranchAssignmentRepository
{
    Task<IReadOnlyList<UserBranchAssignment>> ListForUserAsync(long userId, CancellationToken cancellationToken);

    Task<UserBranchAssignment?> GetByIdAsync(long assignmentId, CancellationToken cancellationToken);

    /// <summary>Reads assignment history for ordinary assignment creation; transfer uses the protected transaction overload below.</summary>
    Task<IReadOnlyList<UserBranchAssignment>> ListForOverlapCheckAsync(long userId, CancellationToken cancellationToken);

    /// <summary>
    /// Reads the full assignment history inside the supplied transaction while acquiring the SQL Server
    /// protection required for transfer (equivalent to UPDLOCK and HOLDLOCK). It must not open another connection.
    /// </summary>
    Task<IReadOnlyList<UserBranchAssignment>> GetHistoryForTransferAsync(
        long userId, IApplicationTransaction transaction, CancellationToken cancellationToken);

    /// <summary>Persists a changed assignment using exactly the supplied transaction and connection.</summary>
    Task SaveTransferChangeAsync(
        UserBranchAssignment assignment, IApplicationTransaction transaction, CancellationToken cancellationToken);

    /// <summary>Inserts the new transfer assignment using exactly the supplied transaction and connection.</summary>
    Task<UserBranchAssignment> AddTransferAssignmentAsync(
        UserBranchAssignment assignment, IApplicationTransaction transaction, CancellationToken cancellationToken);

    Task AddAsync(UserBranchAssignment assignment, CancellationToken cancellationToken);

    Task SaveChangesAsync(UserBranchAssignment assignment, CancellationToken cancellationToken);

}

public interface IBranchRepository
{
    Task<Branch?> GetByIdAsync(long branchId, CancellationToken cancellationToken);
}

