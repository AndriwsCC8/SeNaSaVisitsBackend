using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Services;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class UserAssignmentUseCaseTests
{
    private static readonly DateTime Now = new(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc);

    [Fact]
    public async Task AssignBranchAllowsAdjacentNonOverlappingIntervals()
    {
        var repository = new FakeAssignments
        {
            History = [Assignment(from: Now.AddDays(-1), until: Now)]
        };
        var service = CreateService(repository);

        var result = await service.AssignBranchAsync(4, new UserAssignmentRequest(7, Now), null, default);

        Assert.Equal(7, result.BranchId);
        Assert.Single(repository.Added);
        Assert.Equal(UserBranchAssignmentStatus.Active, repository.Added[0].Status);
    }

    [Fact]
    public async Task AssignBranchRejectsOverlappingHistory()
    {
        var repository = new FakeAssignments
        {
            History = [Assignment(from: Now.AddDays(-1), until: Now.AddDays(1))]
        };
        var service = CreateService(repository);

        await Assert.ThrowsAsync<ApplicationConflictException>(() =>
            service.AssignBranchAsync(4, new UserAssignmentRequest(7, Now), null, default));
        Assert.Empty(repository.Added);
    }

    [Fact]
    public async Task TransferDelegatesAtomicLockingOperationAndUsesInjectedClockWhenDateOmitted()
    {
        var repository = new FakeAssignments { History = [Assignment(from: Now.AddDays(-1), until: null)] };
        var service = CreateService(repository);

        var result = await service.TransferAsync(4, new UserTransferRequest(8), null, default);

        Assert.Equal(1, repository.ProtectedHistoryReads);
        Assert.Equal(8, result.BranchId);
        Assert.Single(repository.Added);
        Assert.Equal(Now, repository.Added[0].ValidFrom);
    }

    private static UserManagementService CreateService(FakeAssignments assignments) => new(
        new FakeUsers(), new FakeRoles(), assignments, new FakeBranches(), new FakePasswordHasher(),
        new FakeClock(), new FakeCurrentUser(), new AllowPermission(), new InlineTransactionRunner(),
        new AuditService(new FakeAuditWriter(), new FakeClock()));

    private static UserBranchAssignment Assignment(DateTime from, DateTime? until) => new()
    {
        Id = 20, UserId = 4, BranchId = 7, AssignedByUserId = 2,
        ValidFrom = from, ValidUntil = until, Status = until is null ? UserBranchAssignmentStatus.Active : UserBranchAssignmentStatus.Ended,
        Branch = new Branch { Id = 7, Code = "B7", Name = "Branch 7", BranchTypeId = 1, IsActive = true }
    };

    private sealed class FakeAssignments : IUserBranchAssignmentRepository
    {
        public IReadOnlyList<UserBranchAssignment> History { get; set; } = [];
        public List<UserBranchAssignment> Added { get; } = [];
        public int ProtectedHistoryReads { get; private set; }
        public Task<IReadOnlyList<UserBranchAssignment>> ListForUserAsync(long userId, CancellationToken cancellationToken) => Task.FromResult(History);
        public Task<UserBranchAssignment?> GetByIdAsync(long assignmentId, CancellationToken cancellationToken) => Task.FromResult<UserBranchAssignment?>(Added.FirstOrDefault(item => item.Id == assignmentId));
        public Task<IReadOnlyList<UserBranchAssignment>> ListForOverlapCheckAsync(long userId, CancellationToken cancellationToken) => Task.FromResult(History);
        public Task<IReadOnlyList<UserBranchAssignment>> GetHistoryForTransferAsync(long userId, IApplicationTransaction transaction, CancellationToken cancellationToken)
        {
            ProtectedHistoryReads++;
            return Task.FromResult(History);
        }
        public Task SaveTransferChangeAsync(UserBranchAssignment assignment, IApplicationTransaction transaction, CancellationToken cancellationToken) => Task.CompletedTask;
        public Task<UserBranchAssignment> AddTransferAssignmentAsync(UserBranchAssignment assignment, IApplicationTransaction transaction, CancellationToken cancellationToken)
        {
            assignment.Id = 30;
            Added.Add(assignment);
            return Task.FromResult(assignment);
        }
        public Task AddAsync(UserBranchAssignment assignment, CancellationToken cancellationToken) { assignment.Id = 21; Added.Add(assignment); return Task.CompletedTask; }
        public Task SaveChangesAsync(UserBranchAssignment assignment, CancellationToken cancellationToken) => Task.CompletedTask;
    }

    private sealed class FakeUsers : IUserRepository
    {
        private readonly User user = new() { Id = 4, Username = "person", FirstName = "User", LastName = "Four", PasswordHash = "hash", IsActive = true };
        public Task<User?> GetByIdAsync(long userId, CancellationToken cancellationToken) => Task.FromResult<User?>(userId == user.Id ? user : null);
        public Task<(IReadOnlyList<User> Items, int Total)> SearchAsync(UserSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken) => Task.FromResult<(IReadOnlyList<User>, int)>(([user], 1));
        public Task<bool> UsernameExistsAsync(string username, long? excludingUserId, CancellationToken cancellationToken) => Task.FromResult(false);
        public Task<bool> EmailExistsAsync(string email, long? excludingUserId, CancellationToken cancellationToken) => Task.FromResult(false);
        public Task<bool> EmployeeCodeExistsAsync(string employeeCode, long? excludingUserId, CancellationToken cancellationToken) => Task.FromResult(false);
        public Task AddAsync(User user, CancellationToken cancellationToken) => Task.CompletedTask;
        public Task SaveChangesAsync(User user, CancellationToken cancellationToken) => Task.CompletedTask;
    }

    private sealed class FakeRoles : IRoleRepository
    {
        public Task<Role?> GetByCodeAsync(string roleCode, CancellationToken cancellationToken) => Task.FromResult<Role?>(null);
        public Task<IReadOnlyList<Role>> ListActiveForUserAsync(long userId, CancellationToken cancellationToken) => Task.FromResult<IReadOnlyList<Role>>([]);
        public Task ReplaceActiveRoleAsync(long userId, Role role, long assignedByUserId, DateTime atUtc, CancellationToken cancellationToken) => Task.CompletedTask;
    }
    private sealed class FakeBranches : IBranchRepository
    {
        public Task<Branch?> GetByIdAsync(long branchId, CancellationToken cancellationToken) => Task.FromResult<Branch?>(new Branch { Id = branchId, Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = true });
    }
    private sealed class FakePasswordHasher : IPasswordHasher { public string Hash(string password) => "test-hash"; }
    private sealed class FakeClock : IClock { public DateTime UtcNow => Now; }
    private sealed class FakeCurrentUser : ICurrentUser { public long UserId => 2; }
    private sealed class AllowPermission : IPermissionEvaluator
    {
        public Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) => Task.FromResult(true);
        public Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) => Task.CompletedTask;
    }
    private sealed class InlineTransactionRunner : ITransactionRunner
    {
        public Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken cancellationToken) => operation(cancellationToken);
        public Task<T> ExecuteWithTransactionAsync<T>(Func<IApplicationTransaction, CancellationToken, Task<T>> operation, CancellationToken cancellationToken) =>
            operation(new FakeApplicationTransaction(), cancellationToken);
    }
    private sealed class FakeApplicationTransaction : IApplicationTransaction;
    private sealed class FakeAuditWriter : IAuditWriter { public Task AppendAsync(AuditLog auditLog, CancellationToken cancellationToken, IApplicationTransaction? transaction = null) => Task.CompletedTask; }
}
