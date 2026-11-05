using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Services;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class AuthorizationAndBranchAccessTests
{
    private static readonly DateTime Now = new(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc);

    [Fact]
    public async Task DenyOverridesAllowAndActiveRoleGrant()
    {
        var source = new FakePermissionSource { UserActive = true, RoleGrant = true };
        source.AddPermission("P", PermissionScope.Branch);
        source.Grants.Add(Grant(PermissionEffect.Allow, branchId: 7));
        source.Grants.Add(Grant(PermissionEffect.Deny, branchId: 7));
        var evaluator = Evaluator(source, Assignment(branchId: 7));

        Assert.False(await evaluator.HasPermissionAsync(1, "P", 7, default));
    }

    [Fact]
    public async Task DirectAllowWinsWhenThereIsNoDenyAndDoesNotNeedRoleGrant()
    {
        var source = new FakePermissionSource { UserActive = true };
        source.AddPermission("P", PermissionScope.Branch);
        source.Grants.Add(Grant(PermissionEffect.Allow, branchId: 7));
        var evaluator = Evaluator(source, Assignment(branchId: 7));

        Assert.True(await evaluator.HasPermissionAsync(1, "P", 7, default));
    }

    [Fact]
    public async Task RoleGrantIsUsedOnlyWhenNoApplicableDirectGrantExists()
    {
        var source = new FakePermissionSource { UserActive = true, RoleGrant = true };
        source.AddPermission("P", PermissionScope.Branch);
        var evaluator = Evaluator(source, Assignment(branchId: 7));

        Assert.True(await evaluator.HasPermissionAsync(1, "P", 7, default));
    }

    [Fact]
    public async Task InactiveUserOrPermissionIsDenied()
    {
        var source = new FakePermissionSource { UserActive = false, RoleGrant = true };
        source.AddPermission("P", PermissionScope.Global);
        var evaluator = Evaluator(source);
        Assert.False(await evaluator.HasPermissionAsync(1, "P", null, default));

        source.UserActive = true;
        source.Permissions["P"].IsActive = false;
        Assert.False(await evaluator.HasPermissionAsync(1, "P", null, default));
    }

    [Fact]
    public async Task GlobalPermissionRejectsBranchIdAndAcceptsOnlyGlobalDirectGrant()
    {
        var source = new FakePermissionSource { UserActive = true };
        source.AddPermission("P", PermissionScope.Global);
        source.Grants.Add(Grant(PermissionEffect.Allow, branchId: null));
        var evaluator = Evaluator(source);

        Assert.False(await evaluator.HasPermissionAsync(1, "P", 7, default));
        Assert.True(await evaluator.HasPermissionAsync(1, "P", null, default));
    }

    [Fact]
    public async Task BranchPermissionRequiresMatchingCurrentActiveBranch()
    {
        var source = new FakePermissionSource { UserActive = true, RoleGrant = true };
        source.AddPermission("P", PermissionScope.Branch);
        var evaluator = Evaluator(source, Assignment(branchId: 7));

        Assert.False(await evaluator.HasPermissionAsync(1, "P", null, default));
        Assert.True(await evaluator.HasPermissionAsync(1, "P", 7, default));
        Assert.False(await evaluator.HasPermissionAsync(1, "P", 8, default));
    }

    [Fact]
    public async Task DirectGrantIsStartInclusiveAndEndExclusive()
    {
        var source = new FakePermissionSource { UserActive = true };
        source.AddPermission("P", PermissionScope.Global);
        source.Grants.Add(new UserPermission
        {
            UserId = 1, PermissionId = 12, Effect = PermissionEffect.Allow,
            ValidFrom = Now, ValidUntil = Now.AddHours(1), IsActive = true
        });
        var evaluator = Evaluator(source);

        Assert.True(await evaluator.HasPermissionAsync(1, "P", null, default));
        source.Grants[0].ValidFrom = Now.AddTicks(1);
        Assert.False(await evaluator.HasPermissionAsync(1, "P", null, default));
        source.Grants[0].ValidFrom = Now;
        source.Grants[0].ValidUntil = Now;
        Assert.False(await evaluator.HasPermissionAsync(1, "P", null, default));
    }

    [Fact]
    public async Task BranchAccessRejectsNoExpiredInactiveOrAmbiguousAssignments()
    {
        var reader = new FakeAssignmentReader();
        var access = new BranchAccessService(reader, new FakeClock(Now));
        Assert.Null(await access.GetCurrentContextAsync(1, default));

        reader.Assignments = [Assignment(branchId: 7, from: Now.AddDays(-2), until: Now.AddTicks(-1))];
        Assert.Null(await access.GetCurrentContextAsync(1, default));

        reader.Assignments = [Assignment(branchId: 7, branchActive: false)];
        Assert.Null(await access.GetCurrentContextAsync(1, default));

        reader.Assignments = [Assignment(branchId: 7), Assignment(branchId: 8)];
        Assert.Null(await access.GetCurrentContextAsync(1, default));
    }

    [Fact]
    public async Task BranchAccessUsesInclusiveStartAndExclusiveEnd()
    {
        var reader = new FakeAssignmentReader
        {
            Assignments = [Assignment(branchId: 7, from: Now, until: Now.AddHours(1))]
        };
        var access = new BranchAccessService(reader, new FakeClock(Now));

        Assert.Equal(7, (await access.GetCurrentContextAsync(1, default))?.BranchId);
        reader.Assignments = [Assignment(branchId: 7, from: Now.AddHours(-1), until: Now)];
        Assert.Null(await access.GetCurrentContextAsync(1, default));
    }

    private static PermissionService Evaluator(FakePermissionSource source, params CurrentBranchAssignment[] assignments) =>
        new(source, new BranchAccessService(new FakeAssignmentReader { Assignments = assignments }, new FakeClock(Now)), new FakeClock(Now));

    private static CurrentBranchAssignment Assignment(long branchId, bool branchActive = true, DateTime? from = null, DateTime? until = null)
    {
        var branch = new Branch { Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = branchActive };
        return new CurrentBranchAssignment(new UserBranchAssignment
        {
            Id = branchId + 100,
            UserId = 1,
            BranchId = branchId,
            Branch = branch,
            AssignedByUserId = 1,
            Status = UserBranchAssignmentStatus.Active,
            ValidFrom = from ?? Now.AddDays(-1),
            ValidUntil = until
        }, branchActive);
    }

    private static UserPermission Grant(PermissionEffect effect, long? branchId) => new()
    {
        UserId = 1, PermissionId = 12, BranchId = branchId, Effect = effect,
        ValidFrom = Now.AddDays(-1), IsActive = true
    };

    private sealed class FakeClock(DateTime now) : IClock
    {
        public DateTime UtcNow { get; } = now;
    }

    private sealed class FakeAssignmentReader : IBranchAssignmentReader
    {
        public IReadOnlyList<CurrentBranchAssignment> Assignments { get; set; } = [];

        public Task<IReadOnlyList<CurrentBranchAssignment>> GetCurrentAssignmentsAsync(long userId, DateTime atUtc, CancellationToken cancellationToken) =>
            Task.FromResult(Assignments);
    }

    private sealed class FakePermissionSource : IPermissionDataSource
    {
        public bool? UserActive { get; set; }
        public bool RoleGrant { get; set; }
        public Dictionary<string, Permission> Permissions { get; } = new();
        public List<UserPermission> Grants { get; } = [];
        public void AddPermission(string code, PermissionScope scope) => Permissions[code] = new Permission
        {
            Id = 12, Code = code, Name = code, Resource = "r", Action = "a", Scope = scope, IsActive = true
        };
        public Task<bool?> GetUserActiveAsync(long userId, CancellationToken cancellationToken) => Task.FromResult(UserActive);
        public Task<Permission?> GetPermissionAsync(string code, CancellationToken cancellationToken) => Task.FromResult(Permissions.GetValueOrDefault(code));
        public Task<IReadOnlyCollection<UserPermission>> GetDirectGrantsAsync(long userId, long permissionId, CancellationToken cancellationToken) =>
            Task.FromResult<IReadOnlyCollection<UserPermission>>(Grants);
        public Task<bool> HasActiveRoleGrantAsync(long userId, long permissionId, CancellationToken cancellationToken) => Task.FromResult(RoleGrant);
    }
}
