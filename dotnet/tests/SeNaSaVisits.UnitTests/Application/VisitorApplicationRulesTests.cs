using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Services;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.ValueObjects;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class VisitorApplicationRulesTests
{
    [Fact]
    public async Task SearchWithoutContactPermissionDoesNotAskRepositoryToSearchContactAndMasksContact()
    {
        var visitor = CreateVisitor();
        var repository = new FakeVisitorRepository(visitor);
        var service = CreateService(repository, canViewContact: false);

        var result = await service.SearchAsync(new VisitorSearchRequest(new PageRequest(), Search: "555"), default);

        Assert.False(repository.LastCriteria!.IncludeContact);
        Assert.Equal("***23", result.Items[0].Phone);
        Assert.Equal("a***@example.test", result.Items[0].Email);
        Assert.True(result.Items[0].ContactMasked);
    }

    [Fact]
    public async Task SearchWithContactPermissionIncludesContactSearchAndReturnsContact()
    {
        var repository = new FakeVisitorRepository(CreateVisitor());
        var service = CreateService(repository, canViewContact: true);

        var result = await service.SearchAsync(new VisitorSearchRequest(new PageRequest(), Search: "555"), default);

        Assert.True(repository.LastCriteria!.IncludeContact);
        Assert.Equal("5550123", result.Items[0].Phone);
        Assert.Equal("ana@example.test", result.Items[0].Email);
        Assert.False(result.Items[0].ContactMasked);
    }

    [Fact]
    public async Task CreatePreservesPythonWhitespaceUppercaseAndHyphenRulesAndEmptyStringDifference()
    {
        var repository = new FakeVisitorRepository();
        var service = CreateService(repository, canViewContact: true);

        await service.CreateAsync(new VisitorCreateRequest(" Ana  ", " Ejemplo ", " ab 12- c "), null, default);
        Assert.Equal("ab 12- c", repository.Added!.Identification!.RawValue);
        Assert.Equal("AB12-C", repository.Added.IdentificationNormalized);

        var emptyRepository = new FakeVisitorRepository();
        var emptyService = CreateService(emptyRepository, true);
        await emptyService.CreateAsync(new VisitorCreateRequest("Ana", "Ejemplo", string.Empty), null, default);
        Assert.Null(emptyRepository.Added!.Identification);
    }

    private static Visitor CreateVisitor() => new()
    {
        Id = 3, FirstName = "Ana", LastName = "Test", Identification = VisitorIdentification.From("00123456789"),
        Phone = "5550123", Email = "ana@example.test", IsActive = true,
        VisitorType = new VisitorType { Id = 1, Code = "V", Name = "Visitor" }
    };

    private static VisitorManagementService CreateService(FakeVisitorRepository repository, bool canViewContact) =>
        new(repository, new FakeVisitorTypeRepository(), new FakeCurrentUser(),
            new FakePermissionEvaluator(canViewContact), new BranchAccessService(new FakeAssignmentReader(), new FakeClock()),
            new FakeClock(), new FakeTransactionRunner(), new AuditService(new FakeAuditWriter(), new FakeClock()));

    private sealed class FakeVisitorRepository(Visitor? item = null) : IVisitorRepository
    {
        public Visitor? Added { get; private set; }
        public VisitorSearchCriteria? LastCriteria { get; private set; }
        public Task<Visitor?> GetByIdAsync(long visitorId, CancellationToken cancellationToken) => Task.FromResult(item ?? Added);
        public Task<(IReadOnlyList<Visitor> Items, int Total)> SearchAsync(VisitorSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken)
        {
            LastCriteria = criteria;
            return Task.FromResult<(IReadOnlyList<Visitor>, int)>((item is null ? [] : [item], item is null ? 0 : 1));
        }
        public Task<bool> IdentificationExistsAsync(string normalizedIdentification, long? excludingVisitorId, CancellationToken cancellationToken) => Task.FromResult(false);
        public Task AddAsync(Visitor visitor, CancellationToken cancellationToken) { visitor.Id = 11; Added = visitor; item = visitor; return Task.CompletedTask; }
        public Task SaveChangesAsync(Visitor visitor, CancellationToken cancellationToken) { item = visitor; return Task.CompletedTask; }
    }

    private sealed class FakeVisitorTypeRepository : IVisitorTypeRepository
    {
        public Task<VisitorType?> GetByIdAsync(long visitorTypeId, CancellationToken cancellationToken) => Task.FromResult<VisitorType?>(null);
    }

    private sealed class FakePermissionEvaluator(bool contact) : IPermissionEvaluator
    {
        public Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) =>
            Task.FromResult(permissionCode switch { "VIEW_VISITOR_CONTACT" => contact, _ => true });
        public Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) =>
            HasPermissionAsync(userId, permissionCode, branchId, cancellationToken).ContinueWith(task =>
            {
                if (!task.Result) throw new ApplicationForbiddenException("Forbidden");
            }, cancellationToken);
    }

    private sealed class FakeCurrentUser : ICurrentUser { public long UserId => 1; }
    private sealed class FakeClock : IClock { public DateTime UtcNow => new(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc); }
    private sealed class FakeAssignmentReader : IBranchAssignmentReader
    {
        public Task<IReadOnlyList<CurrentBranchAssignment>> GetCurrentAssignmentsAsync(long userId, DateTime atUtc, CancellationToken cancellationToken)
        {
            var branch = new Branch { Id = 8, Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = true };
            var assignment = new UserBranchAssignment { Id = 9, UserId = userId, BranchId = 8, Branch = branch,
                AssignedByUserId = userId, Status = UserBranchAssignmentStatus.Active, ValidFrom = atUtc.AddDays(-1) };
            return Task.FromResult<IReadOnlyList<CurrentBranchAssignment>>([new CurrentBranchAssignment(assignment, true)]);
        }
    }
    private sealed class FakeTransactionRunner : ITransactionRunner
    {
        public Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken cancellationToken) => operation(cancellationToken);
        public Task<T> ExecuteWithTransactionAsync<T>(Func<IApplicationTransaction, CancellationToken, Task<T>> operation, CancellationToken cancellationToken) =>
            operation(new FakeApplicationTransaction(), cancellationToken);
    }
    private sealed class FakeApplicationTransaction : IApplicationTransaction;
    private sealed class FakeAuditWriter : IAuditWriter { public Task AppendAsync(AuditLog auditLog, CancellationToken cancellationToken, IApplicationTransaction? transaction = null) => Task.CompletedTask; }
}
