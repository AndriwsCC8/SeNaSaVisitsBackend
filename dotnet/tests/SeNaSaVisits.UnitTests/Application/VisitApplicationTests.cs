using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Services;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.ValueObjects;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class VisitApplicationTests
{
    [Fact]
    public async Task CreateUsesAuthenticatedUserAndResolvedBranchAndSearchIsBranchScoped()
    {
        var repository = new FakeVisitRepository();
        var service = CreateService(repository);

        await service.CreateAsync(new VisitCreateRequest(VisitorId: 3, ReasonId: 4, Destination: "  Floor 2 "), null, default);

        Assert.Equal(7, repository.Added!.BranchId);
        Assert.Equal(1, repository.Added.RegisteredByUserId);
        Assert.Equal(VisitStatus.Active, repository.Added.Status);
        Assert.Equal("Floor 2", repository.Added.Destination);
        await service.SearchAsync(new VisitSearchRequest(new PageRequest()), default);
        Assert.Equal(7, repository.SearchCriteria!.BranchId);
    }

    [Fact]
    public async Task CompleteDefaultsExitTimeFromInjectedUtcClock()
    {
        var visit = CreateActiveVisit();
        var repository = new FakeVisitRepository(visit);
        var service = CreateService(repository);

        await service.CompleteAsync(visit.Id, new VisitCompleteRequest(), null, default);

        Assert.Equal(new DateTime(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc), visit.ExitAt);
        Assert.Equal(1, visit.CompletedByUserId);
    }

    [Fact]
    public async Task CancelUsesClockAndDomainNormalizesRequiredReason()
    {
        var visit = CreateActiveVisit();
        var repository = new FakeVisitRepository(visit);
        var service = CreateService(repository);

        await service.CancelAsync(visit.Id, new VisitCancelRequest("  no   show  "), null, default);

        Assert.Equal(VisitStatus.Cancelled, visit.Status);
        Assert.Equal("no show", visit.CancellationReason);
        Assert.Equal(new DateTime(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc), visit.CancelledAt);
    }

    [Fact]
    public async Task MissingBranchContextPreventsVisitAccess()
    {
        var service = CreateService(new FakeVisitRepository(), hasAssignment: false);

        await Assert.ThrowsAsync<ApplicationForbiddenException>(() => service.SearchAsync(new VisitSearchRequest(new PageRequest()), default));
    }

    private static Visit CreateActiveVisit()
    {
        var branch = new Branch { Id = 7, Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = true };
        var user = new User { Id = 1, Username = "u", FirstName = "User", LastName = "One", PasswordHash = "hash" };
        var visitor = new Visitor { Id = 3, FirstName = "Ana", LastName = "Visitor", Identification = VisitorIdentification.From("123456789") };
        var reason = new VisitReason { Id = 4, Code = "R", Name = "Reason" };
        return new Visit
        {
            Id = 9, VisitorId = 3, Visitor = visitor, BranchId = 7, Branch = branch,
            RegisteredByUserId = 1, RegisteredBy = user, ReasonId = 4, Reason = reason,
            EntryAt = new DateTime(2026, 10, 1, 11, 0, 0, DateTimeKind.Utc)
        };
    }

    private static VisitManagementService CreateService(FakeVisitRepository repository, bool hasAssignment = true) =>
        new(repository, new FakeReferences(), new FakeCurrentUser(), new AllowAllPermissions(),
            new BranchAccessService(new FakeAssignmentReader(hasAssignment), new FakeClock()), new FakeClock(),
            new InlineTransactionRunner(), new AuditService(new FakeAuditWriter(), new FakeClock()));

    private sealed class FakeVisitRepository(Visit? existing = null) : IVisitRepository
    {
        public Visit? Added { get; private set; }
        public VisitSearchCriteria? SearchCriteria { get; private set; }
        private Visit? Current => Added ?? existing;
        public Task<Visit?> GetInBranchAsync(long visitId, long branchId, CancellationToken cancellationToken) =>
            Task.FromResult(Current is { } visit && visit.Id == visitId && visit.BranchId == branchId ? visit : null);
        public Task<(IReadOnlyList<Visit> Items, int Total)> SearchInBranchAsync(VisitSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken)
        {
            SearchCriteria = criteria;
            return Task.FromResult<(IReadOnlyList<Visit>, int)>((Current is null ? [] : [Current], Current is null ? 0 : 1));
        }
        public Task AddAsync(Visit visit, CancellationToken cancellationToken) { visit.Id = 10; Added = visit; return Task.CompletedTask; }
        public Task SaveChangesAsync(Visit visit, CancellationToken cancellationToken) => Task.CompletedTask;
    }

    private sealed class FakeReferences : IVisitReferenceReader
    {
        private readonly Visitor visitor = new() { Id = 3, FirstName = "Ana", LastName = "Visitor", IsActive = true };
        private readonly VisitReason reason = new() { Id = 4, Code = "R", Name = "Reason", IsActive = true };
        private readonly Branch branch = new() { Id = 7, Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = true };
        private readonly User user = new() { Id = 1, Username = "u", FirstName = "User", LastName = "One", PasswordHash = "hash" };
        public Task<Visitor?> GetVisitorAsync(long visitorId, CancellationToken cancellationToken) => Task.FromResult<Visitor?>(visitorId == visitor.Id ? visitor : null);
        public Task<VisitReason?> GetReasonAsync(long reasonId, CancellationToken cancellationToken) => Task.FromResult<VisitReason?>(reasonId == reason.Id ? reason : null);
        public Task<Branch?> GetBranchAsync(long branchId, CancellationToken cancellationToken) => Task.FromResult<Branch?>(branchId == branch.Id ? branch : null);
        public Task<User?> GetUserAsync(long userId, CancellationToken cancellationToken) => Task.FromResult<User?>(userId == user.Id ? user : null);
    }

    private sealed class AllowAllPermissions : IPermissionEvaluator
    {
        public Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) => Task.FromResult(true);
        public Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) => Task.CompletedTask;
    }
    private sealed class FakeCurrentUser : ICurrentUser { public long UserId => 1; }
    private sealed class FakeClock : IClock { public DateTime UtcNow => new(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc); }
    private sealed class InlineTransactionRunner : ITransactionRunner
    {
        public Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken cancellationToken) => operation(cancellationToken);
        public Task<T> ExecuteWithTransactionAsync<T>(Func<IApplicationTransaction, CancellationToken, Task<T>> operation, CancellationToken cancellationToken) =>
            operation(new FakeApplicationTransaction(), cancellationToken);
    }
    private sealed class FakeApplicationTransaction : IApplicationTransaction;
    private sealed class FakeAuditWriter : IAuditWriter { public Task AppendAsync(AuditLog auditLog, CancellationToken cancellationToken, IApplicationTransaction? transaction = null) => Task.CompletedTask; }
    private sealed class FakeAssignmentReader(bool available) : IBranchAssignmentReader
    {
        public Task<IReadOnlyList<CurrentBranchAssignment>> GetCurrentAssignmentsAsync(long userId, DateTime atUtc, CancellationToken cancellationToken)
        {
            if (!available) return Task.FromResult<IReadOnlyList<CurrentBranchAssignment>>([]);
            var branch = new Branch { Id = 7, Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = true };
            var assignment = new UserBranchAssignment { Id = 8, UserId = userId, BranchId = 7, AssignedByUserId = userId,
                Branch = branch, Status = UserBranchAssignmentStatus.Active, ValidFrom = atUtc.AddDays(-1) };
            return Task.FromResult<IReadOnlyList<CurrentBranchAssignment>>([new CurrentBranchAssignment(assignment, true)]);
        }
    }
}
