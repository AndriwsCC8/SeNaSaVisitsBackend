using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Services;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class TransferTransactionOrderingTests
{
    private static readonly DateTime Now = new(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc);

    [Fact]
    public async Task TransferReadsDecidesClosesCreatesAuditsAndCommitsWithinOneTransactionInOrder()
    {
        var setup = Create();

        var result = await setup.Service.TransferAsync(4, new UserTransferRequest(8), null, default);

        Assert.Equal(8, result.BranchId);
        Assert.Equal(
            ["begin", "history", "close", "create", "audit", "commit"],
            setup.Events);
        Assert.Same(setup.Transaction, setup.Assignments.TransactionUsedForHistory);
        Assert.Same(setup.Transaction, setup.Assignments.TransactionUsedForClose);
        Assert.Same(setup.Transaction, setup.Assignments.TransactionUsedForCreate);
        Assert.Same(setup.Transaction, setup.AuditWriter.TransactionUsedForAudit);
        Assert.Equal(7L, setup.AuditWriter.LastAudit!.OldValuesBranchId());
        Assert.Equal(Now, setup.Assignments.Created!.ValidFrom);
        Assert.Equal(UserBranchAssignmentStatus.Ended, setup.Assignments.Previous.Status);
        Assert.Equal(Now, setup.Assignments.Previous.ValidUntil);
    }

    [Theory]
    [InlineData("history")]
    [InlineData("close")]
    [InlineData("create")]
    public async Task TransferRollsBackWhenHistoryCloseOrCreateFails(string failAt)
    {
        var setup = Create(failAt);

        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            setup.Service.TransferAsync(4, new UserTransferRequest(8), null, default));

        Assert.Equal("begin", setup.Events[0]);
        Assert.Equal("rollback", setup.Events[^1]);
        Assert.DoesNotContain("commit", setup.Events);
        if (failAt == "history")
        {
            Assert.Equal(["begin", "history", "rollback"], setup.Events);
            Assert.DoesNotContain("close", setup.Events);
            Assert.DoesNotContain("create", setup.Events);
        }
        else if (failAt == "close")
        {
            Assert.Equal(["begin", "history", "close", "rollback"], setup.Events);
            Assert.DoesNotContain("create", setup.Events);
        }
        else
        {
            Assert.Equal(["begin", "history", "close", "create", "rollback"], setup.Events);
            Assert.DoesNotContain("audit", setup.Events);
        }
    }

    [Fact]
    public async Task SameBranchConflictIsDecidedFromProtectedInTransactionHistoryAndRollsBack()
    {
        var setup = Create(newBranchId: 7);

        await Assert.ThrowsAsync<ApplicationConflictException>(() =>
            setup.Service.TransferAsync(4, new UserTransferRequest(7), null, default));

        Assert.Equal(["begin", "history", "rollback"], setup.Events);
        Assert.Same(setup.Transaction, setup.Assignments.TransactionUsedForHistory);
    }

    private static TestSetup Create(string? failAt = null, long newBranchId = 8)
    {
        var events = new List<string>();
        var transaction = new FakeApplicationTransaction(events);
        var runner = new RecordingTransactionRunner(events, transaction);
        var previousBranch = new Branch { Id = 7, Code = "B7", Name = "Old", BranchTypeId = 1, IsActive = true };
        var previous = new UserBranchAssignment
        {
            Id = 70, UserId = 4, BranchId = previousBranch.Id, Branch = previousBranch,
            AssignedByUserId = 2, ValidFrom = Now.AddDays(-10), Status = UserBranchAssignmentStatus.Active
        };
        var nextBranch = new Branch { Id = newBranchId, Code = $"B{newBranchId}", Name = "New", BranchTypeId = 1, IsActive = true };
        var assignments = new RecordingAssignmentRepository(events, transaction, previous, nextBranch, failAt);
        var auditWriter = new RecordingAuditWriter(events, transaction);
        var service = new UserManagementService(
            new FakeUsers(), new FakeRoles(), assignments, new FakeBranches(nextBranch),
            new FakePasswordHasher(), new FakeClock(), new FakeCurrentUser(), new AllowPermission(),
            runner, new AuditService(auditWriter, new FakeClock()));
        return new TestSetup(service, events, transaction, assignments, auditWriter);
    }

    private sealed record TestSetup(UserManagementService Service, List<string> Events,
        FakeApplicationTransaction Transaction, RecordingAssignmentRepository Assignments,
        RecordingAuditWriter AuditWriter);

    private sealed class FakeApplicationTransaction(List<string> events) : IApplicationTransaction
    {
        public bool IsActive { get; set; }
        public List<string> Events { get; } = events;
    }

    private sealed class RecordingTransactionRunner(List<string> events, FakeApplicationTransaction transaction) : ITransactionRunner
    {
        public async Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken cancellationToken)
        {
            events.Add("begin");
            try
            {
                var result = await operation(cancellationToken);
                events.Add("commit");
                return result;
            }
            catch
            {
                events.Add("rollback");
                throw;
            }
        }

        public async Task<T> ExecuteWithTransactionAsync<T>(
            Func<IApplicationTransaction, CancellationToken, Task<T>> operation, CancellationToken cancellationToken)
        {
            events.Add("begin");
            transaction.IsActive = true;
            try
            {
                var result = await operation(transaction, cancellationToken);
                events.Add("commit");
                transaction.IsActive = false;
                return result;
            }
            catch
            {
                events.Add("rollback");
                transaction.IsActive = false;
                throw;
            }
        }
    }

    private sealed class RecordingAssignmentRepository(
        List<string> events, FakeApplicationTransaction expectedTransaction,
        UserBranchAssignment previous, Branch nextBranch, string? failAt) : IUserBranchAssignmentRepository
    {
        public IApplicationTransaction? TransactionUsedForHistory { get; private set; }
        public IApplicationTransaction? TransactionUsedForClose { get; private set; }
        public IApplicationTransaction? TransactionUsedForCreate { get; private set; }
        public UserBranchAssignment Previous { get; } = previous;
        public UserBranchAssignment? Created { get; private set; }

        public Task<IReadOnlyList<UserBranchAssignment>> GetHistoryForTransferAsync(
            long userId, IApplicationTransaction transaction, CancellationToken cancellationToken)
        {
            AssertTransaction(transaction);
            TransactionUsedForHistory = transaction;
            events.Add("history");
            ThrowIf("history");
            return Task.FromResult<IReadOnlyList<UserBranchAssignment>>([Previous]);
        }

        public Task SaveTransferChangeAsync(UserBranchAssignment assignment, IApplicationTransaction transaction, CancellationToken cancellationToken)
        {
            AssertTransaction(transaction);
            TransactionUsedForClose = transaction;
            Assert.Same(Previous, assignment);
            events.Add("close");
            ThrowIf("close");
            return Task.CompletedTask;
        }

        public Task<UserBranchAssignment> AddTransferAssignmentAsync(
            UserBranchAssignment assignment, IApplicationTransaction transaction, CancellationToken cancellationToken)
        {
            AssertTransaction(transaction);
            TransactionUsedForCreate = transaction;
            events.Add("create");
            ThrowIf("create");
            assignment.Id = 80;
            assignment.Branch = nextBranch;
            Created = assignment;
            return Task.FromResult(assignment);
        }

        public Task<IReadOnlyList<UserBranchAssignment>> ListForUserAsync(long userId, CancellationToken cancellationToken) => Task.FromResult<IReadOnlyList<UserBranchAssignment>>([Previous]);
        public Task<UserBranchAssignment?> GetByIdAsync(long assignmentId, CancellationToken cancellationToken) => Task.FromResult<UserBranchAssignment?>(Previous);
        public Task<IReadOnlyList<UserBranchAssignment>> ListForOverlapCheckAsync(long userId, CancellationToken cancellationToken) => Task.FromResult<IReadOnlyList<UserBranchAssignment>>([Previous]);
        public Task AddAsync(UserBranchAssignment assignment, CancellationToken cancellationToken) => Task.CompletedTask;
        public Task SaveChangesAsync(UserBranchAssignment assignment, CancellationToken cancellationToken) => Task.CompletedTask;

        private void AssertTransaction(IApplicationTransaction transaction)
        {
            Assert.Same(expectedTransaction, transaction);
            Assert.True(expectedTransaction.IsActive, "Repository operation must execute while transaction is active.");
        }

        private void ThrowIf(string operation)
        {
            if (failAt == operation) throw new InvalidOperationException($"Injected {operation} failure.");
        }
    }

    private sealed class RecordingAuditWriter(List<string> events, FakeApplicationTransaction transaction) : IAuditWriter
    {
        public AuditLog? LastAudit { get; private set; }
        public IApplicationTransaction? TransactionUsedForAudit { get; private set; }
        public Task AppendAsync(AuditLog auditLog, CancellationToken cancellationToken, IApplicationTransaction? transactionScope = null)
        {
            Assert.True(transaction.IsActive, "Audit insert must use the active transaction scope.");
            Assert.Same(transaction, transactionScope);
            TransactionUsedForAudit = transactionScope;
            events.Add("audit");
            LastAudit = auditLog;
            return Task.CompletedTask;
        }
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
    private sealed class FakeBranches(Branch branch) : IBranchRepository
    {
        public Task<Branch?> GetByIdAsync(long branchId, CancellationToken cancellationToken) => Task.FromResult<Branch?>(branch.Id == branchId ? branch : null);
    }
    private sealed class FakePasswordHasher : IPasswordHasher { public string Hash(string password) => "test-hash"; }
    private sealed class FakeClock : IClock { public DateTime UtcNow => Now; }
    private sealed class FakeCurrentUser : ICurrentUser { public long UserId => 2; }
    private sealed class AllowPermission : IPermissionEvaluator
    {
        public Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) => Task.FromResult(true);
        public Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) => Task.CompletedTask;
    }
}

internal static class AuditJsonTestExtensions
{
    public static long? OldValuesBranchId(this AuditLog audit)
    {
        using var document = System.Text.Json.JsonDocument.Parse(audit.OldValues!);
        return document.RootElement.GetProperty("old_branch_id").ValueKind == System.Text.Json.JsonValueKind.Null
            ? null
            : document.RootElement.GetProperty("old_branch_id").GetInt64();
    }
}
